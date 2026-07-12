from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "src"))
    from modeller.doctor import run_doctor

    result = run_doctor(root)
    print(result.format())
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

