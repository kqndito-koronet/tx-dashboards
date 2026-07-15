"""Provenance envelope for Koronet OS data files.

Every data file in dashboards/data/ should be wrapped in a provenance envelope
so that dashboards can show freshness, trust level, and known gaps. This module
creates and validates those envelopes.

Usage:
    from shared.envelope import wrap, validate

    envelope = wrap(
        data={"rows": [...], "totals": {...}},
        source_description="Snowflake PRODUCTION.ANALYTICS.CONSOLIDATED_TRANSACTION_FEES",
        pulled_by="claude:fee_pacing",
        trust_level="operational",
        known_gaps=["Axerrio uplift (~$19.6K/period) NOT included"],
        freshness_window_hours=168,
    )
    # envelope == {"_meta": {...}, "data": {...}}

    errors = validate(envelope)
    # errors == []  (empty list means valid)
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Trust levels (allowed values)
# ---------------------------------------------------------------------------
TRUST_LEVELS = ("trusted", "needs_validation", "partial", "blocked")

# Alias mapping: architecture doc uses slightly different names in places.
# Accept both the canonical set above AND the architecture-doc set.
_TRUST_ALIASES: dict[str, str] = {
    "verified": "trusted",
    "operational": "needs_validation",
    "estimated": "partial",
    "draft": "needs_validation",
}


def _normalize_trust(level: str) -> str:
    """Accept canonical or aliased trust level; return the canonical form."""
    if level in TRUST_LEVELS:
        return level
    canonical = _TRUST_ALIASES.get(level)
    if canonical:
        return canonical
    raise ValueError(
        f"Unknown trust_level '{level}'. "
        f"Allowed: {TRUST_LEVELS} (aliases: {list(_TRUST_ALIASES.keys())})"
    )


# ---------------------------------------------------------------------------
# Core: wrap data in a provenance envelope
# ---------------------------------------------------------------------------

def wrap(
    data: Any,
    source_description: str,
    pulled_by: str,
    trust_level: str,
    known_gaps: list[str] | None = None,
    freshness_window_hours: int = 24,
    *,
    dataset: str | None = None,
    version: int = 1,
    query_hash: str | None = None,
    notes: str | None = None,
    row_count: int | None = None,
    schema_version: str | None = None,
) -> dict:
    """Wrap a data payload in a provenance envelope.

    Parameters
    ----------
    data : any
        The actual payload (dict, list, whatever the dashboard expects).
    source_description : str
        Full path / name of the data source (table, API, etc.).
    pulled_by : str
        Who or what pulled the data. Convention: "claude:<skill>" or "manual:<person>".
    trust_level : str
        One of: "trusted", "needs_validation", "partial", "blocked".
        Aliases accepted: "verified" -> "trusted", "operational" -> "needs_validation",
        "estimated" -> "partial", "draft" -> "needs_validation".
    known_gaps : list[str], optional
        Explicit list of what is NOT in this data. Defaults to [].
    freshness_window_hours : int, optional
        Hours before data is considered stale. Default 24.
    dataset : str, optional
        Machine-readable name (e.g., "tx_fees"). Optional metadata.
    version : int, optional
        Schema version number. Default 1.
    query_hash : str, optional
        SHA256 of the SQL query, for auditing.
    notes : str, optional
        Human-readable context string.
    row_count : int, optional
        Row count from the source, for sanity checking.
    schema_version : str, optional
        Date string for when the payload schema last changed.

    Returns
    -------
    dict
        {"_meta": {...}, "data": <data>}
    """
    canonical_trust = _normalize_trust(trust_level)

    meta: dict[str, Any] = {
        "pulled_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pulled_by": pulled_by,
        "trust_level": canonical_trust,
        "known_gaps": known_gaps if known_gaps is not None else [],
        "freshness_window_hours": freshness_window_hours,
        "source": source_description,
    }

    # Optional fields -- only include if provided
    if dataset is not None:
        meta["dataset"] = dataset
    if version != 1:
        meta["version"] = version
    if query_hash is not None:
        meta["query_hash"] = query_hash
    if notes is not None:
        meta["notes"] = notes
    if row_count is not None:
        meta["row_count"] = row_count
    if schema_version is not None:
        meta["schema_version"] = schema_version

    return {
        "_meta": meta,
        "data": data,
    }


# ---------------------------------------------------------------------------
# Validation: check that an envelope has the required fields
# ---------------------------------------------------------------------------

_REQUIRED_META_FIELDS = {
    "pulled_at": str,
    "pulled_by": str,
    "trust_level": str,
    "known_gaps": list,
    "freshness_window_hours": (int, float),
    "source": str,
}


def validate(envelope: dict) -> list[str]:
    """Validate an envelope dict. Returns a list of error strings (empty = valid).

    This is intentionally lenient -- it checks structure, not business rules.
    Dashboards should still render even with a few validation warnings.
    """
    errors: list[str] = []

    if not isinstance(envelope, dict):
        return ["Envelope is not a dict"]

    if "_meta" not in envelope:
        errors.append("Missing '_meta' key")
    if "data" not in envelope:
        errors.append("Missing 'data' key")

    if "_meta" in envelope:
        meta = envelope["_meta"]
        if not isinstance(meta, dict):
            errors.append("'_meta' is not a dict")
        else:
            for field, expected_type in _REQUIRED_META_FIELDS.items():
                if field not in meta:
                    errors.append(f"_meta missing required field '{field}'")
                elif not isinstance(meta[field], expected_type):
                    errors.append(
                        f"_meta.{field} has wrong type: "
                        f"expected {expected_type}, got {type(meta[field]).__name__}"
                    )
            # Check trust_level value
            if "trust_level" in meta and isinstance(meta["trust_level"], str):
                if meta["trust_level"] not in TRUST_LEVELS:
                    # Accept aliases too
                    if meta["trust_level"] not in _TRUST_ALIASES:
                        errors.append(
                            f"_meta.trust_level '{meta['trust_level']}' is not a "
                            f"recognized value. Allowed: {TRUST_LEVELS}"
                        )

    return errors


# ---------------------------------------------------------------------------
# Utility: check if data is stale
# ---------------------------------------------------------------------------

def is_stale(envelope: dict) -> bool:
    """Return True if the envelope's data is past its freshness window."""
    meta = envelope.get("_meta", {})
    pulled_at_str = meta.get("pulled_at")
    window = meta.get("freshness_window_hours", 24)

    if not pulled_at_str:
        return True  # No timestamp = stale by default

    try:
        pulled_at = datetime.fromisoformat(pulled_at_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return True

    now = datetime.now(timezone.utc)
    age_hours = (now - pulled_at).total_seconds() / 3600
    return age_hours > window


def age_hours(envelope: dict) -> float | None:
    """Return the age of the data in hours, or None if unparseable."""
    meta = envelope.get("_meta", {})
    pulled_at_str = meta.get("pulled_at")
    if not pulled_at_str:
        return None
    try:
        pulled_at = datetime.fromisoformat(pulled_at_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return (datetime.now(timezone.utc) - pulled_at).total_seconds() / 3600


# ---------------------------------------------------------------------------
# Utility: read/write envelope JSON files
# ---------------------------------------------------------------------------

def read_envelope(path: str | Path) -> dict:
    """Read a JSON file and return the envelope dict.

    If the file is a bare data payload (no _meta), wraps it in a minimal
    envelope for backward compatibility.
    """
    path = Path(path)
    raw = json.loads(path.read_text())

    if isinstance(raw, dict) and "_meta" in raw and "data" in raw:
        return raw

    # Legacy file -- bare payload with no envelope.
    # Wrap it so downstream code can treat it uniformly.
    return {
        "_meta": {
            "pulled_at": "unknown",
            "pulled_by": "unknown",
            "trust_level": "needs_validation",
            "known_gaps": ["Legacy file -- no provenance metadata"],
            "freshness_window_hours": 24,
            "source": f"file:{path.name} (no envelope)",
        },
        "data": raw,
    }


def write_envelope(envelope: dict, path: str | Path, *, indent: int = 2) -> None:
    """Write an envelope dict to a JSON file."""
    path = Path(path)
    errors = validate(envelope)
    if errors:
        import warnings
        warnings.warn(
            f"Writing envelope with validation errors: {errors}",
            stacklevel=2,
        )
    path.write_text(json.dumps(envelope, indent=indent, ensure_ascii=False) + "\n")
