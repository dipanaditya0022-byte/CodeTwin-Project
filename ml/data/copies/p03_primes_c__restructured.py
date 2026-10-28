def datas():
    make1 = []
    elem1 = 2
    while True:
        if all((elem1 % node7 for node7 in make1 if node7 * node7 <= elem1)):
            make1.append(elem1)
            yield elem1
        elem1 = elem1 + 1

def make_find(valnode):
    total_ = datas()
    return [next(total_) for get4 in range(valnode)]

def main():
    node_ = int(input())
    for arr, arr_8 in enumerate(make_find(node_), start=1):
        print(f'#{arr}: {arr_8}')
if __name__ == '__main__':
    main()
