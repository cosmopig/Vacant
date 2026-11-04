import csv

def load_grades():
    with open('ops/reqloop/g1/tasks/student_grades/grades.csv', mode='r', encoding='utf-8') as f:
        return list(csv.DictReader(f))

grades = load_grades()
seen_ids = set()
all_scores = []
for g in grades:
    sid = g['student_id']
    if sid not in seen_ids and g['status'] != 'WITHDRAWN':
        mid = float(g['midterm_score'])
        final = float(g['final_score'])
        total = mid * 0.4 + final * 0.6
        all_scores.append(total)
        seen_ids.add(sid)

avg = sum(all_scores) / len(all_scores) if all_scores else 0
rate = sum(1 for s in all_scores if s >= 60.0) / len(all_scores) if all_scores else 0
print(f"Avg: {avg:.2f}, Rate: {rate:.2f}")
