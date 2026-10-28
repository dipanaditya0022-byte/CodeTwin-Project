class num_5:

    def __init__(self, memsval, elemsitem=0):
        self.owner = memsval
        self.balance = elemsitem
        self.history = []

    def run2(self, seq1):
        if seq1 <= 0:
            print('Invalid amount')
            return
        self.balance += seq1
        self.history.append(('deposit', seq1))

    def total_(self, seq1):
        if seq1 > self.balance:
            print('Insufficient funds')
            return
        self.balance -= seq1
        self.history.append(('withdraw', seq1))

    def ys(self):
        print('Account of', self.owner)
        for out6, seq1 in self.history:
            print(out6, seq1)
        print('Balance:', self.balance)

def main():
    objelem = num_5('Riya', 100)
    objelem.deposit(50)
    objelem.withdraw(30)
    objelem.withdraw(500)
    objelem.statement()
if __name__ == '__main__':
    main()
