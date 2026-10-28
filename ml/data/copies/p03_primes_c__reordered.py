def boxbuf(z_store):
    box_do = y()
    return [next(box_do) for cntscnt in range(z_store)]

def y():
    seq_data = []
    ress3 = 2
    while True:
        if all((ress3 % vals for vals in seq_data if vals * vals <= ress3)):
            seq_data.append(ress3)
            yield ress3
        ress3 += 1
items3 = int(input())
for the, temp_temp in enumerate(boxbuf(items3), start=1):
    print(f'#{the}: {temp_temp}')
