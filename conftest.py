import sys
import os

# Allow bare imports like `from db import get_connection` used in vizualizacija modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "vizualizacija"))
