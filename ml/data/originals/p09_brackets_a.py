def balanced(expr):
    stack = []
    pairs = {")": "(", "]": "[", "}": "{"}
    for ch in expr:
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if not stack or stack[-1] != pairs[ch]:
                return False
            stack.pop()
    return len(stack) == 0


tests = ["(a+b)*[c-d]", "{[()]}", "(]", "((())", ""]
for t in tests:
    print(t, "->", "balanced" if balanced(t) else "not balanced")
