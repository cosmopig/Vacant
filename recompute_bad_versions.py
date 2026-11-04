import csv
from collections import defaultdict

def load_grades():
    with open('ops/reqloop/g1/tasks/student_grades/grades.csv', mode='r', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def calculate_stats(grades, include_withdrawn=False, weight_midterm=0.4):
    # Remove duplicates based on student_id (keep first)
    seen_ids = set()
    unique_grades = []
    for g in grades:
        sid = g['student_id']
        if sid not in seen_ids:
            unique_grades.append(g)
            seen_ids.add(sid)
    
    # Filter by status if needed
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
    for cls, scores in class_data.items():
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

# 1. Good version (Standard)
good_stats = calculate_stats(grades, include_withdrawn=False, weight_midterm=0.4)
print("--- GOOD ---")
for s in good_stats: print(s)

# 2. bad_include_withdrawn
bad_withdrawn_stats = calculate_stats(grades, include_withdrawn=True, weight_midterm=0.4)
print("\n--- BAD INCLUDE WITHDRAWN ---")
for s in bad_withdrawn_stats: print(s)

# 3. bad_weight_calculation (50/50)
bad_weight_stats = calculate_stats(grades, include_withdrawn=False, weight_midterm=0.5)
print("\n--- BAD WEIGHT ---")
for s in bad_weight_stats: print(s)

# 4. Summary for Good (Total)
all_scores = []
seen_ids = set()
for g in grades:
    sid = g['student_id']
    if sid not in seen_ids and g['status'] != 'WITHDRAWN':
        mid = float(g['midterm_score'])
        final = float(g['final_score'])
        total = mid * 0.4 + final * 0.6
        all_scores.append(total)
        seen_ids.add(sid)

total_avg = sum(all_scores) / len(all_scores) if all_scores else 0
total_pass_rate = sum(1 for s in all_scores if s >= 60.0) / len(all_scores) if all_scores else 0
print("\n--- TOTAL SUMMARY (GOOD) ---")
print(f"Avg: {total_avg:.2f}, Rate: {total_pass_rate:.2f}")

