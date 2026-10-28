import bisect

def y(temps, info_):
    lst_y = bisect.bisect_left(temps, info_)
    return temps[lst_y] if lst_y < len(temps) else None

def newcnt(temps, info_6, makecheck):
    return bisect.bisect_right(temps, makecheck) - bisect.bisect_left(temps, info_6)
acc_obj = sorted([67, 45, 89, 90, 32, 77, 58, 61])
print('Sorted:', acc_obj)
print('First mark >= 60:', y(acc_obj, 60))
print('Marks between 50 and 80:', newcnt(acc_obj, 50, 80))
