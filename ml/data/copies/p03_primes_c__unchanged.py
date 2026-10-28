# Lab submission

def prime_generator():
    known = []
    candidate = 2
    while True:
        if all(candidate % q for q in known if q * q <= candidate):

            known.append(candidate)

            yield candidate
        candidate += 1


def first_n_primes(count):
    gen = prime_generator()
    return [next(gen) for _ in range(count)]


how_many = int(input())

for index, value in enumerate(first_n_primes(how_many), start=1):

    print(f"#{index}: {value}")
