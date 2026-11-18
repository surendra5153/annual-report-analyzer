"""
Pre-processing library for the ml/ workspace.

The cleaning / labelling code itself lives in backend/app/ml/ so that the
notebooks and the live pipeline run exactly the same rules. The modules in
this package re-export it.
"""
import sys

from ml.paths import BACKEND_DIR

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
