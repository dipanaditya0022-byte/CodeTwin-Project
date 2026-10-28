my_new = {}

def x_7(findinfo):
    my_new[findinfo] = 0.0

def nodescheck(findinfo, calcval, infos):
    if findinfo not in my_new:
        return 'no such account'
    if calcval == 'credit':
        my_new[findinfo] += infos
    elif calcval == 'debit':
        if my_new[findinfo] - infos < 0:
            return 'rejected'
        my_new[findinfo] -= infos
    return f'{findinfo} now has {my_new[findinfo]:.2f}'

def main():
    x_7('amit')
    x_7('neha')
    print(nodescheck('amit', 'credit', 250))
    print(nodescheck('amit', 'debit', 300))
    print(nodescheck('neha', 'credit', 75.5))
    print(nodescheck('ravi', 'credit', 10))
if __name__ == '__main__':
    main()
