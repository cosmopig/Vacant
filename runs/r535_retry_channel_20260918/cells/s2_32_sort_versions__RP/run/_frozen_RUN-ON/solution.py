def sort_versions(vs):
    def version_key(v):
        return [int(part) for part in v.split('.')]
    
    return sorted(vs, key=version_key)

if __name__ == "__main__":
    # Example usage (optional, but good for testing)
    test_cases = [
        ["1.2", "1.10", "1.1"],
        ["10.0.1", "2.0", "10.0.0", "1.9.9"],
        ["1.2.3", "1.2.34", "1.2.3.1"]
    ]
    for case in test_cases:
        print(f"Input:  {case}")
        print(f"Output: {sort_versions(case)}")
