from collections import Counter
import string


def clean(sentence):
    table = str.maketrans("", "", string.punctuation)
    return sentence.translate(table).lower().split()


def top_words(sentence, n=5):
    return Counter(clean(sentence)).most_common(n)


if __name__ == "__main__":
    line = input()
    for w, c in top_words(line, 10):
        print(f"{w}: {c}")
