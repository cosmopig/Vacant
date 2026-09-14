"""Reference solution for ow_18_taskorder (gauge only; never enters a workspace)."""


def all_jobs(jobs):
    """Every name that is a job: the keys, plus anything named as a prerequisite."""
    waiting = {}
    for name, needs in jobs.items():
        waiting.setdefault(name, set())
        for need in needs:
            waiting.setdefault(need, set())
            waiting[name].add(need)
    return waiting


def plan(jobs):
    waiting = all_jobs(jobs)
    ordered = []
    while waiting:
        # Sorting the ready set is the whole of the "same table, same order" rule.
        ready = sorted(name for name, needs in waiting.items() if not needs)
        if not ready:
            raise ValueError("these jobs wait on each other in a circle: %s"
                             % ", ".join(sorted(waiting)))
        for name in ready:
            ordered.append(name)
            del waiting[name]
        for needs in waiting.values():
            needs.difference_update(ready)
    return ordered
