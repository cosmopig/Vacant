import json

def calculate_average_fee():
    with open('data/fees.json', 'r') as f:
        data = json.load(f)
    
    # Filter for GlobalCard and credit transactions
    relevant_fees = []
    for item in data:
        if item['card_scheme'] == 'GlobalCard' and item.get('is_credit') is True:
            relevant_fees.append(item)
    
    if not relevant_fees:
        print("0.000000")
        return

    transaction_value = 10
    total_fee = 0
    
    for item in relevant_fees:
        # fee = fixed_amount + rate * transaction_value / 10000
        fixed_amount = item.get('fixed_amount', 0)
        rate = item.get('rate', 0)
        fee = fixed_amount + (rate * transaction_value / 10000)
        total_fee += fee
    
    average_fee = total_fee / len(relevant_fees)
    print(f"{average_fee:.6f}")

if __name__ == "__main__":
    calculate_average_fee()
