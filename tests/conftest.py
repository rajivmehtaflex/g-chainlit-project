import sys
from pathlib import Path

# Add the app directory to sys.path so tests can import modules from the root
sys.path.insert(0, str(Path(__file__).parent.parent))
