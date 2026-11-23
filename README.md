# Task workspaces and pre-existing-test gates

Vacant and its wrapper require Python >=3.11. Repository tests use separate
per-instance interpreters, not this Python. At this kit root:

```bash
PYTHON="${PYTHON:-python3.11}"
"$PYTHON" -m venv .venv
. .venv/bin/activate
python -m pip install git+https://github.com/cosmopig/Vacant 'pytest>=7,<8' 'setuptools<81'
```

Clone only your assigned `sandbox-v3/INSTANCE` branch into `INSTANCE/` under
this kit root (`git clone --single-branch --depth 1 --branch ...`). Read
`prompts/INSTANCE.txt` at the kit root: it is exactly the problem statement.
The workspace is an independent history-free base snapshot. With Conda
initialized, use the instance's Python version and harness setup commands below
from this kit root, creating `.envs/INSTANCE/bin/python`. Do not substitute a
newer interpreter. No environment is bundled with the workspace.
Install all dependencies needed by the selected tests, not only the project's
minimal runtime dependencies. The scikit-learn workspace needs pandas; use
the harness constraints below rather than separately upgrading NumPy/SciPy.
The commands are taken from the official harness environment and repository
installation specifications, adapting paths, temporary requirements files and
the digest-pinned official HTTPS Qhull download. Pytest
and pytest-django are added where listed. Django uses its own DiscoverRunner
for database setup; other projects load their environment's pytest plugins.
System provisioning commands require operator privileges and must be reviewed
for the host; the measured images already contain these system packages.
Do not install a released copy of the project in place of the workspace source.

Only the gated arm uses the selected pre-existing tests and feedback. They
reveal which existing tests must stay green; this is part of the intervention.
Other arms do not inspect gates. Newly added tests are excluded even when their
labels appear in the passing-test list. There are no newly introduced acceptance tests
or reference fixes here. Concrete base-passing node IDs are frozen, covering
every retained label. Ambiguous descriptions exclude base-skipped variants;
no failing-at-base variant is dropped. Every selected case must actually pass: skipped,
deselected, missing and unexecuted cases cause refusal with their IDs in feedback.

From `INSTANCE/`, with a fresh receipts directory each time:

```bash
TIMEOUT=$(../.venv/bin/python -c 'import json; print(json.load(open("../gates/INSTANCE/selection.json"))["timeout_s"])')
../.venv/bin/vacant run --workspace . --suite ../gates/INSTANCE \
  --run-dir ../receipts/INSTANCE-N --test-timeout "$TIMEOUT" \
  --sandbox none --retry none -- true
```

Use at most three submissions (N=1,2,3). The runner invokes only selected test
nodes through `.envs/INSTANCE/bin/python` and pytest with the repository's
own fixtures/conftest. BLAS/OMP/MKL threads are fixed to one inside the runner.
Timeouts are max(120, ceil(3 * measured base P2P seconds + 30)), measured in
each pinned official image. It does not run all tests or apply a test patch.

## django__django-15732

Python 3.9; measured base P2P 1.570s; gate timeout 120s.

```bash
conda create --prefix "$PWD/.envs/django__django-15732" python=3.9 -y
(
set -e
VACANT_REQUIREMENTS=$(mktemp)
trap 'rm -f -- "$VACANT_REQUIREMENTS"' EXIT
cat <<'EOF_59812759871' > "$VACANT_REQUIREMENTS"
aiosmtpd
asgiref >= 3.6.0
argon2-cffi >= 19.2.0
backports.zoneinfo; python_version < '3.9'
bcrypt
black
docutils
geoip2; python_version < '3.12'
jinja2 >= 2.11.0
numpy; python_version < '3.12'
Pillow >= 6.2.1; sys.platform != 'win32' or python_version < '3.12'
pylibmc; sys.platform != 'win32'
pymemcache >= 3.4.0
pytz
pywatchman; sys.platform != 'win32'
PyYAML
redis >= 3.4.0
selenium
sqlparse >= 0.3.1
tblib >= 1.5.0
tzdata
colorama; sys.platform == 'win32'

EOF_59812759871
conda activate "$PWD/.envs/django__django-15732" && python -m pip install -r "$VACANT_REQUIREMENTS"
)
conda activate "$PWD/.envs/django__django-15732"
cd django__django-15732
python -m pip install -e .
python -m pip install pytest==7.4.4 pytest-django==4.5.2
```

## astropy__astropy-13236

Python 3.9; measured base P2P 2.362s; gate timeout 120s.

```bash
conda create --prefix "$PWD/.envs/astropy__astropy-13236" python=3.9  -y
conda activate "$PWD/.envs/astropy__astropy-13236"
python -m pip install attrs==23.1.0 exceptiongroup==1.1.3 execnet==2.0.2 hypothesis==6.82.6 iniconfig==2.0.0 numpy==1.25.2 packaging==23.1 pluggy==1.3.0 psutil==5.9.5 pyerfa==2.0.0.3 pytest-arraydiff==0.5.0 pytest-astropy-header==0.2.2 pytest-astropy==0.10.0 pytest-cov==4.1.0 pytest-doctestplus==1.0.0 pytest-filter-subpackage==0.1.2 pytest-mock==3.11.1 pytest-openfiles==0.5.0 pytest-remotedata==0.4.0 pytest-xdist==3.3.1 pytest==7.4.0 PyYAML==6.0.1 setuptools==68.0.0 sortedcontainers==2.4.0 tomli==2.0.1
cd astropy__astropy-13236
sed -i 's/requires = \["setuptools",/requires = \["setuptools==68.0.0",/' pyproject.toml
python -m pip install -e .[test] --verbose
python -m pip install pytest==7.4.4
```

## matplotlib__matplotlib-24870

Python 3.11; measured base P2P 3.476s; gate timeout 120s.

```bash
cat <<'EOF_59812759871' > environment.yml
# To set up a development environment using conda run:
#
#   conda env create -f environment.yml
#   conda activate mpl-dev
#   pip install -e .
#
name: testbed
channels:
  - conda-forge
dependencies:
  # runtime dependencies
  - cairocffi
  - contourpy>=1.0.1
  - cycler>=0.10.0
  - fonttools>=4.22.0
  - importlib-resources>=3.2.0
  - kiwisolver>=1.0.1
  - numpy>=1.21
  - pillow>=6.2
  - pybind11>=2.6.0
  - pygobject
  - pyparsing
  - pyqt
  - python-dateutil>=2.1
  - setuptools
  - setuptools_scm
  - wxpython
  # building documentation
  - colorspacious
  - graphviz
  - ipython
  - ipywidgets
  - numpydoc>=0.8
  - packaging
  - pydata-sphinx-theme
  - pyyaml
  - sphinx>=1.8.1,!=2.0.0
  - sphinx-copybutton
  - sphinx-gallery>=0.10
  - sphinx-design
  - pip
  - pip:
      - mpl-sphinx-theme
      - sphinxcontrib-svg2pdfconverter
      - pikepdf
  # testing
  - coverage
  - flake8>=3.8
  - flake8-docstrings>=1.4.0
  - gtk4
  - ipykernel
  - nbconvert[execute]!=6.0.0,!=6.0.1
  - nbformat!=5.0.0,!=5.0.1
  - pandas!=0.25.0
  - psutil
  - pre-commit
  - pydocstyle>=5.1.0
  - pytest!=4.6.0,!=5.4.0
  - pytest-cov
  - pytest-rerunfailures
  - pytest-timeout
  - pytest-xdist
  - tornado
  - pytz

EOF_59812759871
conda env create --prefix "$PWD/.envs/matplotlib__matplotlib-24870" --file environment.yml
conda activate "$PWD/.envs/matplotlib__matplotlib-24870" && conda install python=3.11 -y
rm environment.yml
conda activate "$PWD/.envs/matplotlib__matplotlib-24870"
python -m pip install contourpy==1.1.0 cycler==0.11.0 fonttools==4.42.1 ghostscript kiwisolver==1.4.5 numpy==1.25.2 packaging==23.1 pillow==10.0.0 pikepdf pyparsing==3.0.9 python-dateutil==2.8.2 six==1.16.0 setuptools==68.1.2 setuptools-scm==7.1.0 typing-extensions==4.7.1
cd matplotlib__matplotlib-24870
apt-get -y update && apt-get -y upgrade && DEBIAN_FRONTEND=noninteractive apt-get install -y imagemagick ffmpeg texlive texlive-latex-extra texlive-fonts-recommended texlive-xetex texlive-luatex cm-super dvipng
QHULL_URL="https://codeload.github.com/qhull/qhull/tar.gz/refs/tags/2020.2"
QHULL_SHA256="59356b229b768e6e2b09a701448bfa222c37b797a84f87f864f97462d8dbc7c5"
QHULL_TAR="/tmp/qhull-2020-src-8.0.2.tgz"
QHULL_BUILD_DIR="$PWD/build"
curl --fail --location --proto "=https" --tlsv1.2 --output "$QHULL_TAR" "$QHULL_URL" || exit 1
mkdir -p "$QHULL_BUILD_DIR"
python -I -c 'import hashlib,pathlib,sys; actual=hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest(); sys.exit(0 if actual == sys.argv[2] else "Qhull sha256 mismatch")' "$QHULL_TAR" "$QHULL_SHA256" || exit 1
tar -xvzf "$QHULL_TAR" -C "$QHULL_BUILD_DIR"
python -m pip install -e .
python -m pip install pytest==7.4.4
```

## django__django-13344

Python 3.6; measured base P2P 73.113s; gate timeout 250s.

```bash
conda create --prefix "$PWD/.envs/django__django-13344" python=3.6 -y
(
set -e
VACANT_REQUIREMENTS=$(mktemp)
trap 'rm -f -- "$VACANT_REQUIREMENTS"' EXIT
cat <<'EOF_59812759871' > "$VACANT_REQUIREMENTS"
asgiref >= 3.3.2
argon2-cffi >= 16.1.0
backports.zoneinfo; python_version < '3.9'
bcrypt
docutils
geoip2
jinja2 >= 2.9.2
numpy
Pillow >= 6.2.0
pylibmc; sys.platform != 'win32'
pymemcache >= 3.4.0
python-memcached >= 1.59
pytz
pywatchman; sys.platform != 'win32'
PyYAML
selenium
sqlparse >= 0.2.2
tblib >= 1.5.0
tzdata
colorama; sys.platform == 'win32'

EOF_59812759871
conda activate "$PWD/.envs/django__django-13344" && python -m pip install -r "$VACANT_REQUIREMENTS"
)
conda activate "$PWD/.envs/django__django-13344"
cd django__django-13344
python -m pip install -e .
python -m pip install pytest==6.2.5 pytest-django==4.5.2
```

## astropy__astropy-14598

Python 3.9; measured base P2P 1.199s; gate timeout 120s.

```bash
conda create --prefix "$PWD/.envs/astropy__astropy-14598" python=3.9  -y
conda activate "$PWD/.envs/astropy__astropy-14598"
python -m pip install attrs==23.1.0 exceptiongroup==1.1.3 execnet==2.0.2 hypothesis==6.82.6 iniconfig==2.0.0 numpy==1.25.2 packaging==23.1 pluggy==1.3.0 psutil==5.9.5 pyerfa==2.0.0.3 pytest-arraydiff==0.5.0 pytest-astropy-header==0.2.2 pytest-astropy==0.10.0 pytest-cov==4.1.0 pytest-doctestplus==1.0.0 pytest-filter-subpackage==0.1.2 pytest-mock==3.11.1 pytest-openfiles==0.5.0 pytest-remotedata==0.4.0 pytest-xdist==3.3.1 pytest==7.4.0 PyYAML==6.0.1 setuptools==68.0.0 sortedcontainers==2.4.0 tomli==2.0.1
cd astropy__astropy-14598
sed -i 's/requires = \["setuptools",/requires = \["setuptools==68.0.0",/' pyproject.toml
python -m pip install -e .[test] --verbose
python -m pip install pytest==7.4.4
```

## sympy__sympy-14248

Python 3.9; measured base P2P 4.077s; gate timeout 120s.

```bash
conda create --prefix "$PWD/.envs/sympy__sympy-14248" python=3.9 mpmath flake8 -y
conda activate "$PWD/.envs/sympy__sympy-14248"
python -m pip install mpmath==1.3.0 flake8-comprehensions
cd sympy__sympy-14248
python -m pip install -e .
python -m pip install pytest==7.4.4 py==1.10.0
```

## scikit-learn__scikit-learn-25747

Python 3.9; measured base P2P 0.796s; gate timeout 120s.

```bash
conda create --prefix "$PWD/.envs/scikit-learn__scikit-learn-25747" python=3.9 'numpy==1.19.2' 'scipy==1.5.2' 'cython==3.0.10' pytest 'pandas<2.0.0' 'matplotlib<3.9.0' setuptools pytest joblib threadpoolctl -y
conda activate "$PWD/.envs/scikit-learn__scikit-learn-25747"
python -m pip install cython setuptools numpy scipy
cd scikit-learn__scikit-learn-25747
python -m pip install -v --no-use-pep517 --no-build-isolation -e .
python -m pip install pytest==7.4.4
```

## sphinx-doc__sphinx-8548

Python 3.9; measured base P2P 0.629s; gate timeout 120s.

```bash
conda create --prefix "$PWD/.envs/sphinx-doc__sphinx-8548" python=3.9  -y
conda activate "$PWD/.envs/sphinx-doc__sphinx-8548"
python -m pip install tox==4.16.0 tox-current-env==0.0.11 Jinja2==3.0.3
cd sphinx-doc__sphinx-8548
sed -i 's/pytest/pytest -rA/' tox.ini
sed -i 's/Jinja2>=2.3/Jinja2<3.0/' setup.py
sed -i 's/sphinxcontrib-applehelp/sphinxcontrib-applehelp<=1.0.7/' setup.py
sed -i 's/sphinxcontrib-devhelp/sphinxcontrib-devhelp<=1.0.5/' setup.py
sed -i 's/sphinxcontrib-qthelp/sphinxcontrib-qthelp<=1.0.6/' setup.py
sed -i 's/alabaster>=0.7,<0.8/alabaster>=0.7,<0.7.12/' setup.py
sed -i "s/'packaging',/'packaging', 'markupsafe<=2.0.1',/" setup.py
sed -i 's/sphinxcontrib-htmlhelp/sphinxcontrib-htmlhelp<=2.0.4/' setup.py
sed -i 's/sphinxcontrib-serializinghtml/sphinxcontrib-serializinghtml<=1.1.9/' setup.py
python -m pip install -e .[test]
python -m pip install pytest==7.4.4
```

## sympy__sympy-15875

Python 3.9; measured base P2P 2.222s; gate timeout 120s.

```bash
conda create --prefix "$PWD/.envs/sympy__sympy-15875" python=3.9 mpmath flake8 -y
conda activate "$PWD/.envs/sympy__sympy-15875"
python -m pip install mpmath==1.3.0 flake8-comprehensions
cd sympy__sympy-15875
python -m pip install -e .
python -m pip install pytest==7.4.4 py==1.10.0
```

## sympy__sympy-21612

Python 3.9; measured base P2P 0.849s; gate timeout 120s.

```bash
conda create --prefix "$PWD/.envs/sympy__sympy-21612" python=3.9 mpmath flake8 -y
conda activate "$PWD/.envs/sympy__sympy-21612"
python -m pip install mpmath==1.3.0 flake8-comprehensions
cd sympy__sympy-21612
python -m pip install -e .
python -m pip install pytest==7.4.4 py==1.10.0
```

## sphinx-doc__sphinx-7985

Python 3.9; measured base P2P 0.913s; gate timeout 120s.

```bash
conda create --prefix "$PWD/.envs/sphinx-doc__sphinx-7985" python=3.9  -y
conda activate "$PWD/.envs/sphinx-doc__sphinx-7985"
python -m pip install tox==4.16.0 tox-current-env==0.0.11 Jinja2==3.0.3
cd sphinx-doc__sphinx-7985
sed -i 's/pytest/pytest -rA/' tox.ini
sed -i 's/Jinja2>=2.3/Jinja2<3.0/' setup.py
sed -i 's/sphinxcontrib-applehelp/sphinxcontrib-applehelp<=1.0.7/' setup.py
sed -i 's/sphinxcontrib-devhelp/sphinxcontrib-devhelp<=1.0.5/' setup.py
sed -i 's/sphinxcontrib-qthelp/sphinxcontrib-qthelp<=1.0.6/' setup.py
sed -i 's/alabaster>=0.7,<0.8/alabaster>=0.7,<0.7.12/' setup.py
sed -i "s/'packaging',/'packaging', 'markupsafe<=2.0.1',/" setup.py
sed -i 's/sphinxcontrib-htmlhelp/sphinxcontrib-htmlhelp<=2.0.4/' setup.py
sed -i 's/sphinxcontrib-serializinghtml/sphinxcontrib-serializinghtml<=1.1.9/' setup.py
python -m pip install -e .[test]
python -m pip install pytest==7.4.4
```

## django__django-15563

Python 3.9; measured base P2P 0.680s; gate timeout 120s.

```bash
conda create --prefix "$PWD/.envs/django__django-15563" python=3.9 -y
(
set -e
VACANT_REQUIREMENTS=$(mktemp)
trap 'rm -f -- "$VACANT_REQUIREMENTS"' EXIT
cat <<'EOF_59812759871' > "$VACANT_REQUIREMENTS"
aiosmtpd
asgiref >= 3.4.1
argon2-cffi >= 16.1.0
backports.zoneinfo; python_version < '3.9'
bcrypt
black
docutils
geoip2
jinja2 >= 2.9.2
numpy
Pillow >= 6.2.0
pylibmc; sys.platform != 'win32'
pymemcache >= 3.4.0
pytz
pywatchman; sys.platform != 'win32'
PyYAML
redis >= 3.0.0
selenium
sqlparse >= 0.2.2
tblib >= 1.5.0
tzdata
colorama; sys.platform == 'win32'

EOF_59812759871
conda activate "$PWD/.envs/django__django-15563" && python -m pip install -r "$VACANT_REQUIREMENTS"
)
conda activate "$PWD/.envs/django__django-15563"
cd django__django-15563
python -m pip install -e .
python -m pip install pytest==7.4.4 pytest-django==4.5.2
```
