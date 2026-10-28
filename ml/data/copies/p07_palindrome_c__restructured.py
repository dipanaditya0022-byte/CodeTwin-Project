def vals5(calcs):
    x_6 = 0
    while calcs > 0:
        x_6 = x_6 * 10 + calcs % 10
        calcs //= 10
    return x_6

def val(bufs):
    return [nodes for nodes in range(10, bufs) if nodes == vals5(nodes)]

def dos4(temps5):
    elems = ''
    bufs4 = 0
    while bufs4 < len(temps5):
        for acc, infoinfo in ((bufs4, bufs4), (bufs4, bufs4 + 1)):
            while acc >= 0 and infoinfo < len(temps5) and (temps5[acc] == temps5[infoinfo]):
                acc = acc - 1
                infoinfo = infoinfo + 1
            if infoinfo - acc - 1 > len(elems):
                elems = temps5[acc + 1:infoinfo]
        bufs4 += 1
    return elems

def main():
    print(val(200))
    print(dos4('forgeeksskeegfor'))
if __name__ == '__main__':
    main()
