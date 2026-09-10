"""PyInstaller entry point preserving package import semantics."""

from rotomask_analyzer.app import main

if __name__ == "__main__":
    raise SystemExit(main())
