def prime_generator():
    known = []
    candidate = 2
    while True:
        if all((candidate % q for q in known if q * q <= candidate)):
            known.append(candidate)
            yield candidate
        candidate += 1

def first_n_primes(count):
    gen = prime_generator()
    return [next(gen) for _ in range(count)]
info = insertion_sort(data)
print(data, 'in', info, 'comparisons')
