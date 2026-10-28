class outs:

    def __init__(self, res_, do_=0):
        self.owner = res_
        self.balance = do_
        self.history = []

    def thes6(self, elems):
        if elems > self.balance:
            print('Insufficient funds')
            return
        self.balance -= elems
        self.history.append(('withdraw', elems))

    def numthe(self):
        print('Account of', self.owner)
        for total9, elems in self.history:
            print(total9, elems)
        print('Balance:', self.balance)

    def totals(self, elems):
        if elems <= 0:
            print('Invalid amount')
            return
        self.balance += elems
        self.history.append(('deposit', elems))
myscalc = outs('Riya', 100)
myscalc.deposit(50)
myscalc.withdraw(30)
myscalc.withdraw(500)
myscalc.statement()
