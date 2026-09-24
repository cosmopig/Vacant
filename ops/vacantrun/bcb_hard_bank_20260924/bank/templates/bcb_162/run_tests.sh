#!/bin/sh
# Run the checks that ship with this task against the current directory.
# Each check_* function in tests_visible/ is run; failures are printed.
exec python3 - "$@" <<'PY'
import importlib.util, os, sys, traceback
sys.path.insert(0, os.getcwd())
failed = 0
d = os.path.join(os.getcwd(), "tests_visible")
for name in sorted(os.listdir(d)):
    if not (name.startswith("test_") and name.endswith(".py")):
        continue
    path = os.path.join(d, name)
    spec = importlib.util.spec_from_file_location("vis_" + name[:-3], path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        failed += 1
        print("%s: could not be imported" % name)
        traceback.print_exc()
        continue
    checks = [(n, v) for n, v in vars(mod).items()
              if n.startswith("check_") and callable(v)]
    if not checks:
        main = getattr(mod, "main", None)
        checks = [("main", main)] if callable(main) else []
    for cname, fn in checks:
        try:
            fn()
        except Exception as e:
            failed += 1
            print("FAIL %s::%s  %s: %s" % (name, cname, type(e).__name__, e))
        else:
            print("pass %s::%s" % (name, cname))
print("%d check(s) failed" % failed)
sys.exit(1 if failed else 0)
PY
