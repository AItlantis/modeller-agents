"""Step 3 — Enrich trips with geo bounding box (optional).

If geo_enrichment is not provided in config, returns status=skipped.
Otherwise reads trips_validated.csv and computes the bounding box.
"""


def run(config: dict, step_params: dict, run_context: dict) -> dict:
    import csv
    import json
    import time
    from pathlib import Path

    t0 = time.monotonic()
    run_dir = Path(run_context["run_dir"])

    # Support both flat config and nested inputs
    inputs = config.get("inputs", config)
    geo_enrichment = inputs.get("geo_enrichment")

    if not geo_enrichment:
        return {
            "status": "skipped",
            "step_id": 3,
            "step_name": "enrich_geo",
            "message": "geo_enrichment not provided — step skipped gracefully",
            "duration_s": round(time.monotonic() - t0, 3),
            "cached": False,
            "artifacts": [],
            "metrics": {},
            "error": None,
        }

    try:
        validated_csv = run_dir / "trips_validated.csv"
        with open(validated_csv, newline="") as f:
            rows = list(csv.DictReader(f))

        xs = [float(r["x"]) for r in rows]
        ys = [float(r["y"]) for r in rows]

        bbox = {
            "min_x": round(min(xs), 4),
            "max_x": round(max(xs), 4),
            "min_y": round(min(ys), 4),
            "max_y": round(max(ys), 4),
            "source": geo_enrichment,
        }

        bbox_path = run_dir / "geo_bbox.json"
        with open(bbox_path, "w") as f:
            json.dump(bbox, f, indent=2)

        return {
            "status": "success",
            "step_id": 3,
            "step_name": "enrich_geo",
            "message": f"Bounding box computed from {len(rows)} trips",
            "duration_s": round(time.monotonic() - t0, 3),
            "cached": False,
            "artifacts": [{"name": "geo_bbox", "path": "geo_bbox.json"}],
            "metrics": {"point_count": len(rows)},
            "error": None,
        }

    except Exception as exc:
        return {
            "status": "failed",
            "step_id": 3,
            "step_name": "enrich_geo",
            "message": f"Error: {exc}",
            "duration_s": round(time.monotonic() - t0, 3),
            "cached": False,
            "artifacts": [],
            "metrics": {},
            "error": {"type": type(exc).__name__, "message": str(exc), "traceback_path": None},
        }
