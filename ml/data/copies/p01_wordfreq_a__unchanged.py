# Lab submission

text = input("Enter a sentence: ")
counts = {}
for word in text.lower().split():
    word = word.strip(".,!?;:")
    if word == "":
        continue
    if word in counts:
        counts[word] = counts[word] + 1
    else:
        counts[word] = 1
for word in sorted(counts):
    print(word, counts[word])
