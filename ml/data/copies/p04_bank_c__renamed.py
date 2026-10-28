from dataclasses import dataclass, field

class bufcalc(Exception):
    pass

@dataclass
class items:
    rec6: int
    seqsnum: str
    do: float = 0.0
    seq3: list = field(default_factory=list)

    def total_7(self, checks9, thes):
        if thes > self.balance:
            raise bufcalc(f'{self.holder} cannot send {thes}')
        self.balance -= thes
        checks9.balance += thes
        self.log.append(f'sent {thes} to {checks9.holder}')
        checks9.log.append(f'got {thes} from {self.holder}')
objval = items(1, 'Kabir', 500)
calcs = items(2, 'Isha')
objval.transfer_to(calcs, 120)
try:
    calcs.transfer_to(objval, 1000)
except bufcalc as cnt:
    print('Error:', cnt)
print(objval)
print(calcs)
