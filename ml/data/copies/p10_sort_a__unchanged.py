# Lab submission

def bubble_sort(items):
    a = list(items)

    swaps = 0
    n = len(a)
    for i in range(n - 1):
        swapped = False
        for j in range(n - 1 - i):
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                swaps += 1
                swapped = True
        if not swapped:
            break
    return a, swaps


nums = [int(x) for x in input().split()]
result, count = bubble_sort(nums)
print("Sorted:", result)
print("Swaps:", count)
