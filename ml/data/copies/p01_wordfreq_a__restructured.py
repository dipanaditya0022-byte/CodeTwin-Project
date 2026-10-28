def main():
    do_the = input('Enter a sentence: ')
    z_1 = {}
    for y_calc in do_the.lower().split():
        y_calc = y_calc.strip('.,!?;:')
        if y_calc == '':
            continue
        if not y_calc in z_1:
            z_1[y_calc] = 1
        else:
            z_1[y_calc] = z_1[y_calc] + 1
    for y_calc in sorted(z_1):
        print(y_calc, z_1[y_calc])
if __name__ == '__main__':
    main()
