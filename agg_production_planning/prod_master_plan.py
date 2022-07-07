"""Production master plan module"""
import logging.config
from typing import Dict

import pandas as pd

logging.config.fileConfig('logging.conf')
logger = logging.getLogger('ProdMasterPlan')

PRODUCTION_MASTER_PLAN_COLUMNS = [
    'forecasting',
    'initial_inventory',
    'aggregate_demand',
    'disaggregation_percent',
    'disaggregation_normal_hours',
    'disaggregation_extra_hours',
    'production_normal_hours',
    'production_extra_hours',
    'deficit',
    'labor_cost',
    'raw_material_cost',
    'total_manufacturing_cost',
    'inventory_cost',
    'deficit_cost',
    'overrun',
    'total_cost_operation',
    'total_production_cost'
]
STOCK_PATH = 'inputs/stock_data_may.csv'
DEFICIT_COST = 1000


class ProdMasterPlan:
    """
    Class that encapsulate the solving of production master plan problems.

    Parameters:
        aggregate_demand_by_reference (dict): Dict with aggregate demand results by reference.
        total_aggregate_demand (list): list with total demand by moth results.
        demand_assignation (list): list with demand assignation results.
        standard_time (pd.DataFrame): DataFrame with standard time by reference.
        cost_per_kind_of_hour (list): list with cost per kind of hour.
        available_hours (list): list with available hours per kind of hour.
        cost_to_hold_inventory (int): cost to hold inventory by shoes class.
        deficit_cost (int): Deficit cost.

    Attributes:
        __aggregate_demand_by_reference (dict): Dict with aggregate demand results by reference.
        __total_aggregate_demand (list): list with total demand by moth results.
        __demand_assignation (list): list with demand assignation results.
        __standard_time (pd.DataFrame): DataFrame with standard time by reference.
        __cost_per_kind_of_hour (list): list with cost per kind of hour.
        __available_hours (list): list with available hours per kind of hour.
        __cost_to_hold_inventory (int): cost to hold inventory by shoes class.
        __deficit_cost (int): Deficit cost.
        __disaggregation_percent (float): disaggregation percent.
        __production_master_plan_by_reference (dict): Dict to save production master plan results by reference.
        __stock_data (pd.DataFrame): Stock information dataframe.
        __total_production (float): total production result.
    """

    def __init__(
            self,
            aggregate_demand_by_reference: Dict[str, pd.DataFrame],
            total_aggregate_demand: list,
            demand_assignation: list,
            standard_time: pd.DataFrame,
            cost_per_kind_of_hour: list,
            available_hours: list,
            cost_to_hold_inventory: int,
            deficit_cost: int = DEFICIT_COST

    ):
        self.__aggregate_demand_by_reference = aggregate_demand_by_reference
        self.__total_aggregate_demand = total_aggregate_demand
        self.__demand_assignation = demand_assignation
        self.__standard_time = standard_time
        self.__cost_per_kind_of_hour = cost_per_kind_of_hour
        self.__available_hours = available_hours
        self.__cost_to_hold_inventory = cost_to_hold_inventory
        self.__deficit_cost = deficit_cost
        self.__disaggregation_percent = 0.0
        self.__production_master_plan_by_reference = {}
        self.__stock_data = pd.read_csv(STOCK_PATH, delimiter=',')
        self.__total_production = 0.0
        self._months = len(total_aggregate_demand)

    def production_master_planning(self) -> dict:
        """
        Calculate production master planning and return it.

        Returns:
            __production_master_plan_by_reference (dict): production master planning by reference.
        """
        self._master_disaggregation()
        self._calculate_production_by_time()
        self._calculate_deficit()
        self._calculate_costs()
        total_cost = self._calculate_total_costs()
        logger.info('Total cost: %d', total_cost)
        return self.__production_master_plan_by_reference

    def _calculate_total_aggregate_demand(self) -> list:
        """
        Calculate total aggregate demand by month

        Returns:
            total_aggregate_demand (float): total month aggregate demand
        """
        total_aggregate_demand = [0.0 for _ in range(self._months)]
        for month in range(self._months):
            for reference, dataframe in self.__aggregate_demand_by_reference.items():
                total_aggregate_demand[month] += dataframe.loc[month, ['aggregate_demand']].values[0]
        return total_aggregate_demand

    def _master_disaggregation(self) -> None:
        """Calculate disaggregation variables values."""
        total_aggregate_demand = self._calculate_total_aggregate_demand()
        for reference, dataframe in self.__aggregate_demand_by_reference.items():
            prod_master_plan_dataframe = pd.DataFrame(columns=PRODUCTION_MASTER_PLAN_COLUMNS)
            for index, row in dataframe.iterrows():
                try:
                    disaggregation_percent = row.aggregate_demand / total_aggregate_demand[index]
                except (ZeroDivisionError, FloatingPointError):
                    disaggregation_percent = 0
                disaggregation_normal_hours = self.__demand_assignation[0][index] * disaggregation_percent
                disaggregation_extra_hours = self.__demand_assignation[1][index] * disaggregation_percent
                prod_master_plan_dataframe = pd.concat(
                    [
                        prod_master_plan_dataframe,
                        pd.DataFrame({
                            'forecasting': [row.forecasting],
                            'initial_inventory': [row.initial_inventory],
                            'aggregate_demand': [row.aggregate_demand],
                            'disaggregation_percent': [disaggregation_percent],
                            'disaggregation_normal_hours': [disaggregation_normal_hours],
                            'disaggregation_extra_hours': [disaggregation_extra_hours]
                        }, columns=PRODUCTION_MASTER_PLAN_COLUMNS)
                    ], ignore_index=True
                )
            self.__production_master_plan_by_reference[reference] = prod_master_plan_dataframe

    def _calculate_production_by_time(self) -> None:
        """Calculate production per kind of times and total production."""
        for reference, dataframe in self.__production_master_plan_by_reference.items():
            standard_time = self.__standard_time[
                self.__standard_time.reference == reference].standard_time_per_unit.values[0]
            for index, row in dataframe.iterrows():
                try:
                    row.production_normal_hours = row.disaggregation_normal_hours / standard_time
                except (ZeroDivisionError, FloatingPointError):
                    row.production_normal_hours = 0
                try:
                    row.production_extra_hours = row.disaggregation_extra_hours / standard_time
                except (ZeroDivisionError, FloatingPointError):
                    row.production_extra_hours = 0

                self.__total_production += row.production_normal_hours + row.production_extra_hours

    def _calculate_deficit(self) -> None:
        """Calculate deficit by reference."""
        for reference, dataframe in self.__production_master_plan_by_reference.items():
            for index, row in dataframe.iterrows():
                row.deficit = self.__stock_data[self.__stock_data.reference == reference].final_inventory.values[0] + \
                              row.production_normal_hours + row.production_extra_hours - row.forecasting

    def _calculate_costs(self) -> None:
        """Calculate all costs by reference."""
        for reference, dataframe in self.__production_master_plan_by_reference.items():
            for index, row in dataframe.iterrows():
                production = row.production_normal_hours + row.production_extra_hours
                standard_time_reference = self.__standard_time[self.__standard_time.reference == reference]
                standard_time_reference_cost = standard_time_reference.standard_time_per_unit.values[0]
                normal_hour_cost = self.__cost_per_kind_of_hour[0][index]

                row.labor_cost = production * normal_hour_cost * standard_time_reference_cost
                row.raw_material_cost = production * standard_time_reference.cost_per_unit.values[0]
                row.total_manufacturing_cost = row.labor_cost + row.raw_material_cost
                row.inventory_cost = row.initial_inventory * self.__cost_to_hold_inventory * \
                                     standard_time_reference_cost
                row.deficit_cost = row.deficit * self.__deficit_cost
                row.overrun = row.production_extra_hours * standard_time_reference_cost * \
                              (self.__cost_per_kind_of_hour[1][index] - normal_hour_cost)
                row.total_cost_operation = row.inventory_cost + row.deficit_cost + row.overrun
                row.total_production_cost = row.total_cost_operation + row.total_manufacturing_cost

    def _calculate_total_costs(self) -> float:
        """
        Calculate production master plan total cost and return it.

        Returns:
            total_production_cost (float): total production cost.
        """
        total_production_cost = 0.0
        for reference, dataframe in self.__production_master_plan_by_reference.items():
            total_production_cost += dataframe.total_production_cost.sum()
        return total_production_cost

    @staticmethod
    def export_prod_master_plan(
            shoes_class: str,
            families_dataframe: pd.DataFrame,
            production_master_plan: dict,
            months: int,
            results_path: str
    ) -> None:
        """
        Export production master plan results by shoes class to csv format.

        Parameters:
            shoes_class (str): Shoes class name.
            families_dataframe (pd.DataFrame): Dataframe with families and references columns by shoes class.
            production_master_plan (dict): Dict with production master plan dataframes by references.
            months (int): forecasting months.
            results_path (str): path to save results.
        """
        #families = families_dataframe['Linea'].unique().tolist()
        families = families_dataframe.groupby('Linea')
        columns = ['family_production'] + [f'month_{str(i + 1)}' for i in range(months)]
        dataframe = pd.DataFrame(columns=columns)
        final_normal_row = {'family_production': 'Total production normal hours'}
        final_extra_row = {'family_production': 'Total production extra hours'}
        for family, dt in families:
            row_normal_data = {'family_production': f'{family} production normal hours'}
            row_extra_data = {'family_production': f'{family} production extra hours'}
            references = dt['Descripcion'].unique().tolist()
            for month in range(months):
                production_normal_hours_by_family = 0
                production_extra_hours_by_family = 0
                for reference in references:
                    reference_dataframe = production_master_plan[reference]
                    production_normal_hours_by_family += reference_dataframe.loc[month, ['production_normal_hours']]
                    production_extra_hours_by_family += reference_dataframe.loc[month, ['production_extra_hours']]
                row_normal_data[f'month_{month + 1}'] = int(production_normal_hours_by_family)
                row_extra_data[f'month_{month + 1}'] = int(production_extra_hours_by_family)
            dataframe = pd.concat([dataframe, pd.DataFrame(data=[row_normal_data])], ignore_index=True)
            dataframe = pd.concat([dataframe, pd.DataFrame(data=[row_extra_data])], ignore_index=True)

        for month in range(months):
            final_normal_row[f'month_{month + 1}'] = dataframe.loc[dataframe.iloc[:, 0].str.contains('normal hours'),
                                                                   [f'month_{month + 1}']].values.sum()
            final_extra_row[f'month_{month + 1}'] = dataframe.loc[dataframe.iloc[:, 0].str.contains('extra hours'),
                                                                  [f'month_{month + 1}']].values.sum()

        dataframe = pd.concat([dataframe, pd.DataFrame(data=[final_normal_row])], ignore_index=True)
        dataframe = pd.concat([dataframe, pd.DataFrame(data=[final_extra_row])], ignore_index=True)
        excel_writer = results_path.format(shoes_class=shoes_class.lower())
        with pd.ExcelWriter(excel_writer, mode='a') as writer:
            dataframe.to_excel(writer, sheet_name='prod_master_plan')
