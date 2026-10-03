# Stand-in for a slow delivery check: only the zerostop check child sleeps.
import os, sys, time
_a = getattr(sys, "orig_argv", [])
if os.environ.get("SLOW_CHECK_S") and "vacant_network.trace.zerostop" in _a and "check" in _a:
    with open(os.environ["SLOW_LOG"], "a") as f:
        f.write(f"check child pid={os.getpid()} start {time.time():.1f}\n")
    time.sleep(float(os.environ["SLOW_CHECK_S"]))
    with open(os.environ["SLOW_LOG"], "a") as f:
        f.write(f"check child pid={os.getpid()} woke {time.time():.1f}\n")
