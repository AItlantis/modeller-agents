"""Step 1 — Acquire and validate trips from CSV.

Validates that the input CSV has the required columns, copies it to the
run dir as ``trips_validated.csv``, and returns a conformant step-result.
"""


def run(config: dict, step_params: dict, run_context: dict) -> dict:
    import csv
    import hashlib
    import shutil
    import time
    from pathlib import Path

    t0 = time.monotonic()
    run_dir = Path(run_context["run_dir"])
    trips_csv = Path(config.get("trips_csv", config.get("inputs", {}).get("trips_csv", "")))

    required_columns = {"vehicle_id", "t", "x", "y", "speed"}
    out_path = run_dir / "trips_validated.csv"

    try:
        with open(trips_csv, newline="") as f:
            reader = csv.DictReader(f)
            if not required_columns.issubset(set(reader.fieldnames or [])):
                missing = required_columns - set(reader.fieldnames or [])
                return {
                    "status": "failed",
                    "step_id": 1,
                    "step_name": "acquire_trips",
                    "message": f"Missing required columns: {missing}",
                    "duration_s": round(time.monotonic() - t0, 3),
                    "cached": False,
                    "artifacts": [],
                    "metrics": {},
                    "error": {
                        "type": "ValidationError",
                        "message": f"Missing columns: {missing}",
                        "traceback_path": None,
                    },
                }
            rows = list(reader)

        # Compute a cache key from file content
        content_hash = hashlib.md5(open(trips_csv, "rb").read()).hexdigest()[:8]

        # Copy to run dir
        shutil.copy2(trips_csv, out_path)

        return {
            "status": "success",
            "step_id": 1,
            "step_name": "acquire_trips",
            "message": f"Validated {len(rows)} trips from {trips_csv.name}",
            "duration_s": round(time.monotonic() - t0, 3),
            "cached": False,
            "artifacts": [{"name": "trips_validated", "path": "trips_validated.csv"}],
            "metrics": {"row_count": len(rows), "content_hash": content_hash},
            "error": None,
        }

    except FileNotFoundError:
        return {
            "status": "failed",
            "step_id": 1,
            "step_name": "acquire_trips",
            "message": f"File not found: {trips_csv}",
            "duration_s": round(time.monotonic() - t0, 3),
            "cached": False,
            "artifacts": [],
            "metrics": {},
            "error": {
                "type": "FileNotFoundError",
                "message": str(trips_csv),
                "traceback_path": None,
            },
        }
    except Exception as exc:
        return {
            "status": "failed",
            "step_id": 1,
            "step_name": "acquire_trips",
            "message": f"Unexpected error: {exc}",
            "duration_s": round(time.monotonic() - t0, 3),
            "cached": False,
            "artifacts": [],
            "metrics": {},
            "error": {"type": type(exc).__name__, "message": str(exc), "traceback_path": None},
        }
