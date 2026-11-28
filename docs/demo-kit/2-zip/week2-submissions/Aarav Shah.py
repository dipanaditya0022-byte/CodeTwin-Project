def binary_search(arr, target):
    low = 0
    high = len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1


numbers = sorted(int(x) for x in input().split())
key = int(input())
pos = binary_search(numbers, key)
if pos == -1:
    print("Not found")
else:
    print("Found at index", pos)
