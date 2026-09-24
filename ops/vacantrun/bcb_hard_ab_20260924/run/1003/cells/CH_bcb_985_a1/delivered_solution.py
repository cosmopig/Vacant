import pandas as pd
import json
import os
import math

def task_func(json_data, output_dir=".", file_name="country_population_report.csv"):
    # Parse JSON data
    try:
        data = json.loads(json_data)
    except (json.JSONDecodeError, TypeError):
        raise ValueError("Malformed JSON")

    if not data:
        raise ValueError("Empty JSON data")

    countries = []
    populations = []

    # Handle list of dicts structure
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                raise ValueError("Malformed JSON")
            country = item.get("Country")
            population = item.get("Population")

            if not isinstance(country, str):
                raise ValueError("Non-string country name")
            
            try:
                pop_val = float(population)
                if pop_val < 0:
                    raise ValueError("Negative population")
                populations.append(math.floor(pop_val))
            except (ValueError, TypeError):
                raise ValueError("Non-numeric or negative population")

            countries.append(country)

    # Handle {"Countries": {...}} structure
    elif isinstance(data, dict) and "Countries" in data:
        countries_dict = data["Countries"]
        if not isinstance(countries_dict, dict):
            raise ValueError("Malformed JSON")
        for country, population in countries_dict.items():
            if not isinstance(country, str):
                raise ValueError("Non-string country name")
            try:
                pop_val = float(population)
                if pop_val < 0:
                    raise ValueError("Negative population")
                populations.append(math.floor(pop_val))
            except (ValueError, TypeError):
                raise ValueError("Non-numeric or negative population")
            countries.append(country)
    else:
        # If it's some other dict or something else not handled
        raise ValueError("Malformed JSON")

    if not countries:
        raise ValueError("Empty JSON data")

    # Create DataFrame
    df = pd.DataFrame({
        "Country": countries,
        "Population": populations
    })

    # Ensure output directory exists
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError:
            raise IOError("File cannot be written to the specified directory")

    file_path = os.path.join(output_dir, file_name)
    
    try:
        df.to_csv(file_path, index=False)
    except (OSError, IOError):
        raise IOError("File cannot be written to the specified directory")

    return file_path, df
