"""GET-only client for Testudo's immutable, version-scoped scenario analysis API."""
from __future__ import annotations

import json
import ipaddress
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping


class ScenarioQueryError(RuntimeError):
    """The read-only Testudo scenario query could not be completed safely."""


@dataclass(frozen=True)
class ScenarioQueryConfig:
    base_url: str
    version_id: str
    capability_token: str
    activation: bool = False
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        parsed = urllib.parse.urlsplit(self.base_url.strip())
        if (parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username
                or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("Testudo base_url must be an explicit http(s) origin/path without credentials")
        if parsed.scheme == "http" and not _is_loopback(parsed.hostname):
            raise ValueError("Testudo capability tokens require HTTPS except for loopback development")
        if not self.version_id or len(self.version_id) > 128 or "/" in self.version_id:
            raise ValueError("version_id must be one package-version identifier")
        if self.activation and not self.capability_token:
            raise ValueError("activated scenario queries require a scoped capability token")
        if self.timeout_seconds <= 0 or self.timeout_seconds > 60:
            raise ValueError("timeout_seconds must be between 0 and 60")


class TestudoScenarioQueryClient:
    """Only catalog and section-metrics GET requests are exposed by this client."""

    __test__ = False

    def __init__(self, config: ScenarioQueryConfig, *, opener: Any = urllib.request.urlopen) -> None:
        if not config.activation:
            raise ValueError("scenario query client requires explicit activation=true")
        self.config = config
        self._opener = opener

    def catalog(self) -> Mapping[str, Any]:
        return self._get("catalog")

    def metrics(self, scenario_ids: list[int], intervals: list[int] | None = None) -> Mapping[str, Any]:
        if (not scenario_ids or len(scenario_ids) > 10
                or any(isinstance(value, bool) or not isinstance(value, int) for value in scenario_ids)):
            raise ScenarioQueryError("metrics requires 1 to 10 integer scenario IDs")
        params = {"scids": ",".join(map(str, scenario_ids))}
        if intervals is not None:
            if (len(intervals) > 120
                    or any(isinstance(value, bool) or not isinstance(value, int) for value in intervals)):
                raise ScenarioQueryError("intervals must contain at most 120 integer IDs")
            params["intervals"] = ",".join(map(str, intervals))
        return self._get("metrics", params)

    def subpath_crosswalk(self, scenario_id: int) -> Mapping[str, Any]:
        """Read package-verified Aimsun subpath to path/OD identities."""
        self._validate_scenario_id(scenario_id)
        return self._get_scoped_read(
            f"/api/v1/view/{urllib.parse.quote(self.config.version_id, safe='')}/path-api/subpaths/crosswalk",
            {"scid": str(scenario_id)},
        )

    def od_routes(
        self,
        scenario_id: int,
        origin: int,
        destination: int,
        *,
        vehicle: int | None = None,
        interval: int | None = None,
    ) -> Mapping[str, Any]:
        """Read route assignments for one OD pair from the selected scenario."""
        self._validate_scenario_id(scenario_id)
        self._validate_nonnegative_id(origin, "origin")
        self._validate_nonnegative_id(destination, "destination")
        if vehicle is not None:
            self._validate_nonnegative_id(vehicle, "vehicle")
        if interval is not None:
            self._validate_nonnegative_id(interval, "interval")
        version = urllib.parse.quote(self.config.version_id, safe="")
        endpoint = f"/api/v1/view/{version}/path-api/od/{origin}/{destination}/routes"
        params = {"scid": str(scenario_id)}
        if vehicle is not None:
            params["vehicle"] = str(vehicle)
        if interval is not None:
            params["interval"] = str(interval)
        return self._get_scoped_read(endpoint, params)

    def path_delay(
        self,
        scenario_id: int,
        section_ids: list[int],
        interval: int,
    ) -> Mapping[str, Any]:
        """Read exact-interval delay sum for an ordered path section sequence."""
        self._validate_scenario_id(scenario_id)
        if (not section_ids or len(section_ids) > 500
                or any(isinstance(value, bool) or not isinstance(value, int) or value < 0
                       for value in section_ids)):
            raise ScenarioQueryError("section_ids must contain 1 to 500 non-negative integer IDs")
        self._validate_nonnegative_id(interval, "interval")
        version = urllib.parse.quote(self.config.version_id, safe="")
        endpoint = f"/api/v1/view/{version}/result-api/api/v1/env/kpi/path-delay"
        return self._get_scoped_read(endpoint, {
            "scid": str(scenario_id),
            "section_ids": ",".join(map(str, section_ids)),
            "ent": str(interval),
        })

    def subpath_metrics(
        self,
        scenario_id: int,
        subpath_ids: list[int],
        intervals: list[int],
    ) -> Mapping[str, Any]:
        """Read observed subpath journey-time rows for exact intervals."""
        self._validate_scenario_id(scenario_id)
        if (not subpath_ids or len(subpath_ids) > 1000
                or any(isinstance(value, bool) or not isinstance(value, int) or value < 0
                       for value in subpath_ids)):
            raise ScenarioQueryError("subpath_ids must contain 1 to 1000 non-negative integer IDs")
        if (not intervals or len(intervals) > 120
                or any(isinstance(value, bool) or not isinstance(value, int) or value < 0
                       for value in intervals)):
            raise ScenarioQueryError("intervals must contain 1 to 120 non-negative integer IDs")
        version = urllib.parse.quote(self.config.version_id, safe="")
        endpoint = f"/api/v1/view/{version}/result-api/api/v1/env/kpi/subpath"
        return self._get_scoped_read(endpoint, {
            "scid": str(scenario_id),
            "oids": ",".join(map(str, subpath_ids)),
            "ent_values": ",".join(map(str, intervals)),
            "fields": "journey_time,count",
        })

    def _get(self, endpoint: str, params: Mapping[str, str] | None = None) -> Mapping[str, Any]:
        if endpoint not in {"catalog", "metrics"}:
            raise ScenarioQueryError("unsupported scenario query")
        prefix = self.config.base_url.rstrip("/")
        encoded_version = urllib.parse.quote(self.config.version_id, safe="")
        url = f"{prefix}/api/v1/view/{encoded_version}/scenario-analysis/{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        return self._request(url, require_version_id=True)

    def _get_scoped_read(self, endpoint: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        url = self.config.base_url.rstrip("/") + endpoint + "?" + urllib.parse.urlencode(params)
        return self._request(url, require_version_id=False)

    def _request(self, url: str, *, require_version_id: bool) -> Mapping[str, Any]:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self.config.capability_token}"}
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with self._opener(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise ScenarioQueryError(f"Testudo scenario query returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ScenarioQueryError("Testudo scenario query is unavailable") from exc
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ScenarioQueryError("Testudo returned invalid JSON") from exc
        if (not isinstance(decoded, Mapping)
                or (require_version_id and decoded.get("version_id") != self.config.version_id)
                or (decoded.get("version_id") is not None and decoded.get("version_id") != self.config.version_id)):
            raise ScenarioQueryError("Testudo returned a response for a different package version")
        return decoded

    @staticmethod
    def _validate_scenario_id(scenario_id: int) -> None:
        if isinstance(scenario_id, bool) or not isinstance(scenario_id, int) or scenario_id < 0:
            raise ScenarioQueryError("scenario_id must be a non-negative integer")

    @staticmethod
    def _validate_nonnegative_id(value: int, name: str) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ScenarioQueryError(f"{name} must be a non-negative integer")


def _is_loopback(hostname: str | None) -> bool:
    if not hostname:
        return False
    if hostname.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False
