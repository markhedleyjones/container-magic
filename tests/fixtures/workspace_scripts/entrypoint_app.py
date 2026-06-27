#!/usr/bin/env python3
"""Print a marker and any args; verifies the configured entrypoint runs."""

import sys

print("entrypoint_ran")
print(f"args: {' '.join(sys.argv[1:])}")
