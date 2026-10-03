import os, time
_s = os.environ.get("SLOW_EVIDENCE")
if _s:
    import vacant_network.trace.evidence as _ev
    _orig = _ev.evidence_for
    def evidence_for(*a, **k):
        with open(os.environ["SLOW_LOG"], "a") as f:
            f.write(f"check child pid={os.getpid()} start {time.time():.3f}\n")
        time.sleep(float(_s))
        r = _orig(*a, **k)
        with open(os.environ["SLOW_LOG"], "a") as f:
            f.write(f"check child pid={os.getpid()} done {time.time():.3f}\n")
        return r
    _ev.evidence_for = evidence_for
