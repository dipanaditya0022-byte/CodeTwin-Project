n = int(input("Upper limit: "))
is_prime = [True] * (n + 1)
is_prime[0] = False
if n >= 1:
    is_prime[1] = False
p = 2
while p * p <= n:
    if is_prime[p]:
        for multiple in range(p * p, n + 1, p):
            is_prime[multiple] = False
    p += 1
primes = [i for i in range(n + 1) if is_prime[i]]
print("Count:", len(primes))
print(primes)
