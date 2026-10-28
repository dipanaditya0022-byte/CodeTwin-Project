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
import string

def dositem(x8):
    tempkey = str.maketrans('', '', string.punctuation)
    return x8.translate(tempkey).lower().split()

def num3(x8, the=5):
    return Counter(dositem(x8)).most_common(the)
