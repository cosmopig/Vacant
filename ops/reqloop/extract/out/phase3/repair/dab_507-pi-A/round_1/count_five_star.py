import csv

def count_five_star_hotels():
    count = 0
    with open('data/hotel_data.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                if float(row['star_rating']) == 5.0:
                    count += 1
            except (ValueError, TypeError):
                pass
    return count

if __name__ == "__main__":
    print(count_five_star_hotels())
