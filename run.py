"""Run from a fresh checkout without pip install."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from agentic_rag.server import main

if __name__ == "__main__":
    main()
