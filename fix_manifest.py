import json

path = "ops/reqloop/g2/realtask_manifest.json"
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Update budget section with cost caps (already mostly there but let's ensure they are correct)
# The ticket says max_tool_calls=60, max_tokens=4000000, timeout_s_per_round=300
data['budget']['max_tool_calls'] = 60
data['budget']['max_tokens'] = 4000000
data['budget']['timeout_s_per_round'] = 300

# Add six_elements to the root of the manifest (or where it belongs)
# Looking at Slice B, it's a top-level key.
data['six_elements'] = {
    "cost_cap": {
        "max_tool_calls": 60,
        "max_tokens": 4000000,
        "timeout_s_per_round": 300
    },
    "current_behavior": "The agent uses a repair loop to address identified gaps in the target code. It generates multiple drafts and selects the best one based on scoring metrics (e.g., gap closure, coverage).",
    "expected_demonstrable_improvement": "Significant reduction in 'gap' count across all arms compared to baseline, with high reliability in fixing known-bad stubs.",
    "independent_acceptance": "The gate verifies that the final draft satisfies all required test cases and meets the minimum scoring threshold for success."
}

with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
