import pandas as pd

# Load the dataset
df = pd.read_csv('data/payments.csv')

# Filter for in-person transactions (shopper_interaction == 'POS') and year 2023
in_person_2023 = df[(df['shopper_interaction'] == 'POS') & (df['year'] == 2023)]

if len(in_person_2023) == 0:
    print("Not Applicable")
else:
    # has_fraudulent_dispute is boolean, so sum() counts True values
    # We use .apply(lambda x: 1 if str(x).lower() == 'true' else 0) to be safe with different types
    fraud_count = in_person_2023['has_fraudulent_dispute'].apply(lambda x: 1 if str(x).lower() == 'true' else 0).sum()
    total_count = len(in_person_2023)
    fraud_rate = fraud_count / total_count
    print(f"{fraud_rate}")
