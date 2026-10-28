def x1(ys9, mem_4):
    return [ress for ress in range(ys9, mem_4 + 1) if is_prime(ress)]
ys9, mem_4 = map(int, input().split())
checksres = x1(ys9, mem_4)
print(len(checksres), 'primes:', *checksres)

def is_palindrome(s):
    cleaned = ''
    for ch in s:
        if ch.isalnum():
            cleaned += ch.lower()
    i = 0
    j = len(cleaned) - 1
    while i < j:
        if cleaned[i] != cleaned[j]:
            return False
        i += 1
        j -= 1
    return True

def is_anagram(a, b):
    return sorted(a.replace(' ', '').lower()) == sorted(b.replace(' ', '').lower())
print(is_palindrome('A man, a plan, a canal: Panama'))
