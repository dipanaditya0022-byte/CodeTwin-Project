# Lab submission

import random


def running_average(stream):
    total = 0.0
    for count, value in enumerate(stream, start=1):

        total += value
        yield total / count


def histogram(values, buckets=5):
    lo, hi = min(values), max(values)

    width = (hi - lo) / buckets or 1

    bins = [0] * buckets
    for v in values:
        idx = min(int((v - lo) / width), buckets - 1)
        bins[idx] += 1
    for i, b in enumerate(bins):
        print(f"{lo + i * width:6.1f} | " + "*" * b)



random.seed(7)
sample = [random.gauss(50, 12) for _ in range(40)]
print([round(x, 1) for x in list(running_average(sample))[-5:]])
histogram(sample)
