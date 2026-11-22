"""Event-sourced inventory projection with atomic batches."""
from checks import objects, required, integer, text, snapshot

QUANTITY_ERROR = "quantity must be an integer >= 0"


def _quantity(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(QUANTITY_ERROR)
    return value


def normalize(event):
    """Validate one event and return (id, sku, version, kind, quantity)."""
    required(event, ("id", "sku", "version", "kind"))
    event_id = text(event["id"], "id")
    sku = text(event["sku"], "sku")
    version = integer(event["version"], "version", 1)
    kind = event["kind"]
    if kind == "set":
        if "quantity" not in event:
            raise ValueError(QUANTITY_ERROR)
        quantity = _quantity(event["quantity"])
    elif kind == "delete":
        quantity = None
    else:
        raise ValueError("unknown kind")
    return event_id, sku, version, kind, quantity


class Projection:
    def __init__(self):
        self.state = {}
        self.seen = {}
        self._cache = None

    def apply(self, events):
        batch = objects(events, "events")
        if not batch:
            return
        state = snapshot(self.state)
        seen = dict(self.seen)
        changed = False
        for event in batch:
            event_id, sku, version, kind, quantity = normalize(event)
            if event_id in seen:
                if seen[event_id] != event:
                    raise ValueError("event conflict")
                continue
            seen[event_id] = snapshot(event)
            changed = True
            current = state.get(sku)
            if current is not None and version <= current["version"]:
                continue
            state[sku] = {"version": version, "quantity": quantity}
        if changed:
            self.state = state
            self.seen = seen
            self._cache = None

    def items(self):
        if self._cache is None:
            self._cache = [{"sku": sku, "quantity": item["quantity"], "version": item["version"]}
                           for sku, item in sorted(self.state.items())
                           if item["quantity"] is not None]
        return snapshot(self._cache)

    def quantity(self, sku):
        item = self.state.get(sku)
        return 0 if item is None or item["quantity"] is None else item["quantity"]

    def export(self):
        return snapshot({"version": 2, "state": self.state, "seen": self.seen})

    def size(self):
        return len(self.items())
