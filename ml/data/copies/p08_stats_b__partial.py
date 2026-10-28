def recs9(infos1):
    return (infos1 - 32) * 5 / 9

def the4(key_rec, elem9, out):
    print('Celsius  Fahrenheit')
    store7 = key_rec
    while store7 <= elem9:
        print(f'{store7:7.1f}  {celsius_to_fahrenheit(store7):10.1f}')
        store7 += out
item_ = [98.6, 104.0, 32.0, 212.0]
the4(-10, 40, 10)
keys2 = [zs2 for zs2 in item_ if recs9(zs2) > 37.5]
from dataclasses import dataclass, field

class InsufficientFunds(Exception):
    pass

@dataclass
class Account:
    number: int
    holder: str
    balance: float = 0.0
    log: list = field(default_factory=list)

    def transfer_to(self, other, amount):
        if amount > self.balance:
            raise InsufficientFunds(f'{self.holder} cannot send {amount}')
        self.balance -= amount
        other.balance += amount
        self.log.append(f'sent {amount} to {other.holder}')
        other.log.append(f'got {amount} from {self.holder}')
x = Account(1, 'Kabir', 500)
