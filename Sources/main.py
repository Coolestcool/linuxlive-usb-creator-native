#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Shared macOS / Ubuntu / Debian entry point, including the authorized worker."""
from pathlib import Path
import sys

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(ROOT / "Backend"))
if len(sys.argv) > 1 and sys.argv[1] == "--backend":
    sys.argv.pop(1)
    import os
    if sys.stdout is None: sys.stdout = os.fdopen(os.dup(1), "w", buffering=1)
    if sys.stderr is None: sys.stderr = os.fdopen(os.dup(2), "w", buffering=1)
    import lili
    import json
    try:
        print(json.dumps({"event": "result", "value": lili.main()}, ensure_ascii=False), flush=True)
    except Exception as error:
        print(json.dumps({"event": "error", "message": str(error)}, ensure_ascii=False), flush=True)
        sys.exit(1)
elif len(sys.argv)>2 and sys.argv[1] in ("--self-test","--self-test-scale"):
    from selftest import run
    sys.exit(run(sys.argv[2],sys.argv[1]=="--self-test-scale"))
else:
    from app import main
    main()
