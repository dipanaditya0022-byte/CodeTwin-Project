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
while True:
    node = input()
    if not node:
        break
    wc.feed(node)
wc.report()
