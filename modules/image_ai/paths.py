"""Resolve writable AI model storage inside PM Tools' configured data dir."""

from pathlib import Path

from core import config


def data(*parts):
    return Path(config.DATA_DIR, *parts)


def find_model(name):
    path = data("models", name)
    return path if path.is_file() else None
