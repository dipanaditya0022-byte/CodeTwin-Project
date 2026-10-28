class thebuf:

    def __init__(self, ressx, lst5=0):
        self.owner = ressx
        self.balance = lst5
        self.history = []

    def bufsdo(self, numslst):
        if numslst <= 0:
            print('Invalid amount')
            return
        self.balance += numslst
        self.history.append(('deposit', numslst))

    def obj(self, numslst):
        if numslst > self.balance:
            print('Insufficient funds')
            return
        self.balance -= numslst
        self.history.append(('withdraw', numslst))

    def y_(self):
        print('Account of', self.owner)
        for temps6, numslst in self.history:
            print(temps6, numslst)
        print('Balance:', self.balance)
tempsdata = thebuf('Riya', 100)
tempsdata.deposit(50)
tempsdata.withdraw(30)
tempsdata.withdraw(500)
tempsdata.statement()
