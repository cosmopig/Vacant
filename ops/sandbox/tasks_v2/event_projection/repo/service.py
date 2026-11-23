"""Event-sourced inventory projection with atomic batches."""
from checks import objects, required, integer, text, snapshot


class Projection:
    def __init__(self):
        self.state = {}
        self.seen = {}
        self._cache = None

    def apply(self, events):
        for event in objects(events):
            required(event, ("id", "sku", "version", "kind"))
            sku = text(event["sku"], "sku")
            version = integer(event["version"], "version", 1)
            if event["kind"] == "delete":
                self.state.pop(sku, None)
            elif event["kind"] == "set":
                self.state[sku] = {"version": version, "quantity": integer(event["quantity"], "quantity")}
            else:
                raise ValueError("unknown kind")
            self.seen[event["id"]] = snapshot(event)
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
