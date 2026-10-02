"""GET-independent typed Ollaya decision adapter for scenario selection.

This client makes one bounded ``/api/decide`` request. It never asks Ollaya
to write prose or authorize a viewer action.
"""
from __future__ import annotations

import json
import ipaddress
import math
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping


NO_MATCH_CHOICE = "__no_match__"
MATCH_THRESHOLD = 0.80
MATCH_MARGIN = 0.15


class ScenarioDecisionError(RuntimeError):
    """Ollaya could not return a valid typed scenario decision."""


@dataclass(frozen=True)
class OllayaScenarioConfig:
    base_url: str
    model: str
    api_key: str = ""
    activation: bool = False
    timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        parsed = urllib.parse.urlsplit(self.base_url.strip())
        if (parsed.scheme not in {"http", "https"} or not parsed.netloc
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("Ollaya base_url must be an http(s) origin/path without credentials")
        hostname = parsed.hostname or ""
        try:
            loopback = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            loopback = hostname.casefold() == "localhost"
        if parsed.scheme == "http" and not loopback:
            raise ValueError("Ollaya credentials and decisions require HTTPS except for loopback development")
        if not self.model or len(self.model) > 128:
            raise ValueError("Ollaya model must be a non-empty name of at most 128 characters")
        if self.timeout_seconds <= 0 or self.timeout_seconds > 30:
            raise ValueError("timeout_seconds must be between 0 and 30")


class OllayaScenarioMatcher:
    """Select a catalog candidate only when Ollaya's typed score gate passes."""

    def __init__(self, config: OllayaScenarioConfig, *, opener: Callable[..., Any] = urllib.request.urlopen) -> None:
        if not config.activation:
            raise ValueError("Ollaya scenario matching requires explicit activation=true")
        self.config = config
        self._opener = opener

    def match(self, prompt: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4000:
            raise ValueError("prompt must contain 1 to 4000 characters")
        options, context = self._candidate_payload(candidates)
        payload = {
            "model": self.config.model,
            "state": {"prompt": prompt, "verified_candidates": context},
            "questions": {"scenario": {"type": "choice", "criteria": options}},
        }
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        request = urllib.request.Request(
            f"{self.config.base_url.rstrip('/')}/api/decide",
            data=json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with self._opener(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise ScenarioDecisionError(f"Ollaya returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ScenarioDecisionError("Ollaya scenario matching is unavailable") from exc
        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ScenarioDecisionError("Ollaya returned invalid JSON") from exc
        return self._parse_response(result, options)

    @staticmethod
    def _candidate_payload(candidates: list[dict[str, Any]]) -> tuple[dict[str, str], list[dict[str, Any]]]:
        if not isinstance(candidates, list) or not candidates or len(candidates) > 254:
            raise ValueError("candidates must contain 1 to 254 catalog scenarios")
        options: dict[str, str] = {}
        context = []
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                raise ValueError("each candidate must come from the verified catalog")
            scenario_id = candidate.get("scenario_id")
            if not isinstance(scenario_id, (str, int)) or isinstance(scenario_id, bool):
                raise ValueError("every candidate needs a string or integer scenario_id")
            choice = str(scenario_id)
            if not choice or choice == NO_MATCH_CHOICE or choice in options:
                raise ValueError("candidate scenario IDs must be unique and cannot use the no-match ID")
            name = str(candidate.get("name") or choice)[:160]
            options[choice] = name
            analysis = candidate.get("analysis") if isinstance(candidate.get("analysis"), Mapping) else {}
            interventions = analysis.get("interventions", [])
            if not isinstance(interventions, list):
                interventions = []
            types = [str(item.get("type"))[:48] for item in interventions[:20] if isinstance(item, Mapping)]
            locations = []
            effective_windows = []
            for item in interventions[:20]:
                if not isinstance(item, Mapping):
                    continue
                location = item.get("location")
                if location is not None:
                    rendered = location if isinstance(location, str) else json.dumps(
                        location, ensure_ascii=True, separators=(",", ":"),
                    )
                    locations.append(rendered[:100])
                effective_window = item.get("effective_window")
                if isinstance(effective_window, Mapping):
                    effective_windows.append(json.dumps(
                        effective_window, ensure_ascii=True, separators=(",", ":"),
                    )[:100])
            context.append({
                "scenario_id": choice,
                "name": name,
                "baseline_role": str(analysis.get("baseline_role") or "")[:32],
                "baseline_scenario_id": str(analysis.get("baseline_scenario_id") or "")[:128],
                "intervention_types": list(dict.fromkeys(types))[:6],
                "locations": list(dict.fromkeys(locations))[:3],
                "effective_windows": list(dict.fromkeys(effective_windows))[:3],
                "affected_section_ids": list(dict.fromkeys(
                    str(value)[:64] for item in interventions[:20] if isinstance(item, Mapping)
                    for value in item.get("affected_section_ids", [])[:12]
                ))[:12],
                "affected_path_ids": list(dict.fromkeys(
                    str(value)[:64] for item in interventions[:20] if isinstance(item, Mapping)
                    for value in item.get("affected_path_ids", [])[:12]
                ))[:12],
            })
        options[NO_MATCH_CHOICE] = "None of these scenarios; no existing scenario matches the request"
        if len(json.dumps(context, ensure_ascii=True, separators=(",", ":"))) > 100_000:
            raise ValueError("catalog candidate context exceeds the 100000-byte request limit")
        return options, context

    @staticmethod
    def _parse_response(result: Any, options: Mapping[str, str]) -> dict[str, Any]:
        if (not isinstance(result, Mapping) or result.get("done_reason") != "decide"
                or result.get("state_truncated") is True):
            raise ScenarioDecisionError("Ollaya returned an incomplete typed decision")
        answers = result.get("answers")
        answer = answers.get("scenario") if isinstance(answers, Mapping) else None
        if (not isinstance(answer, Mapping) or answer.get("type") != "choice"
                or answer.get("choice") not in options):
            raise ScenarioDecisionError("Ollaya returned a choice outside the verified catalog")
        probabilities = answer.get("probabilities")
        if isinstance(probabilities, list):
            probabilities = {
                str(item.get("choice")): item.get("probability")
                for item in probabilities if isinstance(item, Mapping)
            }
        if not isinstance(probabilities, Mapping) or set(probabilities) != set(options):
            raise ScenarioDecisionError("Ollaya must return scores for every scenario and no-match")
        scores: dict[str, float] = {}
        for choice, value in probabilities.items():
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(float(value)) or not 0 <= float(value) <= 1):
                raise ScenarioDecisionError("Ollaya returned an invalid scenario score")
            scores[str(choice)] = float(value)
        if not 0.98 <= sum(scores.values()) <= 1.02:
            raise ScenarioDecisionError("Ollaya scenario scores do not form a normalized distribution")
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        top_choice, top_score = ranked[0]
        margin = top_score - ranked[1][1]
        matched = (
            top_choice != NO_MATCH_CHOICE
            and answer.get("choice") == top_choice
            and top_score >= MATCH_THRESHOLD
            and margin >= MATCH_MARGIN
        )
        return {
            "status": "matched" if matched else "ambiguous",
            "available": True,
            "scenario_id": top_choice if matched else None,
            "model_match_score": top_score,
            "runner_up_margin": margin,
            "threshold": MATCH_THRESHOLD,
            "required_margin": MATCH_MARGIN,
            "no_match": top_choice == NO_MATCH_CHOICE,
            "candidates": [
                {"scenario_id": choice, "name": options[choice], "model_match_score": score}
                for choice, score in ranked[:5]
            ],
        }
