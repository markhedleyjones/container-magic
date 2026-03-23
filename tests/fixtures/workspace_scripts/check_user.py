#!/usr/bin/env python3
"""Print current user identity."""
import os
import pwd

entry = pwd.getpwuid(os.getuid())
print(f"uid={os.getuid()}")
print(f"user={entry.pw_name}")
print("user_ok")
