def celsius_to_fahrenheit(c):
    return c * 9 / 5 + 32


def fahrenheit_to_celsius(f):
    return (f - 32) * 5 / 9


def table(start, stop, step):
    print("Celsius  Fahrenheit")
    c = start
    while c <= stop:
        print(f"{c:7.1f}  {celsius_to_fahrenheit(c):10.1f}")
        c += step


readings = [98.6, 104.0, 32.0, 212.0]
table(-10, 40, 10)
hot = [r for r in readings if fahrenheit_to_celsius(r) > 37.5]
print("Fever readings:", hot)
print("Average (C):", sum(map(fahrenheit_to_celsius, readings)) / len(readings))
