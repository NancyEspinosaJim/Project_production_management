"""Aggregate production planning module"""
import logging.config
from copy import deepcopy
from typing import Dict

import numpy as np
import pandas as pd

logging.config.fileConfig('logging.conf')
logger = logging.getLogger('AggProdPlan')

STANDARD_PRODUCTION_TIME = 10
AGGREGATE_DEMAND_COLUMNS = ['forecasting', 'initial_inventory', 'final_inventory', 'month_net_demand', 'aggregate_demand']
np.seterr('raise')


class AggProdPlan:
    """
    Class that encapsulate the solving of aggregate production planning problem.

    Parameters:
        cost_to_hold_inventory (int): Cost to hold inventory
        results_path (str): path to save results.

    Attributes:
        __total_demand_per_month (list): Save total demand per month
        __cost_to_hold_inventory (int): Save cost to hold inventory
        __standard_time (pd.DataFrame): DataFrame with standard time by reference
        __costs_and_available_hours (pd.DataFrame): DataFrame with costs and available hours
        __stocks_and_forecasting: (pd.DataFrame): DataFrame with stocks and forecasting by reference
        __aggregate_demand_by_reference (dict): Dictionary with aggregate demand by reference
        __results_path (str): path to save results.
    """

    def __init__(self, cost_to_hold_inventory: int, results_path: str):
        self.__total_demand_per_month = []
        self.__cost_to_hold_inventory = cost_to_hold_inventory
        self.__standard_time = None
        self.__costs_and_available_hours = None
        self.__stocks_and_forecasting = None
        self.__aggregate_demand_by_reference: Dict[str, pd.DataFrame] = {}
        self.__results_path = results_path

    def __net_demand(self, months: int) -> None:
        """
        Calculate net demand for each reference

        Parameters:
            months (int): Forecasting months
        """
        for row in self.__stocks_and_forecasting.itertuples():
            dataframe = pd.DataFrame(columns=AGGREGATE_DEMAND_COLUMNS)
            initial_inventory = row.final_inventory
            row_forecasting = np.array(np.safe_eval(row.forecastings)).flatten()
            for month in range(months):
                forecasting = int(row_forecasting[month])
                final_inventory = initial_inventory - forecasting
                if final_inventory >= 0:
                    month_net_demand = 0
                else:
                    month_net_demand = abs(final_inventory)
                    final_inventory = 0
                dataframe = pd.concat([
                    dataframe,
                    pd.DataFrame(
                        {
                            'forecasting': [forecasting],
                            'month_net_demand': [month_net_demand],
                            'initial_inventory': [initial_inventory],
                            'final_inventory': [final_inventory]
                        },
                        columns=AGGREGATE_DEMAND_COLUMNS
                    )
                ], ignore_index=True)
                initial_inventory = final_inventory
            self.__aggregate_demand_by_reference[row.reference] = dataframe

    def __aggregate_demand(self) -> None:
        """Calculate aggregate demand for each reference"""
        for reference, dataframe in self.__aggregate_demand_by_reference.items():
            index = 0
            for i, row in dataframe.iterrows():
                month_aggregate_demand = row.month_net_demand * self.__standard_time[
                    self.__standard_time.reference == reference].standard_time_per_unit.values[0]
                row.aggregate_demand = month_aggregate_demand
                self.__total_demand_per_month[index] += month_aggregate_demand
                index += 1

    def aggregate_production_planning(
        self,
        forecasting_path: str,
        stock_path: str,
        costs_and_available_hours_path: str,
        standard_time_path: str
    ) -> dict:
        """
        Encapsulate the solution of aggregate production plan

        Parameters:
            forecasting_path (str): Forecasting csv path.
            stock_path (str): Stock csv path.
            costs_and_available_hours_path (str): Costs and available hours csv path.
            standard_time_path (str): Standard time csv path.
        """
        forecasting = pd.read_csv(forecasting_path, delimiter=',')
        stock = pd.read_csv(stock_path, delimiter=',')
        self.__standard_time = pd.read_csv(standard_time_path, delimiter=',')
        stocks_and_forecasting = pd.merge(forecasting, stock, on='reference')
        filtered_monthly = pd.read_csv('inputs/filtered_monthly.csv', delimiter=',')
        shoes_classes = filtered_monthly.groupby(["clase"])
        results = {}
        for shoes_class, dataframe in shoes_classes:
            if shoes_class == 'ARGYLL' or shoes_class == 'PVC':
                logger.info('Calculating aggregate production planning for %s ...', shoes_class)
                self.__costs_and_available_hours = pd.read_csv(
                    costs_and_available_hours_path.format(shoes_class=shoes_class.lower()),
                    delimiter=','
                )
                self.__stocks_and_forecasting = deepcopy(stocks_and_forecasting)
                references = dataframe['Descripcion'].unique().tolist()
                self.__stocks_and_forecasting = self.__stocks_and_forecasting[self.__stocks_and_forecasting.reference.isin(references)]

                months = len(np.safe_eval(forecasting.forecastings[0]))
                self.__total_demand_per_month = [0 for i in range(months)]
                logger.info('Calculating net demand...')
                self.__net_demand(months)
                logger.info('Calculating aggregate demand...')
                self.__aggregate_demand()
                logger.info('Total demand: %s', self.__total_demand_per_month)
                cost_per_kind_of_hour = [
                    self.__costs_and_available_hours.cost_per_hour.values,
                    self.__costs_and_available_hours.cost_per_extra_hour.values
                ]
                available_hours = [
                    self.__costs_and_available_hours.hours_available.values,
                    self.__costs_and_available_hours.extra_hours_available.values
                ]
                families_dataframe = dataframe.loc[:, ['Linea', 'Descripcion']]
                families_dataframe = families_dataframe[
                    families_dataframe['Descripcion'].isin(self.__stocks_and_forecasting.reference.values)]
                results[shoes_class] = {
                    'cost_per_kind_of_hour': cost_per_kind_of_hour,
                    'available_hours': available_hours,
                    'total_demand_per_month': self.__total_demand_per_month,
                    'months': months,
                    'aggregate_demand_by_reference': self.__aggregate_demand_by_reference,
                    'standard_time': self.__standard_time,
                    'families_dataframe': families_dataframe

                }
                logger.info('Exporting aggregation production plan results...')
                self.__export_agg_prod_plan(shoes_class, families_dataframe, months)

        return results

    def __export_agg_prod_plan(self, shoes_class: str, families_dataframe: pd.DataFrame, months: int) -> None:
        """
        Export aggregation production plan results by shoes class to csv format.

        Parameters:
            shoes_class (str): Shoes class name
            families_dataframe (pd.DataFrame): Dataframe with families and references columns by shoes class
            months (int): forecasting months.
        """
        #families = families_dataframe['Linea'].unique().tolist()
        families = families_dataframe.groupby('Linea')
        columns = ['family']
        for i in range(months):
            columns.append(f'month_{str(i+1)}_initial_inventory')
            columns.append(f'month_{str(i+1)}_forecasting')
            columns.append(f'month_{str(i+1)}_final_inventory')
            columns.append(f'month_{str(i+1)}_agg_demand')
        dataframe = pd.DataFrame(columns=columns)
        final_row = {'family': 'Total aggregate demand'}

        for family, dt in families:
            row_data = {'family': family}
            references = dt['Descripcion'].unique().tolist()
            for month in range(months):
                aggregate_demand_by_family = 0
                forecasting_by_family = 0
                initial_inventory_by_family = 0
                final_inventory_by_family = 0
                for reference in references:
                    reference_dataframe = self.__aggregate_demand_by_reference[reference]
                    row = reference_dataframe.iloc[month, :]
                    aggregate_demand_by_family += row.aggregate_demand
                    forecasting_by_family += row.forecasting
                    initial_inventory_by_family += row.initial_inventory
                    final_inventory_by_family += row.final_inventory
                row_data[f'month_{month+1}_agg_demand'] = aggregate_demand_by_family
                row_data[f'month_{month+1}_forecasting'] = int(forecasting_by_family)
                row_data[f'month_{month+1}_initial_inventory'] = int(initial_inventory_by_family)
                row_data[f'month_{month+1}_final_inventory'] = int(final_inventory_by_family)
            dataframe = pd.concat([dataframe, pd.DataFrame(data=[row_data])], ignore_index=True)

        for month in range(months):
            final_row[f'month_{month+1}_agg_demand'] = dataframe.loc[:, [f'month_{month+1}_agg_demand']].values.sum()
            final_row[f'month_{month+1}_forecasting'] = dataframe.loc[:, [f'month_{month+1}_forecasting']].values.sum()
            final_row[f'month_{month+1}_initial_inventory'] = dataframe.loc[:, [f'month_{month+1}_initial_inventory']].values.sum()
            final_row[f'month_{month+1}_final_inventory'] = dataframe.loc[:, [f'month_{month+1}_final_inventory']].values.sum()

        dataframe = pd.concat([dataframe, pd.DataFrame(data=[final_row])], ignore_index=True)
        dataframe.to_excel(self.__results_path.format(shoes_class=shoes_class.lower()), sheet_name='agg_prod_plan')
        self._export_by_reference(shoes_class, months)

    def _export_by_reference(self, shoes_class: str, months: int):

        columns = ['reference']
        for i in range(months):
            columns.append(f'month_{str(i+1)}_agg_demand')
            columns.append(f'month_{str(i+1)}_net_demand')
        dataframe = pd.DataFrame(columns=columns)

        references = self.__stocks_and_forecasting.reference.unique().tolist()

        for reference in references:
            dt = self.__aggregate_demand_by_reference[reference]
            row_data = {'reference': reference}
            for month, row in dt.iterrows():
                row_data[f'month_{month + 1}_agg_demand'] = row.aggregate_demand
                row_data[f'month_{month + 1}_net_demand'] = row.month_net_demand

            dataframe = pd.concat([dataframe, pd.DataFrame(data=[row_data])], ignore_index=True)

        dataframe.to_excel(f"outputs/agg_by_reference_{shoes_class.lower()}.xlsx")
