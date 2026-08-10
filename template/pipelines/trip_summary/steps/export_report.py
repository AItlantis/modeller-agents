"""Step 4 — Export HTML summary report and manifest entry.

Reads stats.json (and optionally geo_bbox.json) from the run dir,
writes report.html and manifest.json.
"""


def run(config: dict, step_params: dict, run_context: dict) -> dict:
    import json
    import time
    from pathlib import Path

    t0 = time.monotonic()
    run_dir = Path(run_context["run_dir"])
    run_id = run_context["run_id"]
    pipeline_id = run_context["pipeline_id"]

    stats_path = run_dir / "stats.json"
    report_path = run_dir / "report.html"
    manifest_path = run_dir / "manifest.json"

    try:
        with open(stats_path) as f:
            stats = json.load(f)

        geo_bbox = None
        bbox_path = run_dir / "geo_bbox.json"
        if bbox_path.exists():
            with open(bbox_path) as f:
                geo_bbox = json.load(f)

        # --- HTML report (minimal skeleton) ---
        rows_html = "".join(
            f"<tr><td>{k}</td><td>{v}</td></tr>"
            for k, v in stats.items()
            if not isinstance(v, dict)
        )
        geo_section = ""
        if geo_bbox:
            geo_rows = "".join(
                f"<tr><td>{k}</td><td>{v}</td></tr>"
                for k, v in geo_bbox.items()
            )
            geo_section = f"<h2>Geo Bounding Box</h2><table border='1'>{geo_rows}</table>"

        html = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>Trip Summary — {run_id}</title></head>
<body>
<h1>Trip Summary</h1>
<p>Pipeline: <code>{pipeline_id}</code> | Run: <code>{run_id}</code></p>
<h2>Statistics</h2>
<table border='1'><tr><th>Metric</th><th>Value</th></tr>{rows_html}</table>
{geo_section}
</body></html>"""

        with open(report_path, "w") as f:
            f.write(html)

        # --- Manifest entry (append-only) ---
        manifest_entry = {
            "pipeline_id": pipeline_id,
            "run_id": run_id,
            "produced": [
                {"name": "summary_report", "path": "report.html"},
                {"name": "stats_json", "path": "stats.json"},
            ],
        }
        if geo_bbox:
            manifest_entry["produced"].append({"name": "geo_bbox", "path": "geo_bbox.json"})

        existing = []
        if manifest_path.exists():
            with open(manifest_path) as f:
                existing = json.load(f)
        existing.append(manifest_entry)
        with open(manifest_path, "w") as f:
            json.dump(existing, f, indent=2)

        return {
            "status": "success",
            "step_id": 4,
            "step_name": "export_report",
            "message": f"Report written to report.html; manifest updated",
            "duration_s": round(time.monotonic() - t0, 3),
            "cached": False,
            "artifacts": [
                {"name": "summary_report", "path": "report.html"},
                {"name": "manifest_json", "path": "manifest.json"},
            ],
            "metrics": {"has_geo": geo_bbox is not None},
            "error": None,
        }

    except Exception as exc:
        return {
            "status": "failed",
            "step_id": 4,
            "step_name": "export_report",
            "message": f"Error: {exc}",
            "duration_s": round(time.monotonic() - t0, 3),
            "cached": False,
            "artifacts": [],
            "metrics": {},
            "error": {"type": type(exc).__name__, "message": str(exc), "traceback_path": None},
        }
