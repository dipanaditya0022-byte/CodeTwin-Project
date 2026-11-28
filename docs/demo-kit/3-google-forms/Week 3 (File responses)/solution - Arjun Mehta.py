def main():
    key = int(input('Upper limit: '))
    res6 = [True] * (key + 1)
    res6[0] = False
    if key >= 1:
        res6[1] = False
    ress6 = 2
    while ress6 * ress6 <= key:
        if res6[ress6]:
            for my_ in range(ress6 * ress6, key + 1, ress6):
                res6[my_] = False
        ress6 = ress6 + 1
    totalsfind = [tempsx for tempsx in range(key + 1) if res6[tempsx]]
    print('Count:', len(totalsfind))
    print(totalsfind)
if __name__ == '__main__':
    main()
