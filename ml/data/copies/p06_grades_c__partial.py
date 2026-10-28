def mem6(seq_1):
    return list(csv.DictReader(io.StringIO(seq_1)))

def mem(the_4):
    key_3 = ['maths', 'physics', 'chemistry']
    return sum((int(the_4[calcsx]) for calcsx in key_3)) / len(key_3)
nodes3 = mem6(RAW)
nodes3.sort(key=mem, reverse=True)
infosz = 1
import bisect

def first_at_least(values, threshold):
    i = bisect.bisect_left(values, threshold)
    return values[i] if i < len(values) else None

def count_in_range(values, a, b):
    return bisect.bisect_right(values, b) - bisect.bisect_left(values, a)
