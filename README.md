# v4 native task kit

Clone only your assigned history-free `sandbox-v4/<id>` into `<id>/`. Read `prompts/<id>.txt`.

Do not look up upstream fixes, SWE-bench data, another branch, or another session.

Do not open a pull request; the pushed branch is the only deliverable.

Kit root bootstrap (Linux x86_64; native environments, no Docker pulls):

```bash

KIT_ROOT="$PWD"

mkdir -p .tools

curl --fail --location --proto "=https" --tlsv1.2 https://api.anaconda.org/download/conda-forge/micromamba/2.10.0/linux-64/micromamba-2.10.0-0.tar.bz2 --output .tools/micromamba.tar.bz2

echo "9a97976244929bbae28fb1fae504e74a3e7e6d1932870e3a03321f01b7fbd07b  .tools/micromamba.tar.bz2" | sha256sum --check

tar -xjf .tools/micromamba.tar.bz2 -C .tools bin/micromamba

export PATH="$KIT_ROOT/.tools/bin:$PATH"

export MAMBA_ROOT_PREFIX="$KIT_ROOT/.mamba"

eval "$(micromamba shell hook --shell bash)"

```

Vacant wrapper: Python >=3.11; tests: the instance Python, never a stdlib shim.

```bash

micromamba create -c conda-forge -p "$KIT_ROOT/.venv" python=3.11 -y

.venv/bin/python -m pip install git+https://github.com/cosmopig/Vacant@1c20654824be170d43f9893161149e054b0b760f

```

Vacant arm: write root VACANT_TESTS.txt, one explicit test node ID per line.

A: pristine base plus only listed candidate test files must exhibit a test-body failure.

B: every listed node must execute and pass on the candidate. C: frozen pre-existing P2P.

Collection/import/setup failures and skips do not qualify as red. Every refusal names step and nodes.

Only the root manifest is dropped from handback patches; retain your tests.

At most 3 submissions. Do not edit gates/. Keep base HEAD unchanged until gating.

Run from <id>/, with receipts under this kit root:

```bash

TIMEOUT=$(../.venv/bin/python -c 'import json; print(json.load(open("../gates/<id>/selection.json"))["timeout_s"])')

../.venv/bin/vacant run --workspace . --suite ../gates/<id> --run-dir ../receipts/<id>-N --test-timeout "$TIMEOUT" --sandbox none --retry none -- true

```

Gate acceptance is not hidden correctness, a security boundary, or a zero-config installation effect.


## django__django-11400

Python 3.6; measured base P2P 1.168s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/django__django-11400"

mkdir -p "$KIT_ROOT/.setup/django__django-11400"

cd "$KIT_ROOT/.setup/django__django-11400"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.6 -y

(
set -e
VACANT_REQUIREMENTS=$(mktemp)
trap 'rm -f -- "$VACANT_REQUIREMENTS"' EXIT
cat <<'EOF_59812759871' > "$VACANT_REQUIREMENTS"
asgiref ~= 3.2
argon2-cffi >= 16.1.0
bcrypt
docutils
geoip2
jinja2 >= 2.9.2
numpy
Pillow != 5.4.0
pylibmc; sys.platform != 'win32'
python-memcached >= 1.59
pytz
pywatchman; sys.platform != 'win32'
PyYAML
selenium
sqlparse >= 0.2.2
tblib >= 1.5.0

EOF_59812759871
micromamba activate "$ENV_PREFIX" && python -m pip install -r "$VACANT_REQUIREMENTS"
)

micromamba activate "$ENV_PREFIX"

python -m pip install pip==21.3.1 setuptools==59.6.0 wheel==0.37.1

cd "$KIT_ROOT/django__django-11400"

python -m pip install -e .

python -m pip install pytest==6.2.5 pytest-django==4.5.2

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'django'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sphinx-doc__sphinx-10614

Python 3.9; measured base P2P 1.217s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sphinx-doc__sphinx-10614"

mkdir -p "$KIT_ROOT/.setup/sphinx-doc__sphinx-10614"

cd "$KIT_ROOT/.setup/sphinx-doc__sphinx-10614"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9  -y

micromamba activate "$ENV_PREFIX"

python -m pip install tox==4.16.0 tox-current-env==0.0.11 Jinja2==3.0.3

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sphinx-doc__sphinx-10614"

sed -i 's/pytest/pytest -rA/' tox.ini

micromamba install -c conda-forge -p "$ENV_PREFIX" -y graphviz

python -m pip install -e .[test]

python -m pip install pytest==7.4.4 roman==4.1

```


## matplotlib__matplotlib-23299

Python 3.11; measured base P2P 1.569s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/matplotlib__matplotlib-23299"

mkdir -p "$KIT_ROOT/.setup/matplotlib__matplotlib-23299"

cd "$KIT_ROOT/.setup/matplotlib__matplotlib-23299"

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
  - cairocffi
  - contourpy>=1.0.1
  - cycler>=0.10.0
  - fonttools>=4.22.0
  - kiwisolver>=1.0.1
  - numpy>=1.19
  - pillow>=6.2
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
  - gtk3
  - ipykernel
  - nbconvert!=6.0.0,!=6.0.1
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

micromamba env create -p "$ENV_PREFIX" --file environment.yml -y

micromamba activate "$ENV_PREFIX" && micromamba install -c conda-forge -p "$ENV_PREFIX" python=3.11 -y

rm environment.yml

micromamba activate "$ENV_PREFIX"

python -m pip install contourpy==1.1.0 cycler==0.11.0 fonttools==4.42.1 ghostscript kiwisolver==1.4.5 numpy==1.25.2 packaging==23.1 pillow==10.0.0 pikepdf pyparsing==3.0.9 python-dateutil==2.8.2 six==1.16.0 setuptools==68.1.2 setuptools-scm==7.1.0 typing-extensions==4.7.1

python -m pip install 'nbconvert[execute]!=6.0.0,!=6.0.1'

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/matplotlib__matplotlib-23299"

micromamba install -c conda-forge -p "$ENV_PREFIX" -y graphviz ghostscript

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

python -m pip install "pandas<2" "setuptools-scm<8"

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

QHULL_URL="https://codeload.github.com/qhull/qhull/tar.gz/refs/tags/2020.2"

QHULL_SHA256="59356b229b768e6e2b09a701448bfa222c37b797a84f87f864f97462d8dbc7c5"

QHULL_TAR="$VACANT_BUILD_TMP/qhull-2020-src-8.0.2.tgz"

QHULL_BUILD_DIR="$PWD/build"

curl --fail --location --proto "=https" --tlsv1.2 --output "$QHULL_TAR" "$QHULL_URL" || exit 1

mkdir -p "$QHULL_BUILD_DIR"

python -I -c 'import hashlib,pathlib,sys; actual=hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest(); sys.exit(0 if actual == sys.argv[2] else "Qhull sha256 mismatch")' "$QHULL_TAR" "$QHULL_SHA256" || exit 1

tar -xvzf "$QHULL_TAR" -C "$QHULL_BUILD_DIR"

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'matplotlib'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sympy__sympy-13974

Python 3.9; measured base P2P 1.422s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sympy__sympy-13974"

mkdir -p "$KIT_ROOT/.setup/sympy__sympy-13974"

cd "$KIT_ROOT/.setup/sympy__sympy-13974"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 mpmath flake8 -y

micromamba activate "$ENV_PREFIX"

python -m pip install mpmath==1.3.0 flake8-comprehensions

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sympy__sympy-13974"

python -m pip install -e .

python -m pip install pytest==7.4.4 py==1.10.0

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sympy'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## django__django-11141

Python 3.6; measured base P2P 0.866s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/django__django-11141"

mkdir -p "$KIT_ROOT/.setup/django__django-11141"

cd "$KIT_ROOT/.setup/django__django-11141"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.6 -y

(
set -e
VACANT_REQUIREMENTS=$(mktemp)
trap 'rm -f -- "$VACANT_REQUIREMENTS"' EXIT
cat <<'EOF_59812759871' > "$VACANT_REQUIREMENTS"
asgiref >= 3.2
argon2-cffi >= 16.1.0
bcrypt
docutils
geoip2
jinja2 >= 2.9.2
numpy
Pillow >= 6.2.0
pylibmc; sys.platform != 'win32'
python-memcached >= 1.59
pytz
pywatchman; sys.platform != 'win32'
PyYAML
selenium
sqlparse >= 0.2.2
tblib >= 1.5.0

EOF_59812759871
micromamba activate "$ENV_PREFIX" && python -m pip install -r "$VACANT_REQUIREMENTS"
)

micromamba activate "$ENV_PREFIX"

python -m pip install pip==21.3.1 setuptools==59.6.0 wheel==0.37.1

cd "$KIT_ROOT/django__django-11141"

python -m pip install -e .

python -m pip install pytest==6.2.5 pytest-django==4.5.2

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'django'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## matplotlib__matplotlib-26466

Python 3.11; measured base P2P 4.779s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/matplotlib__matplotlib-26466"

mkdir -p "$KIT_ROOT/.setup/matplotlib__matplotlib-26466"

cd "$KIT_ROOT/.setup/matplotlib__matplotlib-26466"

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
  - pyparsing>=2.3.1
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
  - sphinx-gallery>=0.12
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
  - nbconvert!=6.0.0,!=6.0.1,!=7.3.0,!=7.3.1
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
  - black

EOF_59812759871

micromamba env create -p "$ENV_PREFIX" --file environment.yml -y

micromamba activate "$ENV_PREFIX" && micromamba install -c conda-forge -p "$ENV_PREFIX" python=3.11 -y

rm environment.yml

micromamba activate "$ENV_PREFIX"

python -m pip install contourpy==1.1.0 cycler==0.11.0 fonttools==4.42.1 ghostscript kiwisolver==1.4.5 numpy==1.25.2 packaging==23.1 pillow==10.0.0 pikepdf pyparsing==3.0.9 python-dateutil==2.8.2 six==1.16.0 setuptools==68.1.2 setuptools-scm==7.1.0 typing-extensions==4.7.1

python -m pip install 'nbconvert[execute]!=6.0.0,!=6.0.1,!=7.3.0,!=7.3.1'

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/matplotlib__matplotlib-26466"

micromamba install -c conda-forge -p "$ENV_PREFIX" -y graphviz ghostscript

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

python -m pip install "pandas<2" "setuptools-scm<8"

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

QHULL_URL="https://codeload.github.com/qhull/qhull/tar.gz/refs/tags/2020.2"

QHULL_SHA256="59356b229b768e6e2b09a701448bfa222c37b797a84f87f864f97462d8dbc7c5"

QHULL_TAR="$VACANT_BUILD_TMP/qhull-2020-src-8.0.2.tgz"

QHULL_BUILD_DIR="$PWD/build"

curl --fail --location --proto "=https" --tlsv1.2 --output "$QHULL_TAR" "$QHULL_URL" || exit 1

mkdir -p "$QHULL_BUILD_DIR"

python -I -c 'import hashlib,pathlib,sys; actual=hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest(); sys.exit(0 if actual == sys.argv[2] else "Qhull sha256 mismatch")' "$QHULL_TAR" "$QHULL_SHA256" || exit 1

tar -xvzf "$QHULL_TAR" -C "$QHULL_BUILD_DIR"

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'matplotlib'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## django__django-15973

Python 3.9; measured base P2P 1.067s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/django__django-15973"

mkdir -p "$KIT_ROOT/.setup/django__django-15973"

cd "$KIT_ROOT/.setup/django__django-15973"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 -y

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
micromamba activate "$ENV_PREFIX" && python -m pip install -r "$VACANT_REQUIREMENTS"
)

micromamba activate "$ENV_PREFIX"

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/django__django-15973"

python -m pip install -e .

python -m pip install pytest==7.4.4 pytest-django==4.5.2

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'django'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## django__django-16256

Python 3.9; measured base P2P 0.822s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/django__django-16256"

mkdir -p "$KIT_ROOT/.setup/django__django-16256"

cd "$KIT_ROOT/.setup/django__django-16256"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 -y

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
micromamba activate "$ENV_PREFIX" && python -m pip install -r "$VACANT_REQUIREMENTS"
)

micromamba activate "$ENV_PREFIX"

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/django__django-16256"

python -m pip install -e .

python -m pip install pytest==7.4.4 pytest-django==4.5.2

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'django'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sympy__sympy-23950

Python 3.9; measured base P2P 1.468s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sympy__sympy-23950"

mkdir -p "$KIT_ROOT/.setup/sympy__sympy-23950"

cd "$KIT_ROOT/.setup/sympy__sympy-23950"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 mpmath flake8 -y

micromamba activate "$ENV_PREFIX"

python -m pip install mpmath==1.3.0 flake8-comprehensions

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sympy__sympy-23950"

python -m pip install -e .

python -m pip install pytest==7.4.4 py==1.10.0

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sympy'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sympy__sympy-20916

Python 3.9; measured base P2P 1.418s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sympy__sympy-20916"

mkdir -p "$KIT_ROOT/.setup/sympy__sympy-20916"

cd "$KIT_ROOT/.setup/sympy__sympy-20916"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 mpmath flake8 -y

micromamba activate "$ENV_PREFIX"

python -m pip install mpmath==1.3.0 flake8-comprehensions

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sympy__sympy-20916"

python -m pip install -e .

python -m pip install pytest==7.4.4 py==1.10.0

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sympy'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sphinx-doc__sphinx-9461

Python 3.9; measured base P2P 2.470s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sphinx-doc__sphinx-9461"

mkdir -p "$KIT_ROOT/.setup/sphinx-doc__sphinx-9461"

cd "$KIT_ROOT/.setup/sphinx-doc__sphinx-9461"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9  -y

micromamba activate "$ENV_PREFIX"

python -m pip install tox==4.16.0 tox-current-env==0.0.11 Jinja2==3.0.3

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sphinx-doc__sphinx-9461"

sed -i 's/pytest/pytest -rA/' tox.ini

sed -i 's/Jinja2>=2.3/Jinja2<3.0/' setup.py

sed -i 's/sphinxcontrib-applehelp/sphinxcontrib-applehelp<=1.0.7/' setup.py

sed -i 's/sphinxcontrib-devhelp/sphinxcontrib-devhelp<=1.0.5/' setup.py

sed -i 's/sphinxcontrib-qthelp/sphinxcontrib-qthelp<=1.0.6/' setup.py

sed -i 's/alabaster>=0.7,<0.8/alabaster>=0.7,<0.7.12/' setup.py

sed -i "s/'packaging',/'packaging', 'markupsafe<=2.0.1',/" setup.py

sed -i 's/sphinxcontrib-htmlhelp>=2.0.0/sphinxcontrib-htmlhelp>=2.0.0,<=2.0.4/' setup.py

sed -i 's/sphinxcontrib-serializinghtml>=1.1.5/sphinxcontrib-serializinghtml>=1.1.5,<=1.1.9/' setup.py

python -m pip install -e .[test]

python -m pip install pytest==7.4.4 roman==4.1

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sphinx'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sphinx-doc__sphinx-8595

Python 3.9; measured base P2P 3.677s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sphinx-doc__sphinx-8595"

mkdir -p "$KIT_ROOT/.setup/sphinx-doc__sphinx-8595"

cd "$KIT_ROOT/.setup/sphinx-doc__sphinx-8595"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9  -y

micromamba activate "$ENV_PREFIX"

python -m pip install tox==4.16.0 tox-current-env==0.0.11 Jinja2==3.0.3

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sphinx-doc__sphinx-8595"

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

python -m pip install pytest==7.4.4 roman==4.1

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sphinx'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## django__django-15916

Python 3.9; measured base P2P 1.268s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/django__django-15916"

mkdir -p "$KIT_ROOT/.setup/django__django-15916"

cd "$KIT_ROOT/.setup/django__django-15916"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 -y

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
micromamba activate "$ENV_PREFIX" && python -m pip install -r "$VACANT_REQUIREMENTS"
)

micromamba activate "$ENV_PREFIX"

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/django__django-15916"

python -m pip install -e .

python -m pip install pytest==7.4.4 pytest-django==4.5.2

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'django'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sympy__sympy-16597

Python 3.9; measured base P2P 2.575s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sympy__sympy-16597"

mkdir -p "$KIT_ROOT/.setup/sympy__sympy-16597"

cd "$KIT_ROOT/.setup/sympy__sympy-16597"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 mpmath flake8 -y

micromamba activate "$ENV_PREFIX"

python -m pip install mpmath==1.3.0 flake8-comprehensions

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sympy__sympy-16597"

python -m pip install -e .

python -m pip install pytest==7.4.4 py==1.10.0

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sympy'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## matplotlib__matplotlib-26208

Python 3.11; measured base P2P 45.233s; timeout 166s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/matplotlib__matplotlib-26208"

mkdir -p "$KIT_ROOT/.setup/matplotlib__matplotlib-26208"

cd "$KIT_ROOT/.setup/matplotlib__matplotlib-26208"

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
  - pyparsing>=2.3.1
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
  - sphinx-gallery>=0.12
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
  - nbconvert!=6.0.0,!=6.0.1,!=7.3.0,!=7.3.1
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
  - black

EOF_59812759871

micromamba env create -p "$ENV_PREFIX" --file environment.yml -y

micromamba activate "$ENV_PREFIX" && micromamba install -c conda-forge -p "$ENV_PREFIX" python=3.11 -y

rm environment.yml

micromamba activate "$ENV_PREFIX"

python -m pip install contourpy==1.1.0 cycler==0.11.0 fonttools==4.42.1 ghostscript kiwisolver==1.4.5 numpy==1.25.2 packaging==23.1 pillow==10.0.0 pikepdf pyparsing==3.0.9 python-dateutil==2.8.2 six==1.16.0 setuptools==68.1.2 setuptools-scm==7.1.0 typing-extensions==4.7.1

python -m pip install 'nbconvert[execute]!=6.0.0,!=6.0.1,!=7.3.0,!=7.3.1'

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/matplotlib__matplotlib-26208"

micromamba install -c conda-forge -p "$ENV_PREFIX" -y graphviz ghostscript

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

python -m pip install "pandas<2" "setuptools-scm<8"

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

QHULL_URL="https://codeload.github.com/qhull/qhull/tar.gz/refs/tags/2020.2"

QHULL_SHA256="59356b229b768e6e2b09a701448bfa222c37b797a84f87f864f97462d8dbc7c5"

QHULL_TAR="$VACANT_BUILD_TMP/qhull-2020-src-8.0.2.tgz"

QHULL_BUILD_DIR="$PWD/build"

curl --fail --location --proto "=https" --tlsv1.2 --output "$QHULL_TAR" "$QHULL_URL" || exit 1

mkdir -p "$QHULL_BUILD_DIR"

python -I -c 'import hashlib,pathlib,sys; actual=hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest(); sys.exit(0 if actual == sys.argv[2] else "Qhull sha256 mismatch")' "$QHULL_TAR" "$QHULL_SHA256" || exit 1

tar -xvzf "$QHULL_TAR" -C "$QHULL_BUILD_DIR"

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'matplotlib'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## django__django-13513

Python 3.6; measured base P2P 3.025s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/django__django-13513"

mkdir -p "$KIT_ROOT/.setup/django__django-13513"

cd "$KIT_ROOT/.setup/django__django-13513"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.6 -y

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
micromamba activate "$ENV_PREFIX" && python -m pip install -r "$VACANT_REQUIREMENTS"
)

micromamba activate "$ENV_PREFIX"

python -m pip install pip==21.3.1 setuptools==59.6.0 wheel==0.37.1

cd "$KIT_ROOT/django__django-13513"

python -m pip install -e .

python -m pip install pytest==6.2.5 pytest-django==4.5.2

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'django'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## django__django-14140

Python 3.8; measured base P2P 1.518s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/django__django-14140"

mkdir -p "$KIT_ROOT/.setup/django__django-14140"

cd "$KIT_ROOT/.setup/django__django-14140"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.8 -y

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
redis >= 3.0.0
selenium
sqlparse >= 0.2.2
tblib >= 1.5.0
tzdata
colorama; sys.platform == 'win32'

EOF_59812759871
micromamba activate "$ENV_PREFIX" && python -m pip install -r "$VACANT_REQUIREMENTS"
)

micromamba activate "$ENV_PREFIX"

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/django__django-14140"

python -m pip install -e .

python -m pip install pytest==7.4.4 pytest-django==4.5.2

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'django'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## django__django-15957

Python 3.9; measured base P2P 1.067s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/django__django-15957"

mkdir -p "$KIT_ROOT/.setup/django__django-15957"

cd "$KIT_ROOT/.setup/django__django-15957"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 -y

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
micromamba activate "$ENV_PREFIX" && python -m pip install -r "$VACANT_REQUIREMENTS"
)

micromamba activate "$ENV_PREFIX"

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/django__django-15957"

python -m pip install -e .

python -m pip install pytest==7.4.4 pytest-django==4.5.2

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'django'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## django__django-16502

Python 3.11; measured base P2P 0.716s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/django__django-16502"

mkdir -p "$KIT_ROOT/.setup/django__django-16502"

cd "$KIT_ROOT/.setup/django__django-16502"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.11 -y

(
set -e
VACANT_REQUIREMENTS=$(mktemp)
trap 'rm -f -- "$VACANT_REQUIREMENTS"' EXIT
cat <<'EOF_59812759871' > "$VACANT_REQUIREMENTS"
aiosmtpd
asgiref >= 3.7.0
argon2-cffi >= 19.2.0
bcrypt
black
docutils
geoip2; python_version < '3.12'
jinja2 >= 2.11.0
numpy; python_version < '3.12'
Pillow >= 6.2.1; sys.platform != 'win32' or python_version < '3.12'
pylibmc; sys.platform != 'win32'
pymemcache >= 3.4.0
pywatchman; sys.platform != 'win32'
PyYAML
redis >= 3.4.0
selenium >= 4.8.0
sqlparse >= 0.3.1
tblib >= 1.5.0
tzdata
colorama; sys.platform == 'win32'

EOF_59812759871
micromamba activate "$ENV_PREFIX" && python -m pip install -r "$VACANT_REQUIREMENTS"
)

micromamba activate "$ENV_PREFIX"

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/django__django-16502"

python -m pip install -e .

python -m pip install pytest==7.4.4 pytest-django==4.5.2

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'django'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sympy__sympy-13798

Python 3.9; measured base P2P 1.769s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sympy__sympy-13798"

mkdir -p "$KIT_ROOT/.setup/sympy__sympy-13798"

cd "$KIT_ROOT/.setup/sympy__sympy-13798"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 mpmath flake8 -y

micromamba activate "$ENV_PREFIX"

python -m pip install mpmath==1.3.0 flake8-comprehensions

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sympy__sympy-13798"

python -m pip install -e .

python -m pip install pytest==7.4.4 py==1.10.0

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sympy'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sympy__sympy-17630

Python 3.9; measured base P2P 1.222s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sympy__sympy-17630"

mkdir -p "$KIT_ROOT/.setup/sympy__sympy-17630"

cd "$KIT_ROOT/.setup/sympy__sympy-17630"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 mpmath flake8 -y

micromamba activate "$ENV_PREFIX"

python -m pip install mpmath==1.3.0 flake8-comprehensions

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sympy__sympy-17630"

python -m pip install -e .

python -m pip install pytest==7.4.4 py==1.10.0

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sympy'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## django__django-11820

Python 3.6; measured base P2P 1.117s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/django__django-11820"

mkdir -p "$KIT_ROOT/.setup/django__django-11820"

cd "$KIT_ROOT/.setup/django__django-11820"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.6 -y

(
set -e
VACANT_REQUIREMENTS=$(mktemp)
trap 'rm -f -- "$VACANT_REQUIREMENTS"' EXIT
cat <<'EOF_59812759871' > "$VACANT_REQUIREMENTS"
asgiref >= 3.2
argon2-cffi >= 16.1.0
bcrypt
docutils
geoip2
jinja2 >= 2.9.2
numpy
Pillow >= 6.2.0
pylibmc; sys.platform != 'win32'
python-memcached >= 1.59
pytz
pywatchman; sys.platform != 'win32'
PyYAML
selenium
sqlparse >= 0.2.2
tblib >= 1.5.0

EOF_59812759871
micromamba activate "$ENV_PREFIX" && python -m pip install -r "$VACANT_REQUIREMENTS"
)

micromamba activate "$ENV_PREFIX"

python -m pip install pip==21.3.1 setuptools==59.6.0 wheel==0.37.1

cd "$KIT_ROOT/django__django-11820"

python -m pip install -e .

python -m pip install pytest==6.2.5 pytest-django==4.5.2

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'django'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## astropy__astropy-8872

Python 3.9; measured base P2P 1.467s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/astropy__astropy-8872"

mkdir -p "$KIT_ROOT/.setup/astropy__astropy-8872"

cd "$KIT_ROOT/.setup/astropy__astropy-8872"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9  -y

micromamba activate "$ENV_PREFIX"

python -m pip install attrs==23.1.0 exceptiongroup==1.1.3 execnet==2.0.2 hypothesis==6.82.6 iniconfig==2.0.0 numpy==1.25.2 packaging==23.1 pluggy==1.3.0 psutil==5.9.5 pyerfa==2.0.0.3 pytest-arraydiff==0.5.0 pytest-astropy-header==0.2.2 pytest-astropy==0.10.0 pytest-cov==4.1.0 pytest-doctestplus==1.0.0 pytest-filter-subpackage==0.1.2 pytest-mock==3.11.1 pytest-openfiles==0.5.0 pytest-remotedata==0.4.0 pytest-xdist==3.3.1 pytest==7.4.0 PyYAML==6.0.1 setuptools==68.0.0 sortedcontainers==2.4.0 tomli==2.0.1

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/astropy__astropy-8872"

python -m pip install -e .[test] --verbose

python -m pip install pytest==7.4.4

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'astropy'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sphinx-doc__sphinx-8638

Python 3.9; measured base P2P 1.567s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sphinx-doc__sphinx-8638"

mkdir -p "$KIT_ROOT/.setup/sphinx-doc__sphinx-8638"

cd "$KIT_ROOT/.setup/sphinx-doc__sphinx-8638"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9  -y

micromamba activate "$ENV_PREFIX"

python -m pip install tox==4.16.0 tox-current-env==0.0.11 Jinja2==3.0.3

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sphinx-doc__sphinx-8638"

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

python -m pip install pytest==7.4.4 roman==4.1

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sphinx'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sympy__sympy-21596

Python 3.9; measured base P2P 3.641s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sympy__sympy-21596"

mkdir -p "$KIT_ROOT/.setup/sympy__sympy-21596"

cd "$KIT_ROOT/.setup/sympy__sympy-21596"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 mpmath flake8 -y

micromamba activate "$ENV_PREFIX"

python -m pip install mpmath==1.3.0 flake8-comprehensions

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sympy__sympy-21596"

python -m pip install -e .

python -m pip install pytest==7.4.4 py==1.10.0

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sympy'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## django__django-15022

Python 3.9; measured base P2P 1.368s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/django__django-15022"

mkdir -p "$KIT_ROOT/.setup/django__django-15022"

cd "$KIT_ROOT/.setup/django__django-15022"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 -y

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
micromamba activate "$ENV_PREFIX" && python -m pip install -r "$VACANT_REQUIREMENTS"
)

micromamba activate "$ENV_PREFIX"

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/django__django-15022"

python -m pip install -e .

python -m pip install pytest==7.4.4 pytest-django==4.5.2

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'django'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## pydata__xarray-7229

Python 3.10; measured base P2P 7.244s; timeout 120s.

```bash

export PYTHONNOUSERSITE=1

ENV_PREFIX="$KIT_ROOT/.envs/pydata__xarray-7229"

mkdir -p "$KIT_ROOT/.setup/pydata__xarray-7229"

cd "$KIT_ROOT/.setup/pydata__xarray-7229"

cat <<'EOF_59812759871' > environment.yml
name: testbed
channels:
  - conda-forge
  - nodefaults
dependencies:
  - aiobotocore
  - boto3
  - bottleneck
  - cartopy
  - cdms2
  - cftime
  - dask-core
  - distributed
  - flox
  - fsspec!=2021.7.0
  - h5netcdf
  - h5py
  - hdf5
  - hypothesis
  - iris
  - lxml  # Optional dep of pydap
  - matplotlib-base
  - nc-time-axis
  - netcdf4
  - numba
  - numbagg
  - numexpr
  - numpy<1.24
  - packaging
  - pandas
  - pint
  - pip
  - pooch
  - pre-commit
  - pseudonetcdf
  - pydap
  - pytest
  - pytest-cov
  - pytest-env
  - pytest-xdist
  - pytest-timeout
  - rasterio
  - scipy
  - seaborn
  - sparse
  - toolz
  - typing_extensions
  - zarr

EOF_59812759871

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.10 -y

micromamba env update -p "$ENV_PREFIX" -f environment.yml

rm environment.yml

micromamba activate "$ENV_PREFIX"

python -m pip install numpy==1.23.0 packaging==23.1 pandas==1.5.3 pytest==7.4.0 python-dateutil==2.8.2 pytz==2023.3 six==1.16.0 scipy==1.11.1 setuptools==68.0.0 dask==2022.8.1

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/pydata__xarray-7229"

python -m pip install -e .

python -m pip install pytest==7.4.4

python -m pip install numpy==1.23.0 packaging==23.1 pandas==1.5.3 pytest==7.4.0 python-dateutil==2.8.2 pytz==2023.3 six==1.16.0 scipy==1.11.1 setuptools==68.0.0 dask==2022.8.1

python -m pip install "exceptiongroup==1.1.3"

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'xarray'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## django__django-11477

Python 3.6; measured base P2P 1.166s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/django__django-11477"

mkdir -p "$KIT_ROOT/.setup/django__django-11477"

cd "$KIT_ROOT/.setup/django__django-11477"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.6 -y

(
set -e
VACANT_REQUIREMENTS=$(mktemp)
trap 'rm -f -- "$VACANT_REQUIREMENTS"' EXIT
cat <<'EOF_59812759871' > "$VACANT_REQUIREMENTS"
asgiref ~= 3.2
argon2-cffi >= 16.1.0
bcrypt
docutils
geoip2
jinja2 >= 2.9.2
numpy
Pillow != 5.4.0
pylibmc; sys.platform != 'win32'
python-memcached >= 1.59
pytz
pywatchman; sys.platform != 'win32'
PyYAML
selenium
sqlparse >= 0.2.2
tblib >= 1.5.0

EOF_59812759871
micromamba activate "$ENV_PREFIX" && python -m pip install -r "$VACANT_REQUIREMENTS"
)

micromamba activate "$ENV_PREFIX"

python -m pip install pip==21.3.1 setuptools==59.6.0 wheel==0.37.1

cd "$KIT_ROOT/django__django-11477"

python -m pip install -e .

python -m pip install pytest==6.2.5 pytest-django==4.5.2

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'django'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## django__django-11734

Python 3.6; measured base P2P 2.068s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/django__django-11734"

mkdir -p "$KIT_ROOT/.setup/django__django-11734"

cd "$KIT_ROOT/.setup/django__django-11734"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.6 -y

(
set -e
VACANT_REQUIREMENTS=$(mktemp)
trap 'rm -f -- "$VACANT_REQUIREMENTS"' EXIT
cat <<'EOF_59812759871' > "$VACANT_REQUIREMENTS"
asgiref ~= 3.2
argon2-cffi >= 16.1.0
bcrypt
docutils
geoip2
jinja2 >= 2.9.2
numpy
Pillow != 5.4.0
pylibmc; sys.platform != 'win32'
python-memcached >= 1.59
pytz
pywatchman; sys.platform != 'win32'
PyYAML
selenium
sqlparse >= 0.2.2
tblib >= 1.5.0

EOF_59812759871
micromamba activate "$ENV_PREFIX" && python -m pip install -r "$VACANT_REQUIREMENTS"
)

micromamba activate "$ENV_PREFIX"

python -m pip install pip==21.3.1 setuptools==59.6.0 wheel==0.37.1

cd "$KIT_ROOT/django__django-11734"

python -m pip install -e .

python -m pip install pytest==6.2.5 pytest-django==4.5.2

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'django'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## django__django-14034

Python 3.8; measured base P2P 0.716s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/django__django-14034"

mkdir -p "$KIT_ROOT/.setup/django__django-14034"

cd "$KIT_ROOT/.setup/django__django-14034"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.8 -y

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
redis >= 3.0.0
selenium
sqlparse >= 0.2.2
tblib >= 1.5.0
tzdata
colorama; sys.platform == 'win32'

EOF_59812759871
micromamba activate "$ENV_PREFIX" && python -m pip install -r "$VACANT_REQUIREMENTS"
)

micromamba activate "$ENV_PREFIX"

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/django__django-14034"

python -m pip install -e .

python -m pip install pytest==7.4.4 pytest-django==4.5.2

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'django'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## matplotlib__matplotlib-21568

Python 3.8; measured base P2P 3.222s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/matplotlib__matplotlib-21568"

mkdir -p "$KIT_ROOT/.setup/matplotlib__matplotlib-21568"

cd "$KIT_ROOT/.setup/matplotlib__matplotlib-21568"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.8 -y

(
set -e
VACANT_REQUIREMENTS=$(mktemp)
trap 'rm -f -- "$VACANT_REQUIREMENTS"' EXIT
cat <<'EOF_59812759871' > "$VACANT_REQUIREMENTS"
sphinx>=1.8.1,!=2.0.0,<4.3.0
colorspacious
ipython
ipywidgets
numpydoc>=0.8
packaging>=20
pyparsing<3.0.0
mpl-sphinx-theme
sphinxcontrib-svg2pdfconverter>=1.1.0
sphinx-gallery>=0.10
sphinx-copybutton
sphinx-panels
scipy


certifi
coverage
pyparsing<3.0.0
pytest!=4.6.0,!=5.4.0
pytest-cov
pytest-rerunfailures
pytest-timeout
pytest-xdist
python-dateutil
tornado


ipykernel
nbconvert!=6.0.0,!=6.0.1
nbformat!=5.0.0,!=5.0.1
pandas!=0.25.0
pikepdf
pytz
pywin32; sys.platform == 'win32'


flake8>=3.8
pydocstyle>=5.1.0
flake8-docstrings>=1.4.0


EOF_59812759871
micromamba activate "$ENV_PREFIX" && python -m pip install -r "$VACANT_REQUIREMENTS"
)

micromamba activate "$ENV_PREFIX"

python -m pip install pytest ipython

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/matplotlib__matplotlib-21568"

micromamba install -c conda-forge -p "$ENV_PREFIX" -y graphviz ghostscript

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

python -m pip install "pandas<2" "setuptools-scm<8"

python -m pip install pytest ipython

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

QHULL_URL="https://codeload.github.com/qhull/qhull/tar.gz/refs/tags/2020.2"

QHULL_SHA256="59356b229b768e6e2b09a701448bfa222c37b797a84f87f864f97462d8dbc7c5"

QHULL_TAR="$VACANT_BUILD_TMP/qhull-2020-src-8.0.2.tgz"

QHULL_BUILD_DIR="$PWD/build"

curl --fail --location --proto "=https" --tlsv1.2 --output "$QHULL_TAR" "$QHULL_URL" || exit 1

mkdir -p "$QHULL_BUILD_DIR"

python -I -c 'import hashlib,pathlib,sys; actual=hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest(); sys.exit(0 if actual == sys.argv[2] else "Qhull sha256 mismatch")' "$QHULL_TAR" "$QHULL_SHA256" || exit 1

tar -xvzf "$QHULL_TAR" -C "$QHULL_BUILD_DIR"

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'matplotlib'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## django__django-15695

Python 3.9; measured base P2P 1.769s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/django__django-15695"

mkdir -p "$KIT_ROOT/.setup/django__django-15695"

cd "$KIT_ROOT/.setup/django__django-15695"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 -y

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
micromamba activate "$ENV_PREFIX" && python -m pip install -r "$VACANT_REQUIREMENTS"
)

micromamba activate "$ENV_PREFIX"

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/django__django-15695"

python -m pip install -e .

python -m pip install pytest==7.4.4 pytest-django==4.5.2

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'django'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sympy__sympy-18763

Python 3.9; measured base P2P 2.621s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sympy__sympy-18763"

mkdir -p "$KIT_ROOT/.setup/sympy__sympy-18763"

cd "$KIT_ROOT/.setup/sympy__sympy-18763"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 mpmath flake8 -y

micromamba activate "$ENV_PREFIX"

python -m pip install mpmath==1.3.0 flake8-comprehensions

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sympy__sympy-18763"

python -m pip install -e .

python -m pip install pytest==7.4.4 py==1.10.0

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sympy'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## pytest-dev__pytest-5840

Python 3.9; measured base P2P 1.218s; timeout 120s.

```bash

export SETUPTOOLS_SCM_PRETEND_VERSION=5.1

ENV_PREFIX="$KIT_ROOT/.envs/pytest-dev__pytest-5840"

mkdir -p "$KIT_ROOT/.setup/pytest-dev__pytest-5840"

cd "$KIT_ROOT/.setup/pytest-dev__pytest-5840"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9  -y

micromamba activate "$ENV_PREFIX"

python -m pip install atomicwrites==1.4.1 attrs==23.1.0 more-itertools==10.1.0 packaging==23.1 pluggy==0.13.1 py==1.11.0 wcwidth==0.2.6

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/pytest-dev__pytest-5840"

python -m pip install -e .

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'pytest'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## astropy__astropy-13977

Python 3.9; measured base P2P 2.169s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/astropy__astropy-13977"

mkdir -p "$KIT_ROOT/.setup/astropy__astropy-13977"

cd "$KIT_ROOT/.setup/astropy__astropy-13977"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9  -y

micromamba activate "$ENV_PREFIX"

python -m pip install attrs==23.1.0 exceptiongroup==1.1.3 execnet==2.0.2 hypothesis==6.82.6 iniconfig==2.0.0 numpy==1.25.2 packaging==23.1 pluggy==1.3.0 psutil==5.9.5 pyerfa==2.0.0.3 pytest-arraydiff==0.5.0 pytest-astropy-header==0.2.2 pytest-astropy==0.10.0 pytest-cov==4.1.0 pytest-doctestplus==1.0.0 pytest-filter-subpackage==0.1.2 pytest-mock==3.11.1 pytest-openfiles==0.5.0 pytest-remotedata==0.4.0 pytest-xdist==3.3.1 pytest==7.4.0 PyYAML==6.0.1 setuptools==68.0.0 sortedcontainers==2.4.0 tomli==2.0.1

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/astropy__astropy-13977"

sed -i 's/requires = \["setuptools",/requires = \["setuptools==68.0.0",/' pyproject.toml

python -m pip install "Cython==0.29.30" "extension-helpers==1.2.0" "setuptools-scm<8"

python setup.py build_ext --inplace --force

python -m pip install --no-build-isolation -e .[test] --verbose

python -m pip install pytest==7.4.4

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'astropy'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## pytest-dev__pytest-10356

Python 3.9; measured base P2P 1.818s; timeout 120s.

```bash

export SETUPTOOLS_SCM_PRETEND_VERSION=7.2

ENV_PREFIX="$KIT_ROOT/.envs/pytest-dev__pytest-10356"

mkdir -p "$KIT_ROOT/.setup/pytest-dev__pytest-10356"

cd "$KIT_ROOT/.setup/pytest-dev__pytest-10356"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9  -y

micromamba activate "$ENV_PREFIX"

python -m pip install attrs==23.1.0 iniconfig==2.0.0 packaging==23.1 pluggy==0.13.1 py==1.11.0 tomli==2.0.1

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/pytest-dev__pytest-10356"

python -m pip install -e .

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'pytest'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## matplotlib__matplotlib-25479

Python 3.11; measured base P2P 2.936s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/matplotlib__matplotlib-25479"

mkdir -p "$KIT_ROOT/.setup/matplotlib__matplotlib-25479"

cd "$KIT_ROOT/.setup/matplotlib__matplotlib-25479"

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
  - pyparsing>=2.3.1
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
  - sphinx-gallery>=0.12
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
  - nbconvert!=6.0.0,!=6.0.1,!=7.3.0,!=7.3.1
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
  - black

EOF_59812759871

micromamba env create -p "$ENV_PREFIX" --file environment.yml -y

micromamba activate "$ENV_PREFIX" && micromamba install -c conda-forge -p "$ENV_PREFIX" python=3.11 -y

rm environment.yml

micromamba activate "$ENV_PREFIX"

python -m pip install contourpy==1.1.0 cycler==0.11.0 fonttools==4.42.1 ghostscript kiwisolver==1.4.5 numpy==1.25.2 packaging==23.1 pillow==10.0.0 pikepdf pyparsing==3.0.9 python-dateutil==2.8.2 six==1.16.0 setuptools==68.1.2 setuptools-scm==7.1.0 typing-extensions==4.7.1

python -m pip install 'nbconvert[execute]!=6.0.0,!=6.0.1,!=7.3.0,!=7.3.1'

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/matplotlib__matplotlib-25479"

micromamba install -c conda-forge -p "$ENV_PREFIX" -y graphviz ghostscript

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

python -m pip install "pandas<2" "setuptools-scm<8"

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

QHULL_URL="https://codeload.github.com/qhull/qhull/tar.gz/refs/tags/2020.2"

QHULL_SHA256="59356b229b768e6e2b09a701448bfa222c37b797a84f87f864f97462d8dbc7c5"

QHULL_TAR="$VACANT_BUILD_TMP/qhull-2020-src-8.0.2.tgz"

QHULL_BUILD_DIR="$PWD/build"

curl --fail --location --proto "=https" --tlsv1.2 --output "$QHULL_TAR" "$QHULL_URL" || exit 1

mkdir -p "$QHULL_BUILD_DIR"

python -I -c 'import hashlib,pathlib,sys; actual=hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest(); sys.exit(0 if actual == sys.argv[2] else "Qhull sha256 mismatch")' "$QHULL_TAR" "$QHULL_SHA256" || exit 1

tar -xvzf "$QHULL_TAR" -C "$QHULL_BUILD_DIR"

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'matplotlib'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sympy__sympy-20438

Python 3.9; measured base P2P 3.628s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sympy__sympy-20438"

mkdir -p "$KIT_ROOT/.setup/sympy__sympy-20438"

cd "$KIT_ROOT/.setup/sympy__sympy-20438"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 mpmath flake8 -y

micromamba activate "$ENV_PREFIX"

python -m pip install mpmath==1.3.0 flake8-comprehensions

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sympy__sympy-20438"

python -m pip install -e .

python -m pip install pytest==7.4.4 py==1.10.0

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sympy'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## pylint-dev__pylint-7080

Python 3.9; measured base P2P 14.423s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/pylint-dev__pylint-7080"

mkdir -p "$KIT_ROOT/.setup/pylint-dev__pylint-7080"

cd "$KIT_ROOT/.setup/pylint-dev__pylint-7080"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 -y

(
set -e
VACANT_REQUIREMENTS=$(mktemp)
trap 'rm -f -- "$VACANT_REQUIREMENTS"' EXIT
cat <<'EOF_59812759871' > "$VACANT_REQUIREMENTS"
black==22.6.0
flake8==5.0.4
flake8-typing-imports==1.13.0
isort==5.10.1
mypy==0.971

astroid==2.12.13  # Pinned to a specific version for tests
typing-extensions~=4.4
py~=1.11.0
pytest~=7.2
pytest-benchmark~=4.0
pytest-timeout~=2.1
towncrier~=22.8
requests

coveralls~=3.3
coverage~=6.4
pre-commit~=2.20
tbump~=6.9.0
contributors-txt>=0.9.0
pytest-cov~=3.0
pytest-profiling~=1.7
pytest-xdist~=2.5
types-pkg_resources==0.1.3
tox>=3

EOF_59812759871
micromamba activate "$ENV_PREFIX" && python -m pip install -r "$VACANT_REQUIREMENTS"
)

micromamba activate "$ENV_PREFIX"

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/pylint-dev__pylint-7080"

python -m pip install -e .

python -m pip install pytest==7.4.4

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'pylint'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sympy__sympy-13852

Python 3.9; measured base P2P 0.916s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sympy__sympy-13852"

mkdir -p "$KIT_ROOT/.setup/sympy__sympy-13852"

cd "$KIT_ROOT/.setup/sympy__sympy-13852"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 mpmath flake8 -y

micromamba activate "$ENV_PREFIX"

python -m pip install mpmath==1.3.0 flake8-comprehensions

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sympy__sympy-13852"

python -m pip install -e .

python -m pip install pytest==7.4.4 py==1.10.0

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sympy'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## matplotlib__matplotlib-23476

Python 3.11; measured base P2P 9.566s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/matplotlib__matplotlib-23476"

mkdir -p "$KIT_ROOT/.setup/matplotlib__matplotlib-23476"

cd "$KIT_ROOT/.setup/matplotlib__matplotlib-23476"

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
  - cairocffi
  - contourpy>=1.0.1
  - cycler>=0.10.0
  - fonttools>=4.22.0
  - kiwisolver>=1.0.1
  - numpy>=1.19
  - pillow>=6.2
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
  - gtk3
  - ipykernel
  - nbconvert!=6.0.0,!=6.0.1
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

micromamba env create -p "$ENV_PREFIX" --file environment.yml -y

micromamba activate "$ENV_PREFIX" && micromamba install -c conda-forge -p "$ENV_PREFIX" python=3.11 -y

rm environment.yml

micromamba activate "$ENV_PREFIX"

python -m pip install contourpy==1.1.0 cycler==0.11.0 fonttools==4.42.1 ghostscript kiwisolver==1.4.5 numpy==1.25.2 packaging==23.1 pillow==10.0.0 pikepdf pyparsing==3.0.9 python-dateutil==2.8.2 six==1.16.0 setuptools==68.1.2 setuptools-scm==7.1.0 typing-extensions==4.7.1

python -m pip install 'nbconvert[execute]!=6.0.0,!=6.0.1'

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/matplotlib__matplotlib-23476"

micromamba install -c conda-forge -p "$ENV_PREFIX" -y graphviz ghostscript

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

python -m pip install "pandas<2" "setuptools-scm<8"

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

QHULL_URL="https://codeload.github.com/qhull/qhull/tar.gz/refs/tags/2020.2"

QHULL_SHA256="59356b229b768e6e2b09a701448bfa222c37b797a84f87f864f97462d8dbc7c5"

QHULL_TAR="$VACANT_BUILD_TMP/qhull-2020-src-8.0.2.tgz"

QHULL_BUILD_DIR="$PWD/build"

curl --fail --location --proto "=https" --tlsv1.2 --output "$QHULL_TAR" "$QHULL_URL" || exit 1

mkdir -p "$QHULL_BUILD_DIR"

python -I -c 'import hashlib,pathlib,sys; actual=hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest(); sys.exit(0 if actual == sys.argv[2] else "Qhull sha256 mismatch")' "$QHULL_TAR" "$QHULL_SHA256" || exit 1

tar -xvzf "$QHULL_TAR" -C "$QHULL_BUILD_DIR"

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'matplotlib'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## pylint-dev__pylint-8898

Python 3.9; measured base P2P 2.319s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/pylint-dev__pylint-8898"

mkdir -p "$KIT_ROOT/.setup/pylint-dev__pylint-8898"

cd "$KIT_ROOT/.setup/pylint-dev__pylint-8898"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 -y

(
set -e
VACANT_REQUIREMENTS=$(mktemp)
trap 'rm -f -- "$VACANT_REQUIREMENTS"' EXIT
cat <<'EOF_59812759871' > "$VACANT_REQUIREMENTS"
astroid==3.0.0a9  # Pinned to a specific version for tests
typing-extensions~=4.7
py~=1.11.0
pytest~=7.4
pytest-benchmark~=4.0
pytest-timeout~=2.1
towncrier~=23.6
requests
setuptools==41.6.0

coverage~=7.3
tbump~=6.10.0
contributors-txt>=1.0.0
pytest-cov~=4.1
pytest-profiling~=1.7
pytest-xdist~=3.3
six
types-pkg_resources==0.1.3
tox>=3

EOF_59812759871
micromamba activate "$ENV_PREFIX" && python -m pip install -r "$VACANT_REQUIREMENTS"
)

micromamba activate "$ENV_PREFIX"

python -m pip install astroid==3.0.0a6 setuptools

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/pylint-dev__pylint-8898"

python -m pip install -e .

python -m pip install pytest==7.4.4

```


## matplotlib__matplotlib-20676

Python 3.8; measured base P2P 3.485s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/matplotlib__matplotlib-20676"

mkdir -p "$KIT_ROOT/.setup/matplotlib__matplotlib-20676"

cd "$KIT_ROOT/.setup/matplotlib__matplotlib-20676"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.8 -y

(
set -e
VACANT_REQUIREMENTS=$(mktemp)
trap 'rm -f -- "$VACANT_REQUIREMENTS"' EXIT
cat <<'EOF_59812759871' > "$VACANT_REQUIREMENTS"
sphinx>=1.8.1,!=2.0.0,<4.3.0
colorspacious
ipython
ipywidgets
numpydoc>=0.8
packaging>=20
pyparsing<3.0.0
mpl-sphinx-theme
sphinxcontrib-svg2pdfconverter>=1.1.0
sphinx-gallery>=0.10
sphinx-copybutton
sphinx-panels
scipy


certifi
coverage
pyparsing<3.0.0
pytest!=4.6.0,!=5.4.0
pytest-cov
pytest-rerunfailures
pytest-timeout
pytest-xdist
python-dateutil
tornado


ipykernel
nbconvert!=6.0.0,!=6.0.1
nbformat!=5.0.0,!=5.0.1
pandas!=0.25.0
pikepdf
pytz
pywin32; sys.platform == 'win32'


flake8>=3.8
pydocstyle>=5.1.0
flake8-docstrings>=1.4.0


EOF_59812759871
micromamba activate "$ENV_PREFIX" && python -m pip install -r "$VACANT_REQUIREMENTS"
)

micromamba activate "$ENV_PREFIX"

python -m pip install pytest ipython

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/matplotlib__matplotlib-20676"

micromamba install -c conda-forge -p "$ENV_PREFIX" -y graphviz ghostscript

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

python -m pip install "pandas<2" "setuptools-scm<8"

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

QHULL_URL="https://codeload.github.com/qhull/qhull/tar.gz/refs/tags/2020.2"

QHULL_SHA256="59356b229b768e6e2b09a701448bfa222c37b797a84f87f864f97462d8dbc7c5"

QHULL_TAR="$VACANT_BUILD_TMP/qhull-2020-src-8.0.2.tgz"

QHULL_BUILD_DIR="$PWD/build"

curl --fail --location --proto "=https" --tlsv1.2 --output "$QHULL_TAR" "$QHULL_URL" || exit 1

mkdir -p "$QHULL_BUILD_DIR"

python -I -c 'import hashlib,pathlib,sys; actual=hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest(); sys.exit(0 if actual == sys.argv[2] else "Qhull sha256 mismatch")' "$QHULL_TAR" "$QHULL_SHA256" || exit 1

tar -xvzf "$QHULL_TAR" -C "$QHULL_BUILD_DIR"

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'matplotlib'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sphinx-doc__sphinx-7748

Python 3.9; measured base P2P 1.016s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sphinx-doc__sphinx-7748"

mkdir -p "$KIT_ROOT/.setup/sphinx-doc__sphinx-7748"

cd "$KIT_ROOT/.setup/sphinx-doc__sphinx-7748"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9  -y

micromamba activate "$ENV_PREFIX"

python -m pip install tox==4.16.0 tox-current-env==0.0.11 Jinja2==3.0.3

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sphinx-doc__sphinx-7748"

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

python -m pip install pytest==7.4.4 roman==4.1

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sphinx'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sympy__sympy-17318

Python 3.9; measured base P2P 1.877s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sympy__sympy-17318"

mkdir -p "$KIT_ROOT/.setup/sympy__sympy-17318"

cd "$KIT_ROOT/.setup/sympy__sympy-17318"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 mpmath flake8 -y

micromamba activate "$ENV_PREFIX"

python -m pip install mpmath==1.3.0 flake8-comprehensions

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sympy__sympy-17318"

python -m pip install -e .

python -m pip install pytest==7.4.4 py==1.10.0

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sympy'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## scikit-learn__scikit-learn-26194

Python 3.9; measured base P2P 1.567s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/scikit-learn__scikit-learn-26194"

mkdir -p "$KIT_ROOT/.setup/scikit-learn__scikit-learn-26194"

cd "$KIT_ROOT/.setup/scikit-learn__scikit-learn-26194"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 'numpy==1.19.2' 'scipy==1.5.2' 'cython==3.0.10' pytest 'pandas<2.0.0' 'matplotlib<3.9.0' setuptools pytest joblib threadpoolctl -y

micromamba activate "$ENV_PREFIX"

python -m pip install cython setuptools numpy scipy

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/scikit-learn__scikit-learn-26194"

python -m pip install -v --no-use-pep517 --no-build-isolation -e .

python -m pip install pytest==7.4.4

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'scikit-learn'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## scikit-learn__scikit-learn-25102

Python 3.9; measured base P2P 2.169s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/scikit-learn__scikit-learn-25102"

mkdir -p "$KIT_ROOT/.setup/scikit-learn__scikit-learn-25102"

cd "$KIT_ROOT/.setup/scikit-learn__scikit-learn-25102"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 'numpy==1.19.2' 'scipy==1.5.2' 'cython==3.0.10' pytest 'pandas<2.0.0' 'matplotlib<3.9.0' setuptools pytest joblib threadpoolctl -y

micromamba activate "$ENV_PREFIX"

python -m pip install cython setuptools numpy scipy

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/scikit-learn__scikit-learn-25102"

python -m pip install -v --no-use-pep517 --no-build-isolation -e .

python -m pip install pytest==7.4.4

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'scikit-learn'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sphinx-doc__sphinx-9602

Python 3.9; measured base P2P 2.169s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sphinx-doc__sphinx-9602"

mkdir -p "$KIT_ROOT/.setup/sphinx-doc__sphinx-9602"

cd "$KIT_ROOT/.setup/sphinx-doc__sphinx-9602"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9  -y

micromamba activate "$ENV_PREFIX"

python -m pip install tox==4.16.0 tox-current-env==0.0.11 Jinja2==3.0.3

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sphinx-doc__sphinx-9602"

sed -i 's/pytest/pytest -rA/' tox.ini

sed -i 's/Jinja2>=2.3/Jinja2<3.0/' setup.py

sed -i 's/sphinxcontrib-applehelp/sphinxcontrib-applehelp<=1.0.7/' setup.py

sed -i 's/sphinxcontrib-devhelp/sphinxcontrib-devhelp<=1.0.5/' setup.py

sed -i 's/sphinxcontrib-qthelp/sphinxcontrib-qthelp<=1.0.6/' setup.py

sed -i 's/alabaster>=0.7,<0.8/alabaster>=0.7,<0.7.12/' setup.py

sed -i "s/'packaging',/'packaging', 'markupsafe<=2.0.1',/" setup.py

sed -i 's/sphinxcontrib-htmlhelp>=2.0.0/sphinxcontrib-htmlhelp>=2.0.0,<=2.0.4/' setup.py

sed -i 's/sphinxcontrib-serializinghtml>=1.1.5/sphinxcontrib-serializinghtml>=1.1.5,<=1.1.9/' setup.py

python -m pip install -e .[test]

python -m pip install pytest==7.4.4 roman==4.1

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sphinx'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sphinx-doc__sphinx-10435

Python 3.9; measured base P2P 5.526s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sphinx-doc__sphinx-10435"

mkdir -p "$KIT_ROOT/.setup/sphinx-doc__sphinx-10435"

cd "$KIT_ROOT/.setup/sphinx-doc__sphinx-10435"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9  -y

micromamba activate "$ENV_PREFIX"

python -m pip install tox==4.16.0 tox-current-env==0.0.11 Jinja2==3.0.3

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sphinx-doc__sphinx-10435"

sed -i 's/pytest/pytest -rA/' tox.ini

python -m pip install -e .[test]

python -m pip install pytest==7.4.4 roman==4.1

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sphinx'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## astropy__astropy-14182

Python 3.9; measured base P2P 1.116s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/astropy__astropy-14182"

mkdir -p "$KIT_ROOT/.setup/astropy__astropy-14182"

cd "$KIT_ROOT/.setup/astropy__astropy-14182"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9  -y

micromamba activate "$ENV_PREFIX"

python -m pip install attrs==23.1.0 exceptiongroup==1.1.3 execnet==2.0.2 hypothesis==6.82.6 iniconfig==2.0.0 numpy==1.25.2 packaging==23.1 pluggy==1.3.0 psutil==5.9.5 pyerfa==2.0.0.3 pytest-arraydiff==0.5.0 pytest-astropy-header==0.2.2 pytest-astropy==0.10.0 pytest-cov==4.1.0 pytest-doctestplus==1.0.0 pytest-filter-subpackage==0.1.2 pytest-mock==3.11.1 pytest-openfiles==0.5.0 pytest-remotedata==0.4.0 pytest-xdist==3.3.1 pytest==7.4.0 PyYAML==6.0.1 setuptools==68.0.0 sortedcontainers==2.4.0 tomli==2.0.1

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/astropy__astropy-14182"

sed -i 's/requires = \["setuptools",/requires = \["setuptools==68.0.0",/' pyproject.toml

python -m pip install "Cython==0.29.30" "extension-helpers==1.2.0" "setuptools-scm<8"

python setup.py build_ext --inplace --force

python -m pip install --no-build-isolation -e .[test] --verbose

python -m pip install pytest==7.4.4

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'astropy'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sphinx-doc__sphinx-11510

Python 3.9; measured base P2P 0.715s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sphinx-doc__sphinx-11510"

mkdir -p "$KIT_ROOT/.setup/sphinx-doc__sphinx-11510"

cd "$KIT_ROOT/.setup/sphinx-doc__sphinx-11510"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9  -y

micromamba activate "$ENV_PREFIX"

python -m pip install tox==4.16.0 tox-current-env==0.0.11 Jinja2==3.0.3

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sphinx-doc__sphinx-11510"

sed -i 's/pytest/pytest -rA/' tox.ini

micromamba install -c conda-forge -p "$ENV_PREFIX" -y graphviz

python -m pip install -e .[test]

python -m pip install pytest==7.4.4 roman==4.1

```


## sphinx-doc__sphinx-8265

Python 3.9; measured base P2P 0.416s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sphinx-doc__sphinx-8265"

mkdir -p "$KIT_ROOT/.setup/sphinx-doc__sphinx-8265"

cd "$KIT_ROOT/.setup/sphinx-doc__sphinx-8265"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9  -y

micromamba activate "$ENV_PREFIX"

python -m pip install tox==4.16.0 tox-current-env==0.0.11 Jinja2==3.0.3

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sphinx-doc__sphinx-8265"

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

python -m pip install pytest==7.4.4 roman==4.1

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sphinx'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sympy__sympy-21930

Python 3.9; measured base P2P 7.939s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sympy__sympy-21930"

mkdir -p "$KIT_ROOT/.setup/sympy__sympy-21930"

cd "$KIT_ROOT/.setup/sympy__sympy-21930"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 mpmath flake8 -y

micromamba activate "$ENV_PREFIX"

python -m pip install mpmath==1.3.0 flake8-comprehensions

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sympy__sympy-21930"

python -m pip install -e .

python -m pip install pytest==7.4.4 py==1.10.0

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sympy'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sphinx-doc__sphinx-7462

Python 3.9; measured base P2P 1.317s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sphinx-doc__sphinx-7462"

mkdir -p "$KIT_ROOT/.setup/sphinx-doc__sphinx-7462"

cd "$KIT_ROOT/.setup/sphinx-doc__sphinx-7462"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9  -y

micromamba activate "$ENV_PREFIX"

python -m pip install tox==4.16.0 tox-current-env==0.0.11 Jinja2==3.0.3

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sphinx-doc__sphinx-7462"

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

python -m pip install pytest==7.4.4 roman==4.1

python -m pip install tox==4.16.0 tox-current-env==0.0.11 Jinja2==3.0.3

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sphinx'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## mwaskom__seaborn-3187

Python 3.9; measured base P2P 40.678s; timeout 153s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/mwaskom__seaborn-3187"

mkdir -p "$KIT_ROOT/.setup/mwaskom__seaborn-3187"

cd "$KIT_ROOT/.setup/mwaskom__seaborn-3187"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9  -y

micromamba activate "$ENV_PREFIX"

python -m pip install contourpy==1.1.0 cycler==0.11.0 fonttools==4.42.1 importlib-resources==6.0.1 kiwisolver==1.4.5 matplotlib==3.7.2 numpy==1.25.2 packaging==23.1 pandas==2.0.0 pillow==10.0.0 pyparsing==3.0.9 pytest python-dateutil==2.8.2 pytz==2023.3.post1 scipy==1.11.2 six==1.16.0 tzdata==2023.1 zipp==3.16.2

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/mwaskom__seaborn-3187"

python -m pip install -e .[dev]

python -m pip install pytest==7.4.4

```


## psf__requests-6028

Python 3.9; measured base P2P 0.365s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/psf__requests-6028"

mkdir -p "$KIT_ROOT/.setup/psf__requests-6028"

cd "$KIT_ROOT/.setup/psf__requests-6028"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 pytest -y

micromamba activate "$ENV_PREFIX"

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/psf__requests-6028"

python -m pip install .

python -m pip install pytest==7.4.4

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'requests'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## pylint-dev__pylint-4970

Python 3.9; measured base P2P 0.765s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/pylint-dev__pylint-4970"

mkdir -p "$KIT_ROOT/.setup/pylint-dev__pylint-4970"

cd "$KIT_ROOT/.setup/pylint-dev__pylint-4970"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 -y

(
set -e
VACANT_REQUIREMENTS=$(mktemp)
trap 'rm -f -- "$VACANT_REQUIREMENTS"' EXIT
cat <<'EOF_59812759871' > "$VACANT_REQUIREMENTS"
black==21.8b0;python_full_version>="3.6.2"
flake8==3.9.2
isort==5.9.3
mypy==0.910

astroid==2.8.0  # Pinned to a specific version for tests
pytest~=6.2
pytest-benchmark~=3.4

coveralls~=3.2
coverage~=5.5
pre-commit~=2.15;python_full_version>="3.6.2"
tbump~=6.3.2
pyenchant~=3.2
pytest-cov~=2.12
pytest-profiling~=1.7
pytest-xdist~=2.3
types-pkg_resources==0.1.3
types-toml==0.1.5

EOF_59812759871
micromamba activate "$ENV_PREFIX" && python -m pip install -r "$VACANT_REQUIREMENTS"
)

micromamba activate "$ENV_PREFIX"

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/pylint-dev__pylint-4970"

python -m pip install -e .

python -m pip install pytest==7.4.4

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'pylint'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sphinx-doc__sphinx-9229

Python 3.9; measured base P2P 0.966s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sphinx-doc__sphinx-9229"

mkdir -p "$KIT_ROOT/.setup/sphinx-doc__sphinx-9229"

cd "$KIT_ROOT/.setup/sphinx-doc__sphinx-9229"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9  -y

micromamba activate "$ENV_PREFIX"

python -m pip install tox==4.16.0 tox-current-env==0.0.11 Jinja2==3.0.3

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sphinx-doc__sphinx-9229"

sed -i 's/pytest/pytest -rA/' tox.ini

sed -i 's/Jinja2>=2.3/Jinja2<3.0/' setup.py

sed -i 's/sphinxcontrib-applehelp/sphinxcontrib-applehelp<=1.0.7/' setup.py

sed -i 's/sphinxcontrib-devhelp/sphinxcontrib-devhelp<=1.0.5/' setup.py

sed -i 's/sphinxcontrib-qthelp/sphinxcontrib-qthelp<=1.0.6/' setup.py

sed -i 's/alabaster>=0.7,<0.8/alabaster>=0.7,<0.7.12/' setup.py

sed -i "s/'packaging',/'packaging', 'markupsafe<=2.0.1',/" setup.py

grep -q 'sphinxcontrib-htmlhelp>=2.0.0' setup.py && sed -i 's/sphinxcontrib-htmlhelp>=2.0.0/sphinxcontrib-htmlhelp>=2.0.0,<=2.0.4/' setup.py || sed -i 's/sphinxcontrib-htmlhelp/sphinxcontrib-htmlhelp<=2.0.4/' setup.py

grep -q 'sphinxcontrib-serializinghtml>=1.1.5' setup.py && sed -i 's/sphinxcontrib-serializinghtml>=1.1.5/sphinxcontrib-serializinghtml>=1.1.5,<=1.1.9/' setup.py || sed -i 's/sphinxcontrib-serializinghtml/sphinxcontrib-serializinghtml<=1.1.9/' setup.py

python -m pip install -e .[test]

python -m pip install pytest==7.4.4 roman==4.1

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

grep -q 'sphinxcontrib-htmlhelp>=2.0.0' setup.py && sed -i 's/sphinxcontrib-htmlhelp>=2.0.0/sphinxcontrib-htmlhelp>=2.0.0,<=2.0.4/' setup.py || sed -i 's/sphinxcontrib-htmlhelp/sphinxcontrib-htmlhelp<=2.0.4/' setup.py

grep -q 'sphinxcontrib-serializinghtml>=1.1.5' setup.py && sed -i 's/sphinxcontrib-serializinghtml>=1.1.5/sphinxcontrib-serializinghtml>=1.1.5,<=1.1.9/' setup.py || sed -i 's/sphinxcontrib-serializinghtml/sphinxcontrib-serializinghtml<=1.1.9/' setup.py

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sphinx'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sympy__sympy-20428

Python 3.9; measured base P2P 4.422s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sympy__sympy-20428"

mkdir -p "$KIT_ROOT/.setup/sympy__sympy-20428"

cd "$KIT_ROOT/.setup/sympy__sympy-20428"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 mpmath flake8 -y

micromamba activate "$ENV_PREFIX"

python -m pip install mpmath==1.3.0 flake8-comprehensions

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sympy__sympy-20428"

python -m pip install -e .

python -m pip install pytest==7.4.4 py==1.10.0

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sympy'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sympy__sympy-22080

Python 3.9; measured base P2P 2.119s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sympy__sympy-22080"

mkdir -p "$KIT_ROOT/.setup/sympy__sympy-22080"

cd "$KIT_ROOT/.setup/sympy__sympy-22080"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 mpmath flake8 -y

micromamba activate "$ENV_PREFIX"

python -m pip install mpmath==1.3.0 flake8-comprehensions

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sympy__sympy-22080"

python -m pip install -e .

python -m pip install pytest==7.4.4 py==1.10.0

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sympy'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## astropy__astropy-8707

Python 3.9; measured base P2P 1.016s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/astropy__astropy-8707"

mkdir -p "$KIT_ROOT/.setup/astropy__astropy-8707"

cd "$KIT_ROOT/.setup/astropy__astropy-8707"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9  -y

micromamba activate "$ENV_PREFIX"

python -m pip install attrs==23.1.0 exceptiongroup==1.1.3 execnet==2.0.2 hypothesis==6.82.6 iniconfig==2.0.0 numpy==1.25.2 packaging==23.1 pluggy==1.3.0 psutil==5.9.5 pyerfa==2.0.0.3 pytest-arraydiff==0.5.0 pytest-astropy-header==0.2.2 pytest-astropy==0.10.0 pytest-cov==4.1.0 pytest-doctestplus==1.0.0 pytest-filter-subpackage==0.1.2 pytest-mock==3.11.1 pytest-openfiles==0.5.0 pytest-remotedata==0.4.0 pytest-xdist==3.3.1 pytest==7.4.0 PyYAML==6.0.1 setuptools==68.0.0 sortedcontainers==2.4.0 tomli==2.0.1

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/astropy__astropy-8707"

python -m pip install -e .[test] --verbose

python -m pip install pytest==7.4.4

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'astropy'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```


## sympy__sympy-18199

Python 3.9; measured base P2P 11.641s; timeout 120s.

```bash

ENV_PREFIX="$KIT_ROOT/.envs/sympy__sympy-18199"

mkdir -p "$KIT_ROOT/.setup/sympy__sympy-18199"

cd "$KIT_ROOT/.setup/sympy__sympy-18199"

micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9 mpmath flake8 -y

micromamba activate "$ENV_PREFIX"

python -m pip install mpmath==1.3.0 flake8-comprehensions

python -m pip install pip==23.3.2 setuptools==68.1.2 wheel==0.41.2

cd "$KIT_ROOT/sympy__sympy-18199"

python -m pip install -e .

python -m pip install pytest==7.4.4 py==1.10.0

```

Step A base-only native rebuild recipe when compiled sources change:

```bash

SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c 'try:
 from importlib.metadata import version
except ImportError:
 from pkg_resources import get_distribution
 version = lambda name: get_distribution(name).version
print(version('"'"'sympy'"'"'))')"

export SETUPTOOLS_SCM_PRETEND_VERSION

python setup.py build_ext --inplace

```
