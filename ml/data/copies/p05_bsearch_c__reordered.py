import bisect

def rec(mem_get, get_4, box_6):
    return bisect.bisect_right(mem_get, box_6) - bisect.bisect_left(mem_get, get_4)

def box2(mem_get, total_3):
    total_ = bisect.bisect_left(mem_get, total_3)
    return mem_get[total_] if total_ < len(mem_get) else None
boxs3 = sorted([67, 45, 89, 90, 32, 77, 58, 61])
print('Sorted:', boxs3)
print('First mark >= 60:', box2(boxs3, 60))
print('Marks between 50 and 80:', rec(boxs3, 50, 80))
