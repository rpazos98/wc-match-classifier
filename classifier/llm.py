"""
LM Studio integration.

Supports both LM Studio APIs:
  - OpenAI-compatible:  http://localhost:1234/v1
  - LM Studio native:   http://localhost:1234/api/v1  (newer, preferred)

Auto-detects which base path is available.

Provides:
  LMStudioClient.check_status()        → {ok, model}
  LMStudioClient.classify_matches()    → [{match_id, label, score, reasoning}]
  LMStudioClient.explain_match()       → str  (narrative in Spanish)
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any


_HOST       = "http://localhost:1234"
# Prefer OpenAI-compat (/v1) — standard response format {data:[{id}]}
# Fall back to LM Studio native (/api/v1) — format {models:[{key}]}
_API_PATHS  = ["/v1", "/api/v1"]


# ── Low-level HTTP ────────────────────────────────────────────────────────────

def _post(url: str, payload: dict, timeout: int = 120) -> dict:
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _get(url: str, timeout: int = 5) -> dict:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _strip_markdown(text: str) -> str:
    """Remove ```json ... ``` fences that some models add."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        t = "\n".join(inner).strip()
    return t


def _parse_json_array(text: str) -> list[dict]:
    """
    Parse a JSON array from LLM output.
    Falls back to object-by-object extraction when the overall JSON is malformed
    (LLMs sometimes emit invalid syntax like missing braces, stray keys, typos).
    """
    clean = _strip_markdown(text)

    # Happy path
    try:
        result = json.loads(clean)
        if isinstance(result, list):
            return [r for r in result if isinstance(r, dict) and "match_id" in r]
        return []
    except json.JSONDecodeError:
        pass

    # Fallback: walk the string character by character, extract each {...} object
    objects: list[dict] = []
    depth  = 0
    start  = None
    for i, ch in enumerate(clean):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                fragment = clean[start : i + 1]
                try:
                    obj = json.loads(fragment)
                    if isinstance(obj, dict) and "match_id" in obj:
                        objects.append(obj)
                except json.JSONDecodeError:
                    pass
                start = None
    return objects


def _extract_content(resp: dict) -> str:
    """Extract text from an OpenAI-style chat response."""
    return resp["choices"][0]["message"]["content"]


# ── Client ────────────────────────────────────────────────────────────────────

class LMStudioClient:
    def __init__(self, host: str = _HOST) -> None:
        self._host     = host.rstrip("/")
        self._base: str | None = None    # discovered base path
        self._model: str | None = None   # last known model id

    # ── Discovery ─────────────────────────────────────────────────────────────

    def _discover(self) -> tuple[str, str | None]:
        """Return (base_path, model_id) for the first responding API path."""
        for path in _API_PATHS:
            try:
                url  = f"{self._host}{path}/models"
                data = _get(url, timeout=3)
                # OpenAI-compat:    {data: [{id: ...}]}
                # LM Studio native: {models: [{key: ...}]}
                if "data" in data:
                    items = data["data"]
                    model = items[0]["id"] if items else None
                elif "models" in data:
                    items = data["models"]
                    model = (items[0].get("key") or items[0].get("id")) if items else None
                else:
                    model = None
                return path, model
            except Exception:
                continue
        raise ConnectionError("LM Studio not reachable on any known API path")

    def _ensure_base(self) -> str:
        if self._base is None:
            self._base, self._model = self._discover()
        return self._base

    def _get_model(self) -> str | None:
        """
        Return the ID of the model currently loaded in LM Studio.
        Uses the native /api/v1/models endpoint (has `loaded_instances` per model).
        Falls back to None (LM Studio auto-selects) if detection fails.
        """
        try:
            data  = _get(f"{self._host}/api/v1/models", timeout=3)
            for m in data.get("models", []):
                if m.get("loaded_instances"):
                    # native API uses "key", OpenAI compat uses "id"
                    return m.get("key") or m.get("id")
        except Exception:
            pass
        return None

    # ── Chat ──────────────────────────────────────────────────────────────────

    def _chat(
        self,
        messages:        list[dict],
        model:           str | None = None,
        max_tokens:      int = 2048,
        temperature:     float = 0.3,
        response_format: dict | None = None,
    ) -> str:
        base    = self._ensure_base()
        # LM Studio native: POST /api/v1/chat
        # OpenAI-compat:    POST /v1/chat/completions
        if base == "/api/v1":
            chat_path = f"{self._host}{base}/chat"
        else:
            chat_path = f"{self._host}{base}/chat/completions"

        payload: dict[str, Any] = {
            "messages":    messages,
            "temperature": temperature,
            "max_tokens":  max_tokens,
        }
        if model:
            payload["model"] = model
        if response_format:
            payload["response_format"] = response_format
        result = _post(chat_path, payload)
        return _extract_content(result)

    # ── Public API ────────────────────────────────────────────────────────────

    def check_status(self) -> dict:
        """Returns {ok: bool, model: str | None, api_path: str | None, error: str | None}."""
        try:
            base, model = self._discover()
            self._base  = base
            self._model = model
            return {"ok": True, "model": model, "api_path": base}
        except Exception as exc:
            return {"ok": False, "model": None, "api_path": None, "error": str(exc)}

    def classify_matches(self, matches: list[dict], profile: dict) -> list[dict]:
        """
        Ask the LLM to classify a list of matches.

        Each match dict must have:
          match_id, home, away, stage_label, kickoff_local, raw_by_scorer

        profile: {name, team_affinities, favorite_players}

        Returns list of:
          {match_id, label, score, reasoning}

        label ∈ {"Imperdible", "Vale la pena", "Para ver el resumen"}
        score ∈ [0.0, 100.0]
        """
        if not matches:
            return []

        model       = self._get_model()
        affs        = profile.get("team_affinities", {})
        teams_str   = ", ".join(f"{t}({'fav' if v>=0.9 else 'like' if v>=0.5 else 'int'})" for t, v in affs.items()) or "none"
        players_str = ", ".join(profile.get("favorite_players", [])) or "none"

        # JSON schema — model MUST follow this structure
        _SCHEMA = {
            "type": "json_schema",
            "json_schema": {
                "name": "match_classifications",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "results": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "match_id":  {"type": "string"},
                                    "label":     {"type": "string", "enum": ["Imperdible", "Vale la pena", "Para ver el resumen"]},
                                    "score":     {"type": "number"},
                                    "reasoning": {"type": "string"},
                                },
                                "required":              ["match_id", "label", "score", "reasoning"],
                                "additionalProperties":  False,
                            },
                        }
                    },
                    "required":             ["results"],
                    "additionalProperties": False,
                },
            },
        }

        system = (
            "You are a football match classifier. Given a fan's profile and a list "
            "of World Cup 2026 matches with feature scores (0.0–1.0), "
            "classify each match.\n\n"
            "Feature keys:\n"
            "  Favorite Team: 1=their fav team plays, 0=no\n"
            "  Match Stage: 1=Final, 0.25=Groups\n"
            "  Competitive Tension: 1=maximum uncertainty, anyone can win\n"
            "  Form: recent form of the teams\n"
            "  Favorite Player: 1=their favorite player plays\n"
            "  Chaos Potential: 1=open match with many expected goals\n"
            "  Upset Potential: 1=potential for historic upset\n"
            "  Star Power: world-class stars in the match\n"
            "  Same Group: match in the favorite team's group\n"
            "  Narrative: history and rivalry between teams\n"
            "  Time Availability: 1=within fan's available schedule\n\n"
            "score must be float 0.0–100.0. reasoning must be one sentence in English."
        )

        # Batch in groups of 25 to keep prompt+output manageable
        _BATCH = 25
        all_results: list[dict] = []

        for batch_start in range(0, len(matches), _BATCH):
            batch = matches[batch_start : batch_start + _BATCH]
            lines: list[str] = []
            for m in batch:
                raw     = m.get("raw_by_scorer", {})
                raw_str = ", ".join(f"{k}: {v:.2f}" for k, v in raw.items())
                lines.append(
                    f'id="{m["match_id"]}" | {m["home"]} vs {m["away"]} | '
                    f'{m.get("stage_label","")} | {m.get("kickoff_local","")} | [{raw_str}]'
                )

            user = (
                f"Fan profile:\n"
                f"  Favorite teams: {teams_str}\n"
                f"  Favorite players: {players_str}\n\n"
                f"Classify these {len(batch)} matches:\n" + "\n".join(lines)
            )

            raw_content = self._chat(
                [{"role": "system", "content": system},
                 {"role": "user",   "content": user}],
                model=model,
                max_tokens=len(batch) * 100 + 256,
                response_format=_SCHEMA,
            )
            try:
                parsed = json.loads(raw_content)
                all_results.extend(parsed.get("results", []))
            except json.JSONDecodeError:
                # Schema enforcement failed or model ignored it — best-effort extraction
                all_results.extend(_parse_json_array(raw_content))

        return all_results

    def explain_match(self, match: dict, profile: dict) -> str:
        """
        Generate a 2-3 sentence narrative in English explaining why to watch (or skip) a match.

        match dict must have: home, away, stage_label, kickoff_local, venue,
                              label, score, raw_by_scorer
        profile: {name, team_affinities, favorite_players}
        """
        model       = self._get_model()
        affs        = profile.get("team_affinities", {})
        teams_str   = ", ".join(f"{t}({'fav' if v>=0.9 else 'like' if v>=0.5 else 'int'})" for t, v in affs.items()) or "none"
        players_str = ", ".join(profile.get("favorite_players", [])) or "none"

        raw      = match.get("raw_by_scorer", {})
        raw_str  = "\n".join(f"  {k}: {v:.2f}" for k, v in raw.items())

        system = (
            "You are a passionate football commentator. In 2-3 sentences in English, "
            "explain in an entertaining and specific way why a fan should (or shouldn't) watch this match. "
            "Mention teams, tournament stage, and any relevant factors from the fan's profile. "
            "Be direct and passionate. Don't use lists or bullet points."
        )

        user = (
            f"Match: {match.get('home','?')} vs {match.get('away','?')}\n"
            f"Stage: {match.get('stage_label','')}\n"
            f"Local time: {match.get('kickoff_local','')}\n"
            f"Venue: {match.get('venue','')}\n\n"
            f"Model scores (0.0–1.0):\n{raw_str}\n\n"
            f"Fan profile:\n"
            f"  Favorite teams: {teams_str}\n"
            f"  Favorite players: {players_str}\n\n"
            f"Model classification: {match.get('label','')} (score: {match.get('score',0)}/100)\n"
        )

        return self._chat(
            [{"role": "system", "content": system},
             {"role": "user",   "content": user}],
            model=model,
            max_tokens=300,
            temperature=0.6,
        )