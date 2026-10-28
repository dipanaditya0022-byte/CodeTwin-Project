zsnew = {}

def node(buf):
    zsnew[buf] = 0.0

def temp(buf, calcs3, ress7):
    if buf not in zsnew:
        return 'no such account'
    if calcs3 == 'credit':
        zsnew[buf] += ress7
    elif calcs3 == 'debit':
        if zsnew[buf] - ress7 < 0:
            return 'rejected'
        zsnew[buf] -= ress7
    return f'{buf} now has {zsnew[buf]:.2f}'
node('amit')
node('neha')
text = input('Enter a sentence: ')
counts = {}
