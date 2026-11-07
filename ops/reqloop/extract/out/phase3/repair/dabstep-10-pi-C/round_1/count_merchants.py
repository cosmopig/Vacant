import csv

def count_unique_merchants(file_path):
    unique_merchants = set()
    with open(file_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            merchant = row.get('merchant')
            if merchant:
                # Strip whitespace to ensure "Merchant" and "Merchant " are treated the same
                unique_merchants.add(merchant.strip())
    return len(unique_merchants)

if __name__ == "__main__":
    count = count_unique_merchants('data/payments.csv')
    print(count)
