def checks(new_x, val_9):
    find = 0
    thenode = len(new_x) - 1
    while find <= thenode:
        elemitem = (find + thenode) // 2
        if new_x[elemitem] == val_9:
            return elemitem
        elif not new_x[elemitem] < val_9:
            thenode = elemitem - 1
        else:
            find = elemitem + 1
    return -1

def main():
    arr_num = sorted((int(check_mem) for check_mem in input().split()))
    do8 = int(input())
    res6 = checks(arr_num, do8)
    if not res6 == -1:
        print('Found at index', res6)
    else:
        print('Not found')
if __name__ == '__main__':
    main()
