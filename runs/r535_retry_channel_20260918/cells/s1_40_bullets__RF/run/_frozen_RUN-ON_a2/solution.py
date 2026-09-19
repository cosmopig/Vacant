def format_list(strings):
    if not strings:
        return ""
    return "\n".join([f"- {s}" for s in strings])
