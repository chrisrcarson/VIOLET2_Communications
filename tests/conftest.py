import sys
from pathlib import Path

# add repo root to path (earth_utils.py, VIOLET2.py, etc.)
repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# add tests/unit so test_utils can be imported directly
unit_tests_dir = Path(__file__).parent / "unit"
if str(unit_tests_dir) not in sys.path:
    sys.path.insert(0, str(unit_tests_dir))
