# Contract

Write your answer in `solution.py` at the root of this workspace.

- Define a top-level function named `task_func`. Not a method, not a class.
- Keep the imports and the signature exactly as the task gives them.
  `solution.py` should start with:

      import pandas as pd
      import numpy as np
      import codecs
      import re
      import datetime
      def task_func(start_year=1980, end_year=2000, email_domain='example.com',
                 latin_names=['Sopetón', 'Méndez', 'Gómez', 'Pérez', 'Muñoz'],
                 other_names=['Smith', 'Johnson', 'Williams', 'Brown', 'Jones'], 
                 rng_seed=None):

- Installed third-party libraries this task uses: `pandas`, `numpy`.
  Standard-library modules it uses: `codecs`, `re`, `datetime`. The rest of the standard
  library is available too. Do not install packages.
- Do not rely on network access.
- The checks load your module with `from solution import *` and call
  `task_func` the way the task statement describes. Names you define in
  `solution.py` that start with `check_` are ignored by the checks.

The checks that ship with this task are in `tests_visible/`. Run them with:

    sh run_tests.sh

Each failure prints `FAIL` or `ERROR`, the test name, and the end of the
error message.
