import csv
from collections import defaultdict

def load_grades():
    with open('ops/reqloop/g1/tasks/student_grades/grades.csv', mode='r', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def calculate_stats(grades, include_withdrawn=False, weight_midterm=0.4):
    seen_ids = set()
    unique_grades = []
    for g in grades:
        sid = g['student_id']
        if sid not in seen_ids:
            unique_grades.append(g)
            seen_ids.add(sid)
    
    filtered_grades = []
    for g in unique_grades:
        if include_withdrawn or g['status'] != 'WITHDRAWN':
            filtered_grades.append(g)
            
    class_data = defaultdict(list)
    for g in filtered_grades:
        mid = float(g['midterm_score'])
        final = float(g['final_score'])
        total = mid * weight_midterm + final * (1.0 - weight_midterm)
        class_data[g['class_name']].append(total)
    
    summary = []
    for cls in sorted(class_data.keys()):
        scores = class_data[cls]
        count = len(scores)
        passing = sum(1 for s in scores if s >= 60.0)
        avg = sum(scores) / count if count > 0 else 0
        rate = passing / count if count > 0 else 0
        summary.append({
            'class_name': cls,
            'student_count': count,
            'passing_count': passing,
            'pass_rate': f"{rate:.2f}",
            'average_score': f"{avg:.2f}"
        })
    return summary

grades = load_grades()

# Good (Standard)
print("GOOD:")
for s in calculate_stats(grades, include_withdrawn=False, weight_midterm=0.4): print(s)

# Bad Include Withdrawn
print("\nBAD INCLUDE WITHDRAWN:")
for s in calculate_stats(grades, include_withdrawn=True, weight_midterm=0.4): print(s)

# Bad Weight (50/50)
print("\nBAD WEIGHT:")
for s in calculate_stats(grades, include_withdrawn=False, weight_midterm=0.5): print(s)

