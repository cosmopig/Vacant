import json

def calculate_average_fee():
    with open('data/fees.json', 'r') as f:
        data = json.load(f)
    
    rules = [r for r in data if r['card_scheme'] == 'GlobalCard' and (r['is_credit'] is True or r['is_credit'] is None)]
    
    transaction_value = 10
    fees = []
    for r in rules:
        fee = r['fixed_amount'] + r['rate'] * transaction_value / 10000
        fees.append(fee)
    
    if not fees:
        return 0.0
    
    average_fee = sum(fees) / len(fees)
    return round(average_fee, 6)

if __name__ == "__main__":
    print(calculate_average_fee())
