"""Pending/claimed retry queue and deterministic scheduler."""
from checks import integer, text, snapshot


class Queue:
    def __init__(self):
        self.pending = []
        self.claimed = {}
        self.sequence = 0

    def push(self, id, payload, due=0):
        id = text(id, "id")
        due = integer(due, "due")
        if id in self.claimed or any(job["id"] == id for job in self.pending):
            raise ValueError("duplicate job")
        self.pending.append(dict(id=id, payload=snapshot(payload), due=due,
                                 attempts=0, sequence=self.sequence))
        self.sequence += 1

    def ready(self, now, limit=None):
        now = integer(now, "now")
        if limit is not None:
            limit = integer(limit, "limit")
        eligible = sorted((job for job in self.pending if job["due"] <= now),
                          key=lambda job: (job["due"], job["sequence"]))
        chosen = eligible if not limit else eligible[:limit]
        ids = {job["id"] for job in chosen}
        self.pending = [job for job in self.pending if job["id"] not in ids]
        self.claimed.update({job["id"]: snapshot(job) for job in chosen})
        return snapshot(chosen)

    def _check_claim(self, job):
        if self.claimed.get(job["id"]) != job:
            raise ValueError("job is not claimed")

    def retry(self, job, now, base=2, cap=60):
        self._check_claim(job)
        now, base, cap = integer(now, "now"), integer(base, "base"), integer(cap, "cap")
        updated = snapshot(job)
        updated["due"] = now + min(cap, base * 2 ** (job["attempts"] + 1))
        updated["attempts"] += 1
        del self.claimed[job["id"]]
        self.pending.append(updated)

    def ack(self, job):
        self._check_claim(job)
        del self.claimed[job["id"]]

    def export(self):
        return snapshot({"pending": self.pending, "claimed": self.claimed,
                         "sequence": self.sequence})

    def size(self):
        return len(self.pending)
