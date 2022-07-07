import math

import pandas as pd
from pulp import LpVariable, LpBinary, LpProblem, LpStatus, value, PULP_CBC_CMD, COIN_CMD

HIGH_NUMBER = 90000000
T_VARIABLE = LpVariable('T', lowBound=0)
data = pd.read_excel('OrdenesCroydon.xlsx')
#data = pd.read_excel('OrdenesCroydon2.xlsx')
#data = pd.read_excel('Ordenes.xlsx')
time_assignation = pd.read_excel('OrdenesCroydon.xlsx', sheet_name="Tiempo disponible")
#time_assignation = pd.read_excel('OrdenesCroydon2.xlsx', sheet_name="Tiempo disponible")
#time_assignation = pd.read_excel('Ordenes.xlsx', sheet_name="Hoja 2")
# print(data)
ordenes = data.shape[0]
machines = data.shape[1] - 1

order_variables = []
for i in range(ordenes):
    for j in range(machines):
        order_variables.append(LpVariable(f'x_{i+1}_{j+1}', lowBound=0))
# print(order_variables)

sequence_constraints = []
for j in range(machines-1):
    n = j+1
    left_variables = list(filter(lambda x: x.name.split("_")[2] == str(n), order_variables))
    right_variables = list(filter(lambda x: x.name.split("_")[2] == str(n+1), order_variables))
    sequence_constraint = []
    for i in range(len(left_variables)):
        sequence_constraint.append(left_variables[i] + data.iat[i, j+1] <= right_variables[i])
    sequence_constraints.append(sequence_constraint)

interference_constraints = []
binary_variables = []
index = 0
for n in range(machines):
    for i in range(ordenes-1):
        left_variable = next(filter(lambda x: x.name == f'x_{i+1}_{n+1}', order_variables))
        for j in range(i+1, ordenes):
            right_variable = next(filter(lambda x: x.name == f'x_{j+1}_{n+1}', order_variables))
            binary_variable = LpVariable(f'y{index + 1}', lowBound=0, cat=LpBinary)
            left_side = left_variable + data.iat[i, n+1]
            right_size = right_variable + HIGH_NUMBER * binary_variable
            interference_constraints.append(left_side <= right_size)
            left_side = right_variable + data.iat[j, n+1]
            right_size = left_variable + HIGH_NUMBER * (1 - binary_variable)
            interference_constraints.append(left_side <= right_size)
            binary_variables.append(binary_variable)
            index += 1
# print(interference_constraints)
# print(binary_variables)

completion_time_constraints = []
variables = list(filter(lambda x: x.name.split("_")[2] == str(machines), order_variables))
for i in range(len(variables)):
    completion_time_constraints.append(variables[i] + data.iat[i, machines] <= T_VARIABLE)
# print(completion_time_constraints)
print(f"Constraints number: {len(interference_constraints) + len(completion_time_constraints) + len(sequence_constraints)*len(sequence_constraints[0])}")
print("Setting obj funct...")
objective_function = LpProblem('Min_T')
objective_function += T_VARIABLE
for machine_sequence_constraint in sequence_constraints:
    for sequence_constraint in machine_sequence_constraint:
        objective_function += sequence_constraint
for interference_constraint in interference_constraints:
    objective_function += interference_constraint
for completion_time_constraint in completion_time_constraints:
    objective_function += completion_time_constraint

print("Solving problem...")
# print(objective_function)
status = objective_function.solve(PULP_CBC_CMD(timeLimit=7200, msg=True))
#status = objective_function.solve(COIN_CMD(timeLimit=1200, msg=True))

print(LpStatus[status])
print(value(objective_function.objective))

scheduling = []

for order_variable in order_variables:
    if order_variable.name == 'x_1_15' or order_variable.name == 'x_2_15' or order_variable.name == 'x_1_9' or order_variable.name == 'x_2_9':
        print(f"{order_variable.name}: {value(order_variable)}")
    scheduling.append((order_variable.name, value(order_variable)))

scheduling = sorted(scheduling, key=lambda x: x[1])
print(scheduling)
first_scheduling = list(filter(lambda x: x[0].split("_")[2] == str(machines), scheduling))
order = []
for name, value in first_scheduling:
    order.append(data.iat[int(name.split("_")[1])-1, 0])
columns = list()
columns.extend(data.columns.tolist())
for i in range(time_assignation.shape[0]):
    columns.append(f"Dia finalizacion {time_assignation.iat[i, 0]}")
scheduling_dataframe = pd.DataFrame(columns=columns, data={columns[0]: order})
#scheduling_dataframe = pd.DataFrame(columns=columns, data={columns[0]: data.iloc[:, 0]})

for name, time in scheduling:
    name = name.split("_")
    data_row = int(name[1]) - 1
    scheduling_row = scheduling_dataframe.index[scheduling_dataframe.iloc[:, 0] == data.iat[data_row, 0]].tolist()[0]
    #scheduling_row = int(name[1]) - 1
    column = int(name[2])
    #finish_time = time + data.iat[data_row, column]
    finish_time = time
    scheduling_dataframe.iat[scheduling_row, column] = finish_time

    machine_row = time_assignation.loc[time_assignation.iloc[:, 0] == scheduling_dataframe.columns[column]].values[0]
    machine_name = machine_row[0]
    machine_availability = machine_row[1]
    scheduling_dataframe.loc[scheduling_row, [f"Dia finalizacion {machine_name}"]] = math.ceil(finish_time/machine_availability)

print(scheduling_dataframe)
column = columns[machines]
#print(columns[1:machines+1])
#scheduling_dataframe.sort_values(by=columns[1:machines+1], inplace=True)
#scheduling_dataframe.sort_values(by=columns[1:machines+1], inplace=True)
scheduling_dataframe.to_excel('scheduling.xlsx')
by_all = scheduling_dataframe.sort_values(by=columns[1:machines+1])
by_all.to_excel('scheduling_by_all.xlsx')
by_last = scheduling_dataframe.sort_values(by=[column])
by_last.to_excel('scheduling_by_last.xlsx')


