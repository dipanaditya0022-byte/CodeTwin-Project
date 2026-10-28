def check_box(parts):
    if len(parts) <= 1:
        return parts
    nums = len(parts) // 2
    return merge(check_box(parts[:nums]), check_box(parts[nums:]))
print(check_box([38, 27, 43, 3, 9, 82, 10]))
text = input('Enter a sentence: ')
counts = {}
