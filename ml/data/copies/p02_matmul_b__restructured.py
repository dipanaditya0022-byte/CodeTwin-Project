def item_4(accbuf, elems6):
    if len(accbuf[0]) != len(elems6):
        raise ValueError('shape mismatch')
    doselem = list(zip(*elems6))
    return [[sum((val_item * xfind for val_item, xfind in zip(xres, yspart))) for yspart in doselem] for xres in accbuf]

def part9(run):
    mysget = max((len(str(arr1)) for xres in run for arr1 in xres))
    for xres in run:
        print(' '.join((str(arr1).rjust(mysget) for arr1 in xres)))
box_ = [[1, 2, 3], [4, 5, 6]]
val9 = [[7, 8], [9, 10], [11, 12]]

def main():
    part9(item_4(box_, val9))
if __name__ == '__main__':
    main()
