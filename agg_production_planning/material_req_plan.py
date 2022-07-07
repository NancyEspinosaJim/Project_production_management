"""Material requirement plan module"""
import math
from typing import Dict

import pandas as pd

SHOES_CLASS_EXCEL_PATH = 'inputs/mrp_{shoes_class}.xlsx'
SHOES_CLASS_DATA_EXCEL_PATH = 'inputs/data_{shoes_class}.xlsx'
MRP_COLUMNS = [
    'gross_requirement',
    'planned_reception',
    'stock',
    'net_requirement',
    'order_receiving_plan',
    'order_release_plan',
    'setup_cost',
    'maintenance_cost',
    'inventory_management_cost'
]


class MaterialReqPlan:
    """
    Class that encapsulate the solving of material requirement plan problems.

    Parameters:
        months (int): Forecasting months.
        production_master_planning_by_reference (dict): Dict with production master planning by reference.
        references_by_families (pd.DataFrame): Dataframe with families and references by shoes class.
        results_path (str): path to save results.
        shoes_class (str): shoes class name.

    Attributes:
        __months (int): Forecasting months + 1.
        __production_master_planning_by_reference (dict): Dict with production master planning by reference.
        __references_by_families (pd.DataFrame): Dataframe with families and references by shoes class.
        __mrp_by_families (dict): Dict to save mrp results by families.
        __families (list): List with families names.
        __order_release_plan_resume_by_families (dict): Dict to save order release plan resume by families.
        __results_path (str): path to save results.
        __shoes_class_dataframes (dict): Dict with mrp dataframes per family.
        __shoes_class_data (pd.DataFrame): Dataframe with data per shoes class.
    """

    def __init__(self, months: int, production_master_planning_by_reference: dict,
                 references_by_families: pd.DataFrame, results_path: str, shoes_class: str):
        self.__months = months + 1
        self.__production_master_planning_by_reference = production_master_planning_by_reference
        self.__references_by_families = references_by_families
        self.__mrp_by_families: Dict[str, Dict[str, pd.DataFrame]] = {}
        self.__families = references_by_families['Linea'].unique().tolist()
        self.__order_release_plan_resume_by_families = {}
        self.__results_path = results_path.format(shoes_class=shoes_class)
        self.__shoes_class_dataframes = pd.read_excel(
            SHOES_CLASS_EXCEL_PATH.format(shoes_class=shoes_class.lower()),
            sheet_name=None
        )
        self.__shoes_class_data = pd.read_excel(
            SHOES_CLASS_DATA_EXCEL_PATH.format(shoes_class=shoes_class.lower()),
            sheet_name=shoes_class.lower()
        )
        self.__shoes_class_data.fillna(0.0, inplace=True)

    def \
            __build_tables(self) -> None:
        """Build a dict with dataframe by components in csv family and save its in general dict."""
        self.__dataframes_by_families = self.__references_by_families.groupby(['Linea'])
        for family in self.__families:
            data = self.__shoes_class_dataframes.get(family)
            if data is not None:
                self.__mrp_by_families[family] = {}
                for i in range(len(data)):
                    key = data.iloc[i, 0]
                    dataframe = pd.DataFrame(columns=MRP_COLUMNS)
                    self.__mrp_by_families[family][key] = dataframe
                self.__mrp_by_families[family]['total_inventory_management_cost'] = []

    def __calculate_gross_requirement(self, family: str, dataframe: pd.DataFrame) -> None:
        """
        Calculate gross requirement of family dataframe.

        Parameters:
            family (str): Family name.
            dataframe (pd.DataFrame): Family dataframe.
        """
        references = self.__references_by_families[self.__references_by_families.Linea == family][
            'Descripcion'].values
        for month in range(self.__months - 1):
            gross_requirement = 0
            for reference in references:
                reference_month_pmp = self.__production_master_planning_by_reference[reference].loc[
                    month, ['production_normal_hours', 'production_extra_hours']]
                gross_requirement += reference_month_pmp.production_normal_hours + \
                                     reference_month_pmp.production_extra_hours
            dataframe.loc[month + 1, ['gross_requirement']] = round(gross_requirement, 1)

    def __calculate_next_columns(self, mrp_dataframe: pd.DataFrame, data: pd.DataFrame) -> None:
        """
        Calculate dataframe missing columns values.

        Parameters:
            mrp_dataframe (pd.DataFrame): Family dataframe.
            data (pd.DataFrame): dataframe with components data filter by family.
        """
        for month in range(1, self.__months):
            actual_row = mrp_dataframe.loc[month, :]
            previous_row = mrp_dataframe.loc[month - 1, :]
            gross_requirement = actual_row.gross_requirement
            previous_stock = previous_row.stock
            net_requirement = round(
                gross_requirement + data.security_stock.values[0] - previous_stock - actual_row.planned_reception,
                1
            )
            if net_requirement < 0:
                net_requirement = 0
            actual_row.net_requirement = net_requirement
            lot_size = data.lot_size.values[0]
            order_receiving_plan = round(math.ceil(net_requirement / lot_size) * lot_size, 1)
            actual_row.order_receiving_plan = order_receiving_plan
            previous_row.order_release_plan = order_receiving_plan
            stock = previous_stock + order_receiving_plan - gross_requirement + actual_row.planned_reception
            actual_row.stock = round(stock, 1)

    def __calculate_costs(self, mrp_dataframe: pd.DataFrame, data: pd.DataFrame) -> None:
        """
        Calculate dataframe cost columns values.

        Parameters:
            mrp_dataframe (pd.DataFrame): Family dataframe.
            data (pd.DataFrame): dataframe with components data filter by actual component.
        """
        for month in range(1, self.__months):
            row = mrp_dataframe.loc[month, :]
            if row.order_release_plan > 0:
                row.setup_cost = round(data.cost_of_order_or_enlistment.values[0], 1)
            else:
                row.setup_cost = 0.0
            row.maintenance_cost = round(row.stock * data.stock_maintenance_cost.values[0], 1)
            row.inventory_management_cost = row.setup_cost + row.maintenance_cost

    def __calculate_components_matrix(self, family: str) -> None:
        """
        Calculate family components dataframes.

        Parameters:
            family (str): Family name.
        """
        family_dataframe = self.__shoes_class_dataframes[family]
        family_dict = self.__mrp_by_families[family]
        for component, dataframe in family_dict.items():
            if component != family and component != 'total_inventory_management_cost':
                component_data = self.__shoes_class_data[self.__shoes_class_data.iloc[:, 0] == component]
                component_dataframe = family_dataframe[family_dataframe.iloc[:, 0] == component]
                columns = component_dataframe.columns
                for month in range(1, self.__months):
                    gross_requirement = 0.0
                    for column in columns:
                        if column != 'cross' and column != component:
                            required_quantity = component_dataframe.loc[:, [column]].values.flatten()[0]
                            if required_quantity > 0:
                                gross_requirement += required_quantity *\
                                                     family_dict[column].loc[month, ['order_release_plan']].values[0]
                    dataframe.loc[month, ['gross_requirement']] = round(gross_requirement, 1)

                planned_reception_month = component_data.pr_month.values[0]
                planned_reception = round(component_data.planned_reception.values[0], 1)
                dataframe.loc[planned_reception_month, ['planned_reception']] = planned_reception
                dataframe.loc[0, ['stock']] = round(component_data.stock.values[0], 1)
                dataframe.fillna(0.0, inplace=True)
                self.__calculate_next_columns(dataframe, component_data)
                self.__calculate_costs(dataframe, component_data)
                family_dict['total_inventory_management_cost'].\
                    append(dataframe.inventory_management_cost.sum())

    def __calculate_family_matrix(self) -> None:
        """Calculate family dataframe."""
        for family in self.__families:
            family_mrp = self.__mrp_by_families.get(family)
            if family_mrp is not None:
                dataframe = family_mrp.get(family)
                if dataframe is not None:
                    family_data = self.__shoes_class_data[self.__shoes_class_data.iloc[:, 0] == family]
                    self.__calculate_gross_requirement(family, dataframe)
                    planned_reception_month = family_data.pr_month.values[0]
                    planned_reception = round(family_data.planned_reception.values[0], 1)
                    dataframe.loc[planned_reception_month, ['planned_reception']] = planned_reception
                    dataframe.loc[0, ['stock']] = round(family_data.stock.values[0], 1)
                    dataframe.fillna(0.0, inplace=True)
                    self.__calculate_next_columns(dataframe, family_data)
                    self.__calculate_costs(dataframe, family_data)
                    self.__mrp_by_families[family]['total_inventory_management_cost']. \
                        append(round(dataframe.inventory_management_cost.sum(), 1))
                    self.__calculate_components_matrix(family)

    def __order_release_plan_resume(self) -> None:
        """Generate order release plan resume per family."""
        columns = ['component'] + [f'month_{str(month)}' for month in range(self.__months)] +\
                  ['total_inventory_management_cost']
        for family, tables in self.__mrp_by_families.items():
            resume_dataframe = pd.DataFrame(columns=columns)
            index = 0
            for component, dataframe in tables.items():
                if component != 'total_inventory_management_cost':
                    row_data = {'component': [component]}
                    for month in range(self.__months):
                        row_data[f'month_{str(month)}'] = [dataframe.loc[month, ['order_release_plan']].values[0]]
                    row_data['total_inventory_management_cost'] = [tables['total_inventory_management_cost'][index]]
                    index += 1
                    resume_dataframe = pd.concat([
                        resume_dataframe,
                        pd.DataFrame(data=row_data, columns=columns)
                    ], ignore_index=True)
            self.__order_release_plan_resume_by_families[family] = resume_dataframe

    def __export_order_release_plan_resume_to_excel(self) -> None:
        """Export order release plan resume results per family to csv format."""
        for family in self.__families:
            dataframe = self.__order_release_plan_resume_by_families.get(family)
            if dataframe is not None:
                with pd.ExcelWriter(self.__results_path, mode='a') as writer:
                    dataframe.to_excel(writer, sheet_name=f'o_r_p_r_{family.replace(" ", "_").lower()}')

    def calculate_mrp(self) -> None:
        """Calculate material requirement plan and export it."""
        self.__build_tables()
        self.__calculate_family_matrix()
        self.__order_release_plan_resume()
        self.__export_order_release_plan_resume_to_excel()
