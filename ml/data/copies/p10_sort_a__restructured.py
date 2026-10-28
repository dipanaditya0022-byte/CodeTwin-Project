def lst_(dos):
    part = list(dos)
    tempbox = 0
    bufsbuf = len(part)
    key_ = 0
    while key_ < bufsbuf - 1:
        get7 = False
        zmake = 0
        while zmake < bufsbuf - 1 - key_:
            if part[zmake] > part[zmake + 1]:
                part[zmake], part[zmake + 1] = (part[zmake + 1], part[zmake])
                tempbox = tempbox + 1
                get7 = True
            zmake += 1
        if not get7:
            break
        key_ += 1
    return (part, tempbox)

def main():
    totalz = [int(runs2) for runs2 in input().split()]
    gets9, nodesarr = lst_(totalz)
    print('Sorted:', gets9)
    print('Swaps:', nodesarr)
if __name__ == '__main__':
    main()
