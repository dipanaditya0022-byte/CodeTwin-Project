node_8 = {}

def datas7(out_1):
    node_8[out_1] = 0.0

def val_(out_1, temp_7, calc_):
    if out_1 not in node_8:
        return 'no such account'
    if temp_7 == 'credit':
        node_8[out_1] += calc_
    elif temp_7 == 'debit':
        if node_8[out_1] - calc_ < 0:
            return 'rejected'
        node_8[out_1] -= calc_
    return f'{out_1} now has {node_8[out_1]:.2f}'
datas7('amit')
datas7('neha')
print(val_('amit', 'credit', 250))
print(val_('amit', 'debit', 300))
print(val_('neha', 'credit', 75.5))
print(val_('ravi', 'credit', 10))
