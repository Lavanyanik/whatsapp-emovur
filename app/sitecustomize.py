"""Test/CI helper.

Ensures the project root is present on sys.path so imports like
`import app.main` work when running `uvicorn app.main:app`.

This does not alter runtime/business logic.
"""

import sys
from pathlib import Path

# .../whatapp_emovur/app/sitecustomize.py -> .../whatapp_emovur
# Add the directory that contains the "app" package to sys.path.
# When running from .../whatapp_emovur/app, PROJECT_ROOT should be .../whatapp_emovur.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Also add the current app directory so imports like "import main" and
# "import routes.*" remain resolvable.
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


