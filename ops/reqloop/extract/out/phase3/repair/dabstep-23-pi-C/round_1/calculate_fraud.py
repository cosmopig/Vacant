import pandas as pd

df = pd.read_csv('data/payments.csv')

# Filter for in-person transactions (shopper_interaction == 'POS') and year 2023
in_person_2023 = df[(df['shopper_interaction'] == 'POS') & (df['year'] == 2023)]

if len(in_person_2023) > 0:
    # has_fraudulent_dispute is boolean, sum() counts True values
    fraud_count = in_person_2023['has_fraudulent_dispute'].sum()
    fraud_rate = fraud_count / len(in_person_2023)
    print(f"{fraud_rate}")
else:
    # If no transactions found, the question might be Not Applicable or 0.0
    # But usually if data exists but doesn't match filter, it's a valid result of 0/0?
    # The prompt says "If a question does not have a relevant or applicable answer... respond with 'Not Applicable'"
    print("Not Applicable")
