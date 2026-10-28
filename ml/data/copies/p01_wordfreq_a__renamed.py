recdata = input('Enter a sentence: ')
get = {}
for checks6 in recdata.lower().split():
    checks6 = checks6.strip('.,!?;:')
    if checks6 == '':
        continue
    if checks6 in get:
        get[checks6] = get[checks6] + 1
    else:
        get[checks6] = 1
for checks6 in sorted(get):
    print(checks6, get[checks6])
