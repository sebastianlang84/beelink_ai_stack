from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Any


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def write_json(path: str, obj: Any) -> None:
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def write_text(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def env_snapshot() -> str:
    parts = [
        f"platform={platform.platform()}",
        f"python_exe={os.environ.get('PYTHON', '')}",
    ]
    try:
        out = subprocess.check_output(["python", "--version"], stderr=subprocess.STDOUT, text=True).strip()
        parts.append(out)
    except Exception:
        pass
    try:
        out = subprocess.check_output(["pip", "freeze"], stderr=subprocess.STDOUT, text=True).strip()
        parts.append("")
        parts.append("pip freeze:")
        parts.append(out)
    except Exception:
        pass
    return "\n".join(parts) + "\n"

