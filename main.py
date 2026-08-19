"""Compatibility entry point for the production pipeline.

The maintained implementation lives in ``scripts/run_pipeline.py``. Keeping
this tiny wrapper prevents the older prototype in ``src/`` from being used by
accident.
"""

from scripts.run_pipeline import main


if __name__ == "__main__":
    raise SystemExit(main())
