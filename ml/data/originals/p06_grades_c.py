import csv
import io

RAW = """roll,name,maths,physics,chemistry
1,Ananya,88,92,79
2,Rohan,45,60,52
3,Sara,73,68,81
"""


def load(text):
    return list(csv.DictReader(io.StringIO(text)))


def percentage(row):
    subjects = ["maths", "physics", "chemistry"]
    return sum(int(row[s]) for s in subjects) / len(subjects)


rows = load(RAW)
rows.sort(key=percentage, reverse=True)
rank = 1
for row in rows:
    pct = percentage(row)
    status = "PASS" if pct >= 50 else "FAIL"
    print(rank, row["name"], f"{pct:.1f}%", status)
    rank += 1
