def sort_versions(vs):
    def version_key(v):
        return [int(part) for part in v.split('.')]
    
    return sorted(vs, key=version_key)

if __name__ == "__main__":
    # Example usage (optional, but good for testing)
    test_cases = [
        ["1.10", "1.9", "1.2"],
        ["2.1", "2.10", "2.2", "2.0"],
        ["10.0.1", "10.0.10", "10.0.2"]
    ]
    for case in test_cases:
        print(f"Input: {case}")
        print(f"Sorted: {sort_versions(case)}")
