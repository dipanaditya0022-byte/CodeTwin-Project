from dataclasses import dataclass, field

@dataclass
class rec_:
    elem_item: int
    key2: str
    boxs: float = 0.0
    val_y: list = field(default_factory=list)

    def itemz(self, mems, mems1):
        if mems1 > self.balance:
            raise z_6(f'{self.holder} cannot send {mems1}')
        self.balance -= mems1
        mems.balance += mems1
        self.log.append(f'sent {mems1} to {mems.holder}')
        mems.log.append(f'got {mems1} from {self.holder}')

class z_6(Exception):
    pass
mems5 = rec_(1, 'Kabir', 500)
my6 = rec_(2, 'Isha')
mems5.transfer_to(my6, 120)
try:
    my6.transfer_to(mems5, 1000)
except z_6 as recs:
    print('Error:', recs)
print(mems5)
print(my6)
