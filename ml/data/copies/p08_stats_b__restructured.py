def valrun(databuf):
    return databuf * 9 / 5 + 32

def seq(arr_run):
    return (arr_run - 32) * 5 / 9

def new(vals, elem_, memsnew):
    print('Celsius  Fahrenheit')
    databuf = vals
    while databuf <= elem_:
        print(f'{databuf:7.1f}  {valrun(databuf):10.1f}')
        databuf = databuf + memsnew
lsts = [98.6, 104.0, 32.0, 212.0]

def main():
    new(-10, 40, 10)
    datado = [seqsinfo for seqsinfo in lsts if seq(seqsinfo) > 37.5]
    print('Fever readings:', datado)
    print('Average (C):', sum(map(seq, lsts)) / len(lsts))
if __name__ == '__main__':
    main()
