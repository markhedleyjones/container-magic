#!/usr/bin/env python3
"""Verify that a pip-installed package is importable."""
import tomli

print(f"tomli version: {tomli.__version__}")
print("import_ok")
