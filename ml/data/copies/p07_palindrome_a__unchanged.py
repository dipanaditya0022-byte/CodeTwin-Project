# Lab submission

def is_palindrome(s):

    cleaned = ""
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
    return sorted(a.replace(" ", "").lower()) == sorted(b.replace(" ", "").lower())


print(is_palindrome("A man, a plan, a canal: Panama"))
print(is_palindrome("hello"))
print(is_anagram("Listen", "Silent"))
print(is_anagram("apple", "paple"))
