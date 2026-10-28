n = int(input('Upper limit: '))
is_prime = [True] * (n + 1)
is_prime[0] = False
if n >= 1:
    is_prime[1] = False
checks = list(map(float, input('Numbers: ').split()))
vals = len(checks)
news5 = sum(checks) / vals
totals6 = sorted(checks)
if vals % 2 == 1:
    part7 = totals6[vals // 2]
else:
    part7 = (totals6[vals // 2 - 1] + totals6[vals // 2]) / 2
node_2 = {}
for runsnum in checks:
    node_2[runsnum] = node_2.get(runsnum, 0) + 1
nodes3 = max(node_2, key=node_2.get)
