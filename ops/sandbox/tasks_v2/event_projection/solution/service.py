"""Event-sourced inventory projection with atomic batches."""
from checks import objects, required, integer, text, snapshot


class Projection:
    def __init__(self):
        self.state = {}
        self.seen = {}
        self._cache = None

    def apply(self, events):
        events = objects(events)
        state, seen = snapshot(self.state), snapshot(self.seen)
        for event in events:
            required(event, ("id", "sku", "version", "kind"))
            text(event["id"], "id")
            sku = text(event["sku"], "sku")
            version = integer(event["version"], "version", 1)
            kind = event["kind"]
            if kind not in ("set", "delete"):
                raise ValueError("unknown kind")
            quantity = integer(event.get("quantity"), "quantity") if kind == "set" else None
            if event["id"] in seen:
                if seen[event["id"]] != event:
                    raise ValueError("event conflict")
                continue
            seen[event["id"]] = snapshot(event)
            if version <= state.get(sku, {"version": 0})["version"]:
                continue
            state[sku] = {"version": version, "quantity": quantity}
        self.state, self.seen = state, seen
        self._cache = None

    def items(self):
        if self._cache is None:
            self._cache = [{"sku": sku, **item} for sku, item in sorted(self.state.items())
                           if item["quantity"] is not None]
        return snapshot(self._cache)

    def quantity(self, sku):
        item = self.state.get(sku)
        return 0 if item is None or item["quantity"] is None else item["quantity"]

    def export(self):
        return snapshot({"version": 2, "state": self.state, "seen": self.seen})

    def size(self):
        return len(self.items())
