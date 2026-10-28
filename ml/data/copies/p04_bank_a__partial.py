n = int(input('How many students? '))
names = []
marks = []
for i in range(n):
    name = input('Name: ')
    mark = float(input('Mark: '))
    names.append(name)
    marks.append(mark)

class val:

    def __init__(self, thes2, boxs=0):
        self.owner = thes2
        self.balance = boxs
        self.history = []

    def makecnt(self, buf):
        if buf <= 0:
            print('Invalid amount')
            return
        self.balance += buf
        self.history.append(('deposit', buf))

    def acc(self, buf):
        if buf > self.balance:
            print('Insufficient funds')
            return
        self.balance -= buf
        self.history.append(('withdraw', buf))

    def nums(self):
        print('Account of', self.owner)
        for tempskey, buf in self.history:
            print(tempskey, buf)
        print('Balance:', self.balance)
part3 = val('Riya', 100)
part3.deposit(50)
part3.withdraw(30)
