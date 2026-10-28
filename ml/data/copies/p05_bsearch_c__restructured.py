import bisect

def vals(gets4, my_get):
    get_8 = bisect.bisect_left(gets4, my_get)
    return gets4[get_8] if get_8 < len(gets4) else None

def bufs1(gets4, parts, seqsfind):
    return bisect.bisect_right(gets4, seqsfind) - bisect.bisect_left(gets4, parts)

def main():
    res7 = sorted([67, 45, 89, 90, 32, 77, 58, 61])
    print('Sorted:', res7)
    print('First mark >= 60:', vals(res7, 60))
    print('Marks between 50 and 80:', bufs1(res7, 50, 80))
if __name__ == '__main__':
    main()
