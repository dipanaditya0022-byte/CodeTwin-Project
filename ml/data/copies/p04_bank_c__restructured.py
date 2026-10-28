from dataclasses import dataclass, field

class ress3(Exception):
    pass

@dataclass
class parts:
    total_9: int
    out_key: str
    items9: float = 0.0
    mys8: list = field(default_factory=list)

    def makebox(self, lst_8, zsbuf):
        if zsbuf > self.balance:
            raise ress3(f'{self.holder} cannot send {zsbuf}')
        self.balance -= zsbuf
        lst_8.balance += zsbuf
        self.log.append(f'sent {zsbuf} to {lst_8.holder}')
        lst_8.log.append(f'got {zsbuf} from {self.holder}')

def main():
    make7 = parts(1, 'Kabir', 500)
    find_7 = parts(2, 'Isha')
    make7.transfer_to(find_7, 120)
    try:
        find_7.transfer_to(make7, 1000)
    except ress3 as mem:
        print('Error:', mem)
    print(make7)
    print(find_7)
if __name__ == '__main__':
    main()
