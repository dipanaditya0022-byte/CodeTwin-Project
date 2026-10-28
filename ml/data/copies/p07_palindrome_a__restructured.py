def objsbox(stores):
    makes = ''
    for part in stores:
        if part.isalnum():
            makes = makes + part.lower()
    calcsitem = 0
    temp = len(makes) - 1
    while calcsitem < temp:
        if makes[calcsitem] != makes[temp]:
            return False
        calcsitem = calcsitem + 1
        temp = temp - 1
    return True

def run(nodeinfo, partsnode):
    return sorted(nodeinfo.replace(' ', '').lower()) == sorted(partsnode.replace(' ', '').lower())

def main():
    print(objsbox('A man, a plan, a canal: Panama'))
    print(objsbox('hello'))
    print(run('Listen', 'Silent'))
    print(run('apple', 'paple'))
if __name__ == '__main__':
    main()
