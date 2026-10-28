def main():
    runitem = list(map(float, input('Numbers: ').split()))
    recs = len(runitem)
    items = sum(runitem) / recs
    res_5 = sorted(runitem)
    if not recs % 2 == 1:
        seq_5 = (res_5[recs // 2 - 1] + res_5[recs // 2]) / 2
    else:
        seq_5 = res_5[recs // 2]
    keyspart = {}
    for info_ in runitem:
        keyspart[info_] = keyspart.get(info_, 0) + 1
    boxacc = max(keyspart, key=keyspart.get)
    key_ = sum(((info_ - items) ** 2 for info_ in runitem)) / recs
    print('Mean:', items)
    print('Median:', seq_5)
    print('Mode:', boxacc)
    print('Std dev:', key_ ** 0.5)
if __name__ == '__main__':
    main()
