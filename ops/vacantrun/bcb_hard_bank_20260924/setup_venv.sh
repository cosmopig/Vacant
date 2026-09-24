#!/bin/sh
# BCB-Hard 題庫的 venv（vacant-dev，2026-09-24 實際下過的指令，依序）。
# 版本對齊理由見 README §五；實際解出來的完整版本見 requirements_venv_freeze.txt
# （＝bank_manifest.json 的 gauge.pip_freeze）。
set -eu
ROOT=${1:-/var/tmp/vacant_piext_20260924/bcb}
cd "$ROOT"
/usr/bin/python3 -m venv venv
venv/bin/pip install --no-cache-dir pyarrow==17.0.0            # 讀 parquet（build_bank.py）
venv/bin/pip install --no-cache-dir numpy==1.26.4 pandas==2.1.4 matplotlib==3.8.4 scipy==1.11.4 \
    scikit-learn==1.3.2 seaborn==0.13.2 statsmodels==0.14.1
cat > constraints.txt <<EOF
numpy==1.26.4
pandas==2.1.4
scipy==1.11.4
matplotlib==3.8.4
scikit-learn==1.3.2
seaborn==0.13.2
statsmodels==0.14.1
EOF
venv/bin/pip install --no-cache-dir -c constraints.txt requests==2.31.0 beautifulsoup4==4.8.2 \
    Faker==20.1.0 nltk==3.8 cryptography==38.0.0 psutil==5.9.5 flask==3.0.3 flask_login==0.6.3 \
    flask_wtf==1.2.1 WTForms==3.1.2 Werkzeug==3.0.1 Flask-Mail==0.9.1 pytz==2023.3.post1 \
    python-dateutil==2.9.0 opencv-python-headless==4.9.0.80 Pillow==10.3.0 rsa==4.9 \
    pycryptodome==3.14.1 lxml==4.9.3 wordcloud==1.9.3 geopandas==0.13.2 fiona==1.9.6 shapely==2.0.4 \
    soundfile==0.12.1 librosa==0.10.1 regex openpyxl==3.1.2 xlwt==1.3.0 pyquery==1.4.3 gensim==4.3.3 \
    Levenshtein==0.25.0 python-docx==1.1.0 pytesseract==0.3.10 chardet==5.2.0 requests_mock==1.11.0
# 第一輪量具抓到的兩個缺件：xlrd（pandas 讀 .xls，BigCodeBench/501）、
# pkg_resources（librosa 0.10.1 要，3.12 的 venv 不帶 setuptools）。
venv/bin/pip install --no-cache-dir -c constraints.txt xlrd==2.0.1 "setuptools<81"
# NLTK 資料放在 sys.prefix/nltk_data：離線（沙箱）也找得到。
venv/bin/python -m nltk.downloader -d venv/nltk_data punkt stopwords
