def bullets(items):
    if not items:
        return ""
    return "\n".join([f"- {item}" for item in items])
