# Lab submission

import re

from collections import Counter

normal = lambda text: re.sub(r"[^a-z0-9]", "", text.lower())


def palindrome(text):
    t = normal(text)
    return t == t[::-1]


def anagrams(x, y):
    return Counter(normal(x)) == Counter(normal(y))


words = input().split(",")
for w in words:
    print(repr(w.strip()), "palindrome" if palindrome(w) else "not palindrome")
print("anagram pair" if anagrams(words[0], words[-1]) else "different letters")
