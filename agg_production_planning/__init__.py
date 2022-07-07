"""Main module"""
import logging.config

from agg_prod_plan import AggProdPlan
from linear_prog_model import LinearProgrammingModel
from material_req_plan import MaterialReqPlan
from prod_master_plan import ProdMasterPlan

logging.config.fileConfig('logging.conf')
logger = logging.getLogger('root')
FORECASTING_PATH = 'inputs/forecasting_score_data_may.csv'
STOCK_PATH = 'inputs/stock_data_may.csv'
COST_AND_AVAILABLE_HOURS_PATH = 'inputs/hours_available_{shoes_class}.csv'
STANDARD_TIME_PATH = 'inputs/standard_time.csv'
COST_TO_HOLD_INVENTORY = 200
EXCEL_PATH = 'outputs/results_{shoes_class}.xlsx'

if __name__ == '__main__':
    logger.info('Calculating aggregate production planning...')
    agg_prod_plan = AggProdPlan(COST_TO_HOLD_INVENTORY, EXCEL_PATH)
    results = agg_prod_plan.aggregate_production_planning(
        forecasting_path=FORECASTING_PATH,
        stock_path=STOCK_PATH,
        costs_and_available_hours_path=COST_AND_AVAILABLE_HOURS_PATH,
        standard_time_path=STANDARD_TIME_PATH
    )
    for shoes_class, result in results.items():
        logger.info('Solving problems for %s...', shoes_class)
        logger.info('Solving linear programming problem...')
        months = result.get('months')
        cost_per_kind_of_hour = result.get('cost_per_kind_of_hour')
        available_hours = result.get('available_hours')
        total_demand_by_month = result.get('total_demand_per_month')
        linear_programming_model = LinearProgrammingModel(
            months=months,
            kind_of_times=['n', 'e'],
            cost_per_kind_of_hour=cost_per_kind_of_hour,
            available_hours=available_hours,
            total_demand_by_month=total_demand_by_month,
            cost_to_hold_inventory=COST_TO_HOLD_INVENTORY
        )
        demand_assignation, time_assignation = linear_programming_model.solve_linear_prog_problem()

        logger.info('Calculating production master plan...')
        aggregate_demand_by_reference = result.get('aggregate_demand_by_reference')
        standard_time = result.get('standard_time')
        prod_master_plan = ProdMasterPlan(
            aggregate_demand_by_reference=aggregate_demand_by_reference,
            total_aggregate_demand=total_demand_by_month,
            demand_assignation=demand_assignation,
            standard_time=standard_time,
            cost_per_kind_of_hour=cost_per_kind_of_hour,
            available_hours=available_hours,
            cost_to_hold_inventory=COST_TO_HOLD_INVENTORY
        )
        production_master_planning = prod_master_plan.production_master_planning()

        logger.info('Calculating MPR...')
        families_dataframe = result.get('families_dataframe')
        material_req_plan = MaterialReqPlan(
            months=months,
            production_master_planning_by_reference=production_master_planning,
            references_by_families=families_dataframe,
            results_path=EXCEL_PATH,
            shoes_class=shoes_class)
        material_req_plan.calculate_mrp()

        logger.info('Exporting time assignation results...')
        linear_programming_model.export_time_assignation(
            shoes_class=shoes_class,
            time_assignation=time_assignation,
            months=months,
            results_path=EXCEL_PATH
        )

        logger.info('Exporting production master plan results...')
        prod_master_plan.export_prod_master_plan(
            shoes_class=shoes_class,
            families_dataframe=families_dataframe,
            production_master_plan=production_master_planning,
            months=months,
            results_path=EXCEL_PATH
        )
        logger.info('Done for %s!', shoes_class)
    logger.info('Done!')
