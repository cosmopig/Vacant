"""statepaths — Vacant 自己的狀態目錄在哪（收件口與 adapters 共用，不互相 import）。

這支在架構裡承重什麼：`flow.submit` 要把這些目錄排除在成果之外；`adapters/run.py` 要
不複製它們、不把它們算進逃逸量具。兩邊用同一份定義，免得一邊改了一邊沒改。
"""
from __future__ import annotations

import os
import pathlib


def state_dir() -> pathlib.Path:
    base = os.environ.get("VACANT_HOME")
    return (pathlib.Path(base).expanduser() if base else pathlib.Path.home() / ".vacant")


def work_dir() -> pathlib.Path:
    env = os.environ.get("VACANT_WORK")
    if env:
        return pathlib.Path(env).expanduser()
    st = state_dir()
    return st.parent / (st.name + "-work")


def state_dirs() -> list[pathlib.Path]:
    return [state_dir().resolve(), work_dir().resolve()]
