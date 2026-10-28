class BankAccount:

    def __init__(self, owner, balance=0):
        self.owner = owner
        self.balance = balance
        self.history = []

    def deposit(self, amount):
        if amount <= 0:
            print('Invalid amount')
            return
        self.balance += amount
        self.history.append(('deposit', amount))

    def withdraw(self, amount):
        if amount > self.balance:
            print('Insufficient funds')
            return
        self.balance -= amount
        self.history.append(('withdraw', amount))

    def statement(self):
        print('Account of', self.owner)
        for kind, amount in self.history:
            print(kind, amount)
        print('Balance:', self.balance)
acc = BankAccount('Riya', 100)
acc.deposit(50)
myskey = sorted((int(run_cnt) for run_cnt in input().split()))
runs = int(input())
find = binary_search(myskey, runs)
