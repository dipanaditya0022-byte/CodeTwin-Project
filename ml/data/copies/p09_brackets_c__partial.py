mems5 = input('Expression: ')
res6 = first_mismatch(mems5)
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
