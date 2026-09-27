# Contract

Write your answer in `solution.py` at the root of this workspace.

- Define a top-level function named `task_func`. Not a method, not a class.
- Keep the imports and the signature exactly as the task gives them.
  `solution.py` should start with:

      from flask import Flask, render_template, redirect, url_for
      from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
      from flask_wtf import FlaskForm
      from wtforms import StringField, PasswordField, SubmitField
      from wtforms.validators import DataRequired, Length
      from werkzeug.security import generate_password_hash, check_password_hash
      class LoginForm(FlaskForm):
          username = StringField('Username', validators=[DataRequired(), Length(min=4, max=25)])
          password = PasswordField('Password', validators=[DataRequired(), Length(min=8, max=80)])
          submit = SubmitField('Log In')
      login_manager = LoginManager()
      def task_func(secret_key, template_folder):

- Installed third-party libraries this task uses: `flask_login`, `flask_wtf`, `wtforms`, `werkzeug`, `flask`.
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
