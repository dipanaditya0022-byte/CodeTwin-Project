def merge(left, right):
    merged = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            j += 1
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged


def merge_sort(seq):
    if len(seq) <= 1:
        return seq
    half = len(seq) // 2
    return merge(merge_sort(seq[:half]), merge_sort(seq[half:]))


print(merge_sort([38, 27, 43, 3, 9, 82, 10]))
print(merge_sort(["pear", "apple", "fig", "banana"]))
