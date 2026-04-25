from __future__ import annotations

import hashlib
import os
import re
import secrets
import unicodedata
from pathlib import Path


def generate_numeric_otp(length: int = 6) -> str:
    return ''.join(secrets.choice('0123456789') for _ in range(length))


def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def normalize_secret_answer(value: str) -> str:
    normalized = unicodedata.normalize('NFKC', value).strip().lower()
    return re.sub(r'\s+', ' ', normalized)


def safe_relative_path(root: str, absolute_path: str) -> str:
    return str(Path(absolute_path).resolve().relative_to(Path(root).resolve()))


def bytes_to_readable(size: int) -> str:
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f'{value:.2f} {unit}'
        value /= 1024
    return f'{size} B'
