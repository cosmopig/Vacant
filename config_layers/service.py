"""Recursive merge and include graph evaluation."""
from checks import snapshot, text


def merge(base, patch):
    result = dict(base)
    for key, value in patch.items():
        if value is None:
            result[key] = None
        elif isinstance(value, dict):
            previous = result.get(key, {})
            result[key] = merge(previous if isinstance(previous, dict) else {}, value)
        else:
            result[key] = snapshot(value)
    return result


def resolve(name, documents):
    memo = {}

    def visit(current, active):
        if current in active:
            raise ValueError("include cycle: " + current)
        if current in memo:
            return snapshot(memo[current])
        document = documents[current]
        includes = document.get("include", [])
        if not isinstance(includes, list):
            raise ValueError("include must be a list")
        merged = {}
        for parent in includes:
            parent = text(parent, "include")
            merged = merge(merged, visit(parent, active + (current,)))
        merged = merge(merged, document.get("config", {}))
        memo[current] = merged
        return snapshot(merged)

    return visit(name, ())


def effective(name, documents, env=None):
    return merge(resolve(name, documents), {} if env is None else env)


def explain(name, documents):
    resolved = resolve(name, documents)
    return {"document": name, "keys": sorted(resolved), "config": resolved}


def get_path(config, path, default=None):
    value = config
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return snapshot(default)
        value = value[part]
    return snapshot(value)
