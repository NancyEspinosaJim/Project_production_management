"""Linear programming model module"""
import logging.config
from typing import Tuple

import pandas as pd
from pulp import LpVariable, LpProblem, LpStatus, value, PULP_CBC_CMD

logging.config.fileConfig('logging.conf')
logger = logging.getLogger('LinearProgModel')


class LinearProgrammingModel:
    """
    Class that encapsulate the solving of linear programming model problems.

    Parameters:
        months (int): number of months to solve.
        kind_of_times (list): list with kind of times variables.
        cost_per_kind_of_hour (list): list with cost per kind of hour.
        available_hours (list): list with available hours per kind of hour.
        total_demand_by_month (list): list with total demand by moth results.
        cost_to_hold_inventory (int): cost to hold inventory by shoes class.
        lp_problem_name (str): Linear programming model problem name.

    Attributes:
        __months (int): number of months to solve.
        __kind_of_times (list): list with kind of times variables.
        __cost_per_kind_of_hour (list): list with cost per kind of hour.
        __available_hours (list): list with available hours per kind of hour.
        __total_demand_by_month (list): list with total demand by moth results.
        __cost_to_hold_inventory (int): cost to hold inventory by shoes class.
        __variables (list): LP variables list.
        __variables_per_kind_of_time (list): LP variables per kind of time filter list.
        __month_variables (list): LP month variables list.
        __constraints_per_kind_of_time (list): LP constraints per kind of time list.
        __demand_constraints (list): LP demand constraints list.
        __objective_function = Linear problem object.
    """

    def __init__(
            self,
            months: int,
            kind_of_times: list,
            cost_per_kind_of_hour: list,
            available_hours: list,
            total_demand_by_month: list,
            cost_to_hold_inventory: int,
            lp_problem_name: str = ''
    ):
        self.__months = months
        self.__kind_of_times = kind_of_times
        self.__cost_per_kind_of_hour = cost_per_kind_of_hour
        self.__available_hours = available_hours
        self.__total_demand_by_month = total_demand_by_month
        self.__cost_to_hold_inventory = cost_to_hold_inventory
        self.__variables = []
        self.__variables_per_kind_of_time = []
        self.__month_variables = []
        self.__constraints_per_kind_of_time = []
        self.__demand_constraints = []
        self.__objective_function = LpProblem(lp_problem_name)

    def __create_variables(self) -> None:
        """
        Create the linear problem variables.
        """
        for kind_of_time in self.__kind_of_times:
            for i in range(self.__months):
                for j in range(i, self.__months):
                    self.__variables.append(LpVariable('x' + str(i + 1) + str(j + 1) + kind_of_time, lowBound=0))

    def __split_variables_per_kind_of_time(self) -> None:
        """
        Split the linear problem variables in a list with the same kind of variables.
        """
        for kind_of_time in self.__kind_of_times:
            time_variables = []
            for variable in self.__variables:
                if kind_of_time in variable.name:
                    time_variables.append(variable)
            self.__variables_per_kind_of_time.append(time_variables)

    def __create_month_variables(self) -> None:
        """
        Split the linear problem variables in a list with the variables for month.
        """
        for i in range(self.__months - 1):
            month_variable = []
            for variable in self.__variables:
                if int(variable.name[2]) - int(variable.name[1]) == (i + 1):
                    month_variable.append(variable)
            self.__month_variables.append(month_variable)

    def __create_constraints(self) -> None:
        """
        Create a list with the linear problem constraints.
        """
        for i in range(self.__months):
            demand_constraint = 0
            for variable_per_kind_of_time in self.__variables_per_kind_of_time:
                constraint = 0
                for variable in variable_per_kind_of_time:
                    if variable.name[1] == str(i + 1):
                        constraint += variable
                    if variable.name[2] == str(i + 1):
                        demand_constraint += variable
                self.__constraints_per_kind_of_time.append(constraint)
            self.__demand_constraints.append(demand_constraint)

    def __create_objective_function(self) -> None:
        """
        Create objective function with yours constrains.
        """
        self.__create_variables()
        self.__split_variables_per_kind_of_time()
        self.__create_month_variables()
        self.__create_constraints()

        objective_function_temp = 0
        index = 0
        constraints = []
        for i, constraint_per_kind_of_time in enumerate(self.__constraints_per_kind_of_time):
            sum_constraint = sum(constraint_per_kind_of_time)
            if i % 2 == 0:
                objective_function_temp += sum_constraint * self.__cost_per_kind_of_hour[0][index]
                constraints.append(sum_constraint <= self.__available_hours[0][index])
            else:
                objective_function_temp += sum_constraint * self.__cost_per_kind_of_hour[1][index]
                constraints.append(sum_constraint <= self.__available_hours[1][index])
                index += 1
        for i in range(self.__months - 1):
            objective_function_temp += sum(self.__month_variables[i]) * (i + 1) * self.__cost_to_hold_inventory
        self.__objective_function += objective_function_temp
        for constraint in constraints:
            self.__objective_function += constraint
        index = 0
        for demand_constraint in self.__demand_constraints:
            self.__objective_function += sum(demand_constraint) == self.__total_demand_by_month[index]
            index += 1

    def solve_linear_prog_problem(self) -> Tuple[list, list]:
        """
        Create and solve a linear programming problem.

        Returns:
            (list, list): demand results, time assignation results.
        """
        self.__create_objective_function()
        status = self.__objective_function.solve(PULP_CBC_CMD(msg=False))
        logger.info('Problem status: %s', LpStatus[status])
        logger.info('Optimal cost: %d', value(self.__objective_function.objective))
        index = 0
        normal_constraints_values = []
        extra_constraints_values = []

        for i, constraint in enumerate(self.__objective_function.constraints):
            constraint_value = self.__objective_function.constraints[constraint].value() - \
                               self.__objective_function.constraints[constraint].constant
            if index < (self.__months * 2):
                if i % 2 == 0:
                    normal_constraints_values.append(constraint_value)
                else:
                    extra_constraints_values.append(constraint_value)
            else:
                break
            index += 1
        logger.info('Normal time constraints values: %s', normal_constraints_values)
        logger.info('Extra time constraints values: %s', extra_constraints_values)

        normal_demand_variables = []
        extra_demand_variables = []

        for demand_constraint in self.__demand_constraints:
            normal_demand_value = 0
            extra_demand_value = 0
            for variable in demand_constraint:
                if self.__kind_of_times[0] in variable.name:
                    normal_demand_value += value(variable)
                else:
                    extra_demand_value += value(variable)
            normal_demand_variables.append(normal_demand_value)
            extra_demand_variables.append(extra_demand_value)
        logger.info('Normal time demand constraints values: %s', normal_demand_variables)
        logger.info('Extra time demand constraints values: %s', extra_demand_variables)
        return [normal_demand_variables, extra_demand_variables], [normal_constraints_values, extra_constraints_values]

    @staticmethod
    def export_time_assignation(shoes_class: str, time_assignation: list, months: int, results_path: str) -> None:
        """
        Export time assignation results by shoes class to csv format.

        Parameters:
            shoes_class (str): Shoes class name
            time_assignation (list): Array with time assignation results by kind of time.
            months (int): forecasting months.
            results_path (str): path to save results.
        """
        columns = ['kind_of_time'] + [f'month_{str(i+1)}' for i in range(months)]
        dataframe = pd.DataFrame(columns=columns)
        index = 0
        kind_of_times = ['Normal time', 'Extra time']
        for kind_of_time in kind_of_times:
            row_data = {'kind_of_time': kind_of_time}
            time_as = time_assignation[index]
            for month in range(months):
                row_data[f'month_{str(month+1)}'] = int(time_as[month])
            dataframe = pd.concat([dataframe, pd.DataFrame(data=[row_data])], ignore_index=True)
        excel_writer = results_path.format(shoes_class=shoes_class.lower())
        with pd.ExcelWriter(excel_writer, mode='a') as writer:
            dataframe.to_excel(writer, sheet_name='time_assignation')
