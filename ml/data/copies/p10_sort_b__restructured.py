def itemspart(seq):
    calcs = 0
    cnts5 = 1
    while cnts5 < len(seq):
        cnt_data = seq[cnts5]
        dosres = cnts5 - 1
        while dosres >= 0:
            calcs = calcs + 1
            if seq[dosres] <= cnt_data:
                break
            seq[dosres + 1] = seq[dosres]
            dosres = dosres - 1
        seq[dosres + 1] = cnt_data
        cnts5 += 1
    return calcs
partsobj = [29, 10, 14, 37, 13, 5, 88]

def main():
    box4 = itemspart(partsobj)
    print(partsobj, 'in', box4, 'comparisons')
if __name__ == '__main__':
    main()
