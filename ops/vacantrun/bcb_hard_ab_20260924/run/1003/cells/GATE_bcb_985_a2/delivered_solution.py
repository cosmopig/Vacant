import pandas as pd
import json
import os
import math

def task_func(json_data, output_dir=".", file_name="country_population_report.csv"):
    # Parse JSON if it's a string
    if isinstance(json_data, str):
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError:
            raise ValueError("Malformed JSON data.")
    else:
        data = json_data

    # Determine the list of country records
    processed_records = []
    if isinstance(data, dict):
        if "Countries" in data and isinstance(data["Countries"], dict):
            countries_dict = data["Countries"]
            for country, population in countries_dict.items():
                processed_records.append({"Country": country, "Population": population})
        else:
            # If it's a dictionary but doesn't have "Countries" or it's empty
            raise ValueError("JSON data must contain 'Countries' key mapping to a dictionary.")
    elif isinstance(data, list):
        for entry in data:
            if not isinstance(entry, dict) or "Country" not in entry or "Population" not in entry:
                raise ValueError("Each entry in the JSON list must be a dictionary with 'Country' and 'Population' keys.")
            processed_records.append({"Country": entry["Country"], "Population": entry["Population"]})
    else:
        raise ValueError("JSON data must be a dictionary containing 'Countries' or a list of country records.")

    # Validate the processed records are not empty
    if not processed_records:
        raise ValueError("No country data found in JSON.")

    final_processed_data = []
    for record in processed_records:
        country = record["Country"]
        population = record["Population"]

        if not isinstance(country, str):
            raise ValueError("Country name must be a string.")
        
        try:
            # Check if population is numeric (int or float)
            if not isinstance(population, (int, float)):
                raise ValueError()
            
            if population < 0:
                raise ValueError("Population cannot be negative.")
            
            # Round down to nearest integer
            processed_pop = math.floor(float(population))
        except (ValueError, TypeError):
            raise ValueError("Population must be a non-negative numeric value.")

        final_processed_data.append({"Country": country, "Population": processed_pop})

    # Create DataFrame
    df = pd.DataFrame(final_processed_data)
    
    # Ensure columns are correct and in order
    if not all(col in df.columns for col in ["Country", "Population"]):
        raise ValueError("Missing required columns.")
    df = df[["Country", "Population"]]

    # Prepare output path
    output_path = os.path.join(output_dir, file_name)
    
    try:
        # Write to CSV
        df.to_csv(output_path, index=False)
    except (OSError, IOError):
        raise IOError(f"Could not write to {output_path}")

    return output_path, df
