"""Config dataclass for the trip_summary pipeline.

Mirrors the ``inputs:`` declaration in trip_summary.pipeline.yml.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class TripSummaryConfig:
    trips_csv: str
    geo_enrichment: Optional[str] = None

    # ------------------------------------------------------------------
    # Round-trip helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "TripSummaryConfig":
        return cls(
            trips_csv=data["trips_csv"],
            geo_enrichment=data.get("geo_enrichment"),
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "TripSummaryConfig":
        """Load config from a YAML file.

        Accepts either a raw config dict or a nested dict with an
        ``inputs`` key (as produced by the run-config schema).
        """
        import yaml  # import inside function — heavy import rule

        with open(path) as f:
            raw = yaml.safe_load(f)

        inputs = raw.get("inputs", raw)  # support both flat and nested
        return cls.from_dict(inputs)
