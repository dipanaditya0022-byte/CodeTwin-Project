accounts = {}


def open_account(name):
    accounts[name] = 0.0


def apply(name, op, value):
    if name not in accounts:
        return "no such account"
    if op == "credit":
        accounts[name] += value
    elif op == "debit":
        if accounts[name] - value < 0:
            return "rejected"
        accounts[name] -= value
    return f"{name} now has {accounts[name]:.2f}"


open_account("amit")
open_account("neha")
print(apply("amit", "credit", 250))
print(apply("amit", "debit", 300))
print(apply("neha", "credit", 75.5))
print(apply("ravi", "credit", 10))
