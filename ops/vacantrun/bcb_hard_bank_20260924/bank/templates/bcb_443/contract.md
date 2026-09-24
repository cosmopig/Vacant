# Contract

Write your answer in `solution.py` at the root of this workspace.

- Define a top-level function named `task_func`. Not a method, not a class.
- Keep the imports and the signature exactly as the task gives them.
  `solution.py` should start with:

      import numpy as np
      from sklearn.cluster import KMeans
      import matplotlib.pyplot as plt
      def task_func(
          P: np.ndarray,
          T: np.ndarray,
          n_clusters: int = 3,
          random_state: int = 0,
          n_init: int = 10,
      ) -> (np.ndarray, plt.Axes):

- Installed third-party libraries this task uses: `numpy`, `matplotlib`, `sklearn`.
  Standard-library modules it uses: -. The rest of the standard
  library is available too. Do not install packages.
- Do not rely on network access.
- The checks load your module with `from solution import *` and call
  `task_func` the way the task statement describes. Names you define in
  `solution.py` that start with `check_` are ignored by the checks.

The checks that ship with this task are in `tests_visible/`. Run them with:

    sh run_tests.sh

Each failure prints `FAIL` or `ERROR`, the test name, and the end of the
error message.
