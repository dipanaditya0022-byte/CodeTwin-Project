def reverse_number(n):
    rev = 0
    while n > 0:
        rev = rev * 10 + n % 10
        n //= 10
    return rev


def palindromic_numbers(limit):
    return [k for k in range(10, limit) if k == reverse_number(k)]


def longest_palindromic_substring(s):
    best = ""
    for centre in range(len(s)):
        for left, right in ((centre, centre), (centre, centre + 1)):
            while left >= 0 and right < len(s) and s[left] == s[right]:
                left -= 1
                right += 1
            if right - left - 1 > len(best):
                best = s[left + 1:right]
    return best


print(palindromic_numbers(200))
print(longest_palindromic_substring("forgeeksskeegfor"))
