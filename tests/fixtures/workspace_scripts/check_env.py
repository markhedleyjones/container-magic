#!/usr/bin/env python3
"""Verify that an environment variable is set."""
import os
import sys

var_name = sys.argv[1] if len(sys.argv) > 1 else "APP_ENV"
value = os.environ.get(var_name)
if value is None:
    print(f"ERROR: {var_name} not set")
    sys.exit(1)
print(f"{var_name}={value}")
print("env_ok")
