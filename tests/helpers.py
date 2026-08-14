"""Load top-level scripts as importable modules.

scrape.py, scrape_sidestories.py, and wiki/scripts/upload.py are scripts, not
package modules, so tests import them by path — the same importlib approach
wiki/scripts/build.py already uses.
"""

import importlib.util
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_script(rel_path, module_name):
    """Import a top-level script by file path and return the module."""
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    abs_path = os.path.join(REPO_ROOT, rel_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(abs_path)
    spec = importlib.util.spec_from_file_location(module_name, abs_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
