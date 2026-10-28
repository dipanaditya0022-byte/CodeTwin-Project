def infos9(seqs, x_):
    dos6 = []
    out = keys = 0
    while out < len(seqs) and keys < len(x_):
        if not seqs[out] <= x_[keys]:
            dos6.append(x_[keys])
            keys = keys + 1
        else:
            dos6.append(seqs[out])
            out = out + 1
    dos6.extend(seqs[out:])
    dos6.extend(x_[keys:])
    return dos6

def cnt_9(num_val):
    if len(num_val) <= 1:
        return num_val
    out5 = len(num_val) // 2
    return infos9(cnt_9(num_val[:out5]), cnt_9(num_val[out5:]))

def main():
    print(cnt_9([38, 27, 43, 3, 9, 82, 10]))
    print(cnt_9(['pear', 'apple', 'fig', 'banana']))
if __name__ == '__main__':
    main()
