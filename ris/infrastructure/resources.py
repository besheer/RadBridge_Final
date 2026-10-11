"""Package-independent location of versioned RIS resources, never patient files."""
from pathlib import Path

RIS_ROOT = Path(__file__).resolve().parents[1]
