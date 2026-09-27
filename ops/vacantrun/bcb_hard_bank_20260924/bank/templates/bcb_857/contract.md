# Contract

Write your answer in `solution.py` at the root of this workspace.

- Define a top-level function named `task_func`. Not a method, not a class.
- Keep the imports and the signature exactly as the task gives them.
  `solution.py` should start with:

      import warnings
      import os
      import glob
      import shutil
      import time
      def task_func(SOURCE_DIR, DEST_DIR, EXTENSIONS):

- Installed third-party libraries this task uses: (none beyond the standard library).
  Standard-library modules it uses: `glob`, `warnings`, `time`, `shutil`, `os`. The rest of the standard
  library is available too. Do not install packages.
- Do not rely on network access.
- The checks load your module with `from solution import *` and call
  `task_func` the way the task statement describes. Names you define in
  `solution.py` that start with `check_` are ignored by the checks.

The checks that ship with this task are in `tests_visible/`. Run them with:

    sh run_tests.sh

Each failure prints `FAIL` or `ERROR`, the test name, and the end of the
error message.
