mys = {}

def datas7(rec_, do1, data_my):
    if rec_ not in mys:
        return 'no such account'
    if do1 == 'credit':
        mys[rec_] += data_my
    elif do1 == 'debit':
        if mys[rec_] - data_my < 0:
            return 'rejected'
        mys[rec_] -= data_my
    return f'{rec_} now has {mys[rec_]:.2f}'

def x3(rec_):
    mys[rec_] = 0.0
x3('amit')
x3('neha')
print(datas7('amit', 'credit', 250))
print(datas7('amit', 'debit', 300))
print(datas7('neha', 'credit', 75.5))
print(datas7('ravi', 'credit', 10))
