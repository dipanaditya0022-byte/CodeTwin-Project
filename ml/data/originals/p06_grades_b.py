import statistics

BANDS = [(90, "A+"), (80, "A"), (70, "B"), (60, "C"), (0, "D")]


def letter(score):
    return next(g for cutoff, g in BANDS if score >= cutoff)


def summarise(records):
    scores = [s for _, s in records]
    return {
        "mean": statistics.mean(scores),
        "median": statistics.median(scores),
        "stdev": statistics.pstdev(scores),
    }


records = [("Aarav", 91), ("Diya", 78), ("Kunal", 64), ("Meera", 85), ("Om", 55)]
for name, score in records:
    print(f"{name:<8}{score:>4} {letter(score)}")
for key, value in summarise(records).items():
    print(key, round(value, 2))
