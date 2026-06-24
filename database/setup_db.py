"""
Run this first if you want to create or repair the MySQL database manually:

    python database/setup_db.py
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.schema import ensure_schema


def setup():
    return ensure_schema(verbose=True)


if __name__ == "__main__":
    setup()
