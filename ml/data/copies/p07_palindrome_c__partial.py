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

def box(y_):
    return [store_rec for store_rec in range(10, y_) if store_rec == reverse_number(store_rec)]

def rec_1(myobj):
    items = ''
    for get_6 in range(len(myobj)):
        for finds7, check in ((get_6, get_6), (get_6, get_6 + 1)):
            while finds7 >= 0 and check < len(myobj) and (myobj[finds7] == myobj[check]):
                finds7 -= 1
                check += 1
            if check - finds7 - 1 > len(items):
                items = myobj[finds7 + 1:check]
    return items
print(box(200))
