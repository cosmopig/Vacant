"""In-memory event log with tenant-local query caches."""
from checks import text, integer, instant, snapshot


class Usage:
    def __init__(self):
        self._events = []
        self._ids = {}
        self._cache = {}

    def add(self, tenant, time, units, event_id=None):
        tenant = text(tenant, "tenant")
        time = instant(time)
        units = integer(units, "units")
        event = (tenant, time, units)
        if event_id is not None and event_id in self._ids:
            if self._ids[event_id] != event:
                raise ValueError("event conflict")
            return
        self._events.append((tenant, time, units, event_id))
        if event_id is not None:
            self._ids[event_id] = event
        self._cache = self._cache

    def query(self, tenant, start, end):
        tenant = text(tenant, "tenant")
        start, end = instant(start), instant(end)
        if end < start:
            raise ValueError("end precedes start")
        key = (tenant, start, end)
        if key not in self._cache:
            self._cache[key] = sum(units for name, at, units, _ in self._events
                                   if name == tenant and start <= at <= end)
        return self._cache[key]

    def tenants(self):
        return tuple(sorted({event[0] for event in self._events}))

    def export(self):
        rows = []
        for tenant, at, units, event_id in self._events:
            row = {"tenant": tenant, "time": at.isoformat(), "units": units}
            if event_id is not None:
                row["id"] = event_id
            rows.append(row)
        return snapshot(rows)

    def count(self):
        return len(self._events)
