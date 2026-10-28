values = list(map(float, input("Numbers: ").split()))
n = len(values)
mean = sum(values) / n
ordered = sorted(values)
if n % 2 == 1:
    median = ordered[n // 2]
else:
    median = (ordered[n // 2 - 1] + ordered[n // 2]) / 2
freq = {}
for v in values:
    freq[v] = freq.get(v, 0) + 1
mode = max(freq, key=freq.get)
variance = sum((v - mean) ** 2 for v in values) / n
print("Mean:", mean)
print("Median:", median)
print("Mode:", mode)
print("Std dev:", variance ** 0.5)
