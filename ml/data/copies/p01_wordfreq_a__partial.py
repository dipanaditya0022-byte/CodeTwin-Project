for check_9 in text.lower().split():
    check_9 = check_9.strip('.,!?;:')
    if check_9 == '':
        continue
    if check_9 in counts:
        counts[check_9] = counts[check_9] + 1
    else:
        counts[check_9] = 1
for check_9 in sorted(counts):
    print(check_9, counts[check_9])

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
