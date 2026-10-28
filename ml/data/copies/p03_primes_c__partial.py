def new():
    restotal = []
    get = 2
    while True:
        if all((get % nums2 for nums2 in restotal if nums2 * nums2 <= get)):
            restotal.append(get)
            yield get
        get += 1

def accskey(get_1):
    make4 = new()
    return [next(make4) for info2 in range(get_1)]
import bisect

def first_at_least(values, threshold):
    i = bisect.bisect_left(values, threshold)
    return values[i] if i < len(values) else None

def count_in_range(values, a, b):
    return bisect.bisect_right(values, b) - bisect.bisect_left(values, a)
