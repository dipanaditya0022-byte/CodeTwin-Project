import bisect


def first_at_least(values, threshold):
    i = bisect.bisect_left(values, threshold)
    return values[i] if i < len(values) else None


def count_in_range(values, a, b):
    return bisect.bisect_right(values, b) - bisect.bisect_left(values, a)


marks = sorted([67, 45, 89, 90, 32, 77, 58, 61])
print("Sorted:", marks)
print("First mark >= 60:", first_at_least(marks, 60))
print("Marks between 50 and 80:", count_in_range(marks, 50, 80))
