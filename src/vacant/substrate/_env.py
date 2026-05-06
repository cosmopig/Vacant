"""Shared `.env` loader used by every real-LLM substrate (D1).

Each substrate calls `_load_dotenv_once()` before reading API key env
vars so the README workflow `echo OPENAI_API_KEY=... > .env` works
without an explicit shell `export`. Cached so repeated `infer()` calls
do not re-walk the filesystem. If `python-dotenv` is not installed the
loader degrades silently and the env var must already be exported.
"""

from __future__ import annotations

_DOTENV_LOADED = False


def _load_dotenv_once() -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True
    try:
        from dotenv import find_dotenv, load_dotenv
    except ImportError:
        return
    path = find_dotenv(usecwd=True)
    if path:
        load_dotenv(path, override=False)


def reset_dotenv_cache_for_tests() -> None:
    """Test-only: clear the once-cache so a fixture can re-trigger
    the loader against a different cwd."""
    global _DOTENV_LOADED
    _DOTENV_LOADED = False
