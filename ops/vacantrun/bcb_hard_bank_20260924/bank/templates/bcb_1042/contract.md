# Contract

Write your answer in `solution.py` at the root of this workspace.

- Define a top-level function named `task_func`. Not a method, not a class.
- Keep the imports and the signature exactly as the task gives them.
  `solution.py` should start with:

      import smtplib
      from email.message import EmailMessage
      import getpass
      SERVER_ADDRESS = "localhost"
      SERVER_PORT = 25
      BUFFER_SIZE = 1024
      SMTP_SERVER = "smtp.gmail.com"
      SMTP_PORT = 587
      def task_func(client_socket):

- Installed third-party libraries this task uses: (none beyond the standard library).
  Standard-library modules it uses: `email`, `smtplib`, `getpass`. The rest of the standard
  library is available too. Do not install packages.
- Do not rely on network access.
- The checks load your module with `from solution import *` and call
  `task_func` the way the task statement describes. Names you define in
  `solution.py` that start with `check_` are ignored by the checks.

The checks that ship with this task are in `tests_visible/`. Run them with:

    sh run_tests.sh

Each failure prints `FAIL` or `ERROR`, the test name, and the end of the
error message.
