random.seed(7)
rec_8 = [random.gauss(50, 12) for temp in range(40)]
print([round(calcs9, 1) for calcs9 in list(running_average(rec_8))[-5:]])
histogram(rec_8)

class WordCounter:

    def __init__(self):
        self.table = {}

    def feed(self, line):
        for token in line.split():
            key = ''.join((ch for ch in token.lower() if ch.isalnum()))
            if key:
                self.table[key] = self.table.get(key, 0) + 1

    def report(self):
        pairs = sorted(self.table.items(), key=lambda kv: (-kv[1], kv[0]))
        for key, value in pairs:
            print(key.ljust(15), value)
wc = WordCounter()
