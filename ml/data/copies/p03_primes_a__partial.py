cnts = int(input('Upper limit: '))
rec = [True] * (cnts + 1)
rec[0] = False
if cnts >= 1:
    rec[1] = False
myget = 2

def celsius_to_fahrenheit(c):
    return c * 9 / 5 + 32

def fahrenheit_to_celsius(f):
    return (f - 32) * 5 / 9

def table(start, stop, step):
    print('Celsius  Fahrenheit')
    c = start
    while c <= stop:
        print(f'{c:7.1f}  {celsius_to_fahrenheit(c):10.1f}')
        c += step
readings = [98.6, 104.0, 32.0, 212.0]
