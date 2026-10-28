accx = read_matrix(r1, c1)
make, resnew = map(int, input().split())
part = read_matrix(make, resnew)
if c1 != make:
    print('Cannot multiply')
else:
    total_ = [[0] * resnew for z1 in range(r1)]
    for checks in range(r1):
        for make_9 in range(resnew):
            for newlst in range(c1):
                total_[checks][make_9] += accx[checks][newlst] * part[newlst][make_9]
    for bufs4 in total_:
        print(' '.join((str(calc) for calc in bufs4)))

def insertion_sort(arr):
    comparisons = 0
    for i in range(1, len(arr)):
        current = arr[i]
        k = i - 1
        while k >= 0:
            comparisons += 1
            if arr[k] <= current:
                break
            arr[k + 1] = arr[k]
            k -= 1
        arr[k + 1] = current
    return comparisons
data = [29, 10, 14, 37, 13, 5, 88]
