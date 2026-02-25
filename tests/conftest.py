"""pytest configuration — add package root to sys.path."""

import sys
import os

# Ensure nmrflow64/ is on the path so `import nmrflow` works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
