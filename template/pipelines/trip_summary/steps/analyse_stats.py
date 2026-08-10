"""Step 2 — Analyse trip statistics.

Reads trips_validated.csv from the run dir, filters by speed bounds,
computes statistics, writes stats.json.
"""


def run(config: dict, step_params: dict, run_context: dict) -> dict:
    import csv
    import json
    import math
    import time
    from pathlib import Path

    t0 = time.monotonic()
    run_dir = Path(run_context["run_dir"])
    validated_csv = run_dir / "trips_validated.csv"
    stats_path = run_dir / "stats.json"

    min_speed = float(step_params.get("min_speed_kmh", 0))
    max_speed = float(step_params.get("max_speed_kmh", 200))

    try:
        with open(validated_csv, newline="") as f:
            rows = list(csv.DictReader(f))

        speeds = [
            float(r["speed"])
            for r in rows
            if min_speed <= float(r["speed"]) <= max_speed
        ]
        vehicle_ids = {r["vehicle_id"] for r in rows}

        if not speeds:
            stats = {"vehicle_count": 0, "trip_count": 0, "mean_speed": None,
                     "max_speed": None, "min_speed": None}
        else:
            stats = {
                "vehicle_count": len(vehicle_ids),
                "trip_count": len(speeds),
                "mean_speed": round(sum(speeds) / len(speeds), 2),
                "max_speed": round(max(speeds), 2),
                "min_speed": round(min(speeds), 2),
                "speed_filter": {"min": min_speed, "max": max_speed},
            }

        with open(stats_path, "w") as f:
            json.dump(stats, f, indent=2)

        return {
            "status": "success",
            "step_id": 2,
            "step_name": "analyse_stats",
            "message": f"Computed stats for {stats['vehicle_count']} vehicles, {stats['trip_count']} trips",
            "duration_s": round(time.monotonic() - t0, 3),
            "cached": False,
            "artifacts": [{"name": "stats_json", "path": "stats.json"}],
            "metrics": stats,
            "error": None,
        }

    except Exception as exc:
        return {
            "status": "failed",
            "step_id": 2,
            "step_name": "analyse_stats",
            "message": f"Error: {exc}",
            "duration_s": round(time.monotonic() - t0, 3),
            "cached": False,
            "artifacts": [],
            "metrics": {},
            "error": {"type": type(exc).__name__, "message": str(exc), "traceback_path": None},
        }
