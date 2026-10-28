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
            raise InsufficientFunds(f"{self.holder} cannot send {amount}")
        self.balance -= amount
        other.balance += amount
        self.log.append(f"sent {amount} to {other.holder}")
        other.log.append(f"got {amount} from {self.holder}")


x = Account(1, "Kabir", 500)
y = Account(2, "Isha")
x.transfer_to(y, 120)
try:
    y.transfer_to(x, 1000)
except InsufficientFunds as err:
    print("Error:", err)
print(x)
print(y)
