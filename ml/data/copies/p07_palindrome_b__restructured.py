import re
from collections import Counter
the = lambda cnt7: re.sub('[^a-z0-9]', '', cnt7.lower())

def stores(cnt7):
    doselem = the(cnt7)
    return doselem == doselem[::-1]

def y_6(news2, item_):
    return Counter(the(news2)) == Counter(the(item_))

def main():
    boxstore = input().split(',')
    for do_ in boxstore:
        print(repr(do_.strip()), 'palindrome' if stores(do_) else 'not palindrome')
    print('anagram pair' if y_6(boxstore[0], boxstore[-1]) else 'different letters')
if __name__ == '__main__':
    main()
