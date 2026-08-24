import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VENV_PYTHON = os.path.join(_ROOT, "venv", "bin", "python")

def ensure_venv():
    """If executed by global system python, re-exec with project's venv python interpreter."""
    if os.path.exists(_VENV_PYTHON) and os.path.realpath(sys.executable) != os.path.realpath(_VENV_PYTHON):
        os.execv(_VENV_PYTHON, [_VENV_PYTHON] + sys.argv)

ensure_venv()
