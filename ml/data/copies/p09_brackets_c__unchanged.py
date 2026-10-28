# Lab submission

def first_mismatch(code):
    opening, closing = "([{", ")]}"
    seen = []
    for position, symbol in enumerate(code):

        if symbol in opening:
            seen.append((symbol, position))
        elif symbol in closing:
            expected = opening[closing.index(symbol)]
            if not seen:
                return position
            top, _ = seen.pop()
            if top != expected:

                return position
    return seen[0][1] if seen else None


source = input("Expression: ")
where = first_mismatch(source)
if where is None:
    print("All brackets match")
else:
    print(source)
    print(" " * where + "^ problem here")
