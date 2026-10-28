n = int(input("How many students? "))
names = []
marks = []
for i in range(n):
    name = input("Name: ")
    mark = float(input("Mark: "))
    names.append(name)
    marks.append(mark)
average = sum(marks) / n
best = max(marks)
print("Average:", round(average, 2))
print("Topper:", names[marks.index(best)], best)
for i in range(n):
    if marks[i] >= 90:
        grade = "A"
    elif marks[i] >= 75:
        grade = "B"
    elif marks[i] >= 50:
        grade = "C"
    else:
        grade = "F"
    print(names[i], grade)
