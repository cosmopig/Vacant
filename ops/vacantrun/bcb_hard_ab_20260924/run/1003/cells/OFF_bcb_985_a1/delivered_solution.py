import pandas as pd
import json
import os
import math

def task_func(json_data, output_dir=".", file_name="country_population_report.csv"):
    # Parse JSON data if it's a string
    if isinstance(json_data, str):
        try:
            data = json.loads(json_data)
        except (json.JSONDecodeError, TypeError):
            raise ValueError("Malformed JSON data")
    else:
        data = json_data

    # Check if it's a dictionary and has "Countries" key
    if not isinstance(data, dict) or "Countries" not in data:
        raise ValueError("Invalid JSON structure")

    countries_dict = data["Countries"]
    if not isinstance(countries_dict, dict) or len(countries_dict) == 0:
        raise ValueError("Empty or invalid Countries data")

    processed_data = []
    for country, population in countries_dict.items():
        if not isinstance(country, str):
            raise ValueError("Non-string country name")
        
        if not isinstance(population, (int, float)):
            raise ValueError("Non-numeric population")
        
        if population < 0:
            raise ValueError("Negative population")

        # Round down to nearest integer if it's a float
        if isinstance(population, float):
            population = math.floor(population)
        else:
            population = int(population)

        processed_data.append({"Country": country, "Population": population})

    df = pd.DataFrame(processed_data)
    # Ensure columns are in correct order and names are correct
    df = df[["Country", "Population"]]

    output_path = os.path.join(output_dir, file_name)
    
    try:
        df.to_csv(output_path, index=False)
    except Exception as e:
        raise IOError(f"Could not write to {output_path}") from e

    return output_path, df
