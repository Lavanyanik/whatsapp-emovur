"""pytest configuration that ensures the project root is on sys.path.

This allows all test modules to use ``from app import ...`` style imports
without relying on sitecustomize.py being loaded at interpreter startup.
"""

import sys
from pathlib import Path

# This file is at: .../whatapp_emovur/app/tests/conftest.py
# Project root is: .../whatapp_emovur  (parent of the parent of app)
# The "app" package is at .../whatapp_emovur/app/
# So we need .../whatapp_emovur/ on sys.path for "from app.config import ..."
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

