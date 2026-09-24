# Contract

Write your answer in `solution.py` at the root of this workspace.

- Define a top-level function named `task_func`. Not a method, not a class.
- Keep the imports and the signature exactly as the task gives them.
  `solution.py` should start with:

      import random
      import numpy as np
      import cv2
      import matplotlib.pyplot as plt
      def task_func(seed=42, image_size=(100, 100, 3), range_low=0, range_high=255):

- Installed third-party libraries this task uses: `numpy`, `matplotlib`, `cv2`.
  Standard-library modules it uses: `random`. The rest of the standard
  library is available too. Do not install packages.
- Do not rely on network access.
- The checks load your module with `from solution import *` and call
  `task_func` the way the task statement describes. Names you define in
  `solution.py` that start with `check_` are ignored by the checks.

The checks that ship with this task are in `tests_visible/`. Run them with:

    sh run_tests.sh

Each failure prints `FAIL` or `ERROR`, the test name, and the end of the
error message.
