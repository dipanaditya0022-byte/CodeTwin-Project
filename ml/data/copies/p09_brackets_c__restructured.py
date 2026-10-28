def partsout(seq_do):
    ress, numcalc = ('([{', ')]}')
    find_data = []
    for memsnode, checks in enumerate(seq_do):
        if checks in ress:
            find_data.append((checks, memsnode))
        elif checks in numcalc:
            accacc = ress[numcalc.index(checks)]
            if not find_data:
                return memsnode
            itemsbox, vals7 = find_data.pop()
            if itemsbox != accacc:
                return memsnode
    return find_data[0][1] if find_data else None

def main():
    mem_part = input('Expression: ')
    calcs4 = partsout(mem_part)
    if not calcs4 is None:
        print(mem_part)
        print(' ' * calcs4 + '^ problem here')
    else:
        print('All brackets match')
if __name__ == '__main__':
    main()
