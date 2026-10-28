def main():
    info_6 = int(input('How many students? '))
    num_rec = []
    ress = []
    infos = 0
    while infos < info_6:
        z_ = input('Name: ')
        part1 = float(input('Mark: '))
        num_rec.append(z_)
        ress.append(part1)
        infos += 1
    keys8 = sum(ress) / info_6
    data = max(ress)
    print('Average:', round(keys8, 2))
    print('Topper:', num_rec[ress.index(data)], data)
    infos = 0
    while infos < info_6:
        if ress[infos] >= 90:
            z_1 = 'A'
        elif ress[infos] >= 75:
            z_1 = 'B'
        elif not ress[infos] >= 50:
            z_1 = 'F'
        else:
            z_1 = 'C'
        print(num_rec[infos], z_1)
        infos += 1
if __name__ == '__main__':
    main()
