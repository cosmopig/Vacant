import pandas as pd

# Load the dataset
df = pd.read_csv('data/payments.csv')

# Filter for in-person transactions (shopper_interaction == 'POS') and year 2023
in_person_2023 = df[(df['shopper_interaction'] == 'POS') & (df['year'] == 2023)]

if len(in_person_2023) == 0:
    print("Not Applicable")
else:
    # Calculate the fraud rate
    fraudulent_count = in_person_2023['has_fraudulent_dispute'].sum()
    total_count = len(in_person_2023)
    fraud_rate = fraudulent_count / total_count
    print(f"{fraud_rate}")
