"""Known-bad C: the skeleton. Every name exists, almost nothing happens."""
def slugify(titles):
    return [title.lower().replace(" ", "-") for title in titles]
