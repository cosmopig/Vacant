import csv

count = 0
with open('data/hotel_data.csv', mode='r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            if float(row['star_rating']) == 5.0:
                count += 1
        except (ValueError, KeyError):
            continue

print(count)
