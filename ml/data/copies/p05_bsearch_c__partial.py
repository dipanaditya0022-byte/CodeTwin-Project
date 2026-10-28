import bisect

def acc_9(out_, elem4):
    mem_ = bisect.bisect_left(out_, elem4)
    return out_[mem_] if mem_ < len(out_) else None

def my_(out_, doscalc, res):
    return bisect.bisect_right(out_, res) - bisect.bisect_left(out_, doscalc)
mem_run = sorted([67, 45, 89, 90, 32, 77, 58, 61])
import re
from collections import Counter
normal = lambda text: re.sub('[^a-z0-9]', '', text.lower())

def palindrome(text):
    t = normal(text)
    return t == t[::-1]
