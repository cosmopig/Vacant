import json
import subprocess

def run_test(hex_color, expected):
    result = subprocess.run(['python3', 'solution.py'], input=hex_color, capture_output=True, text=True)
    actual = json.loads(result.stdout.strip())
    if actual == expected:
        print(f"PASS: {hex_color} -> {actual}")
    else:
        print(f"FAIL: {hex_color} -> Expected {expected}, got {actual}")

tests = [
    ("#FFFFFF", {"r": 255, "g": 255, "b": 255}),
    ("#000000", {"r": 0, "g": 0, "b": 0}),
    ("#FF5733", {"r": 255, "g": 87, "b": 51}),
    ("ffffff", {"r": 255, "g": 255, "b": 255}),
    ("#00ff00", {"r": 0, "g": 255, "b": 0}),
]

for color, expected in tests:
    run_test(color, expected)
