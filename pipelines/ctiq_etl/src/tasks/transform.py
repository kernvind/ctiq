"""
Transform task: map raw clinicalTrials.gov v2 JSON → ClinicalTrial models.

The v2 API returns studies as a nested ``protocolSection`` object.
Each helper below extracts one slice of that object and maps it to the
flat BigQuery column names defined in ``models/trial.py``.

Bad records (missing nct_id or unparseable startDate) are skipped and
logged rather than raising, so a single malformed study never aborts a
full-load run.
"""
from __future__ import annotations

import datetime
import json
import logging
import re
from datetime import date
from typing import Any, Optional

from dateutil import parser as du_parser

from src.models.trial import ClinicalTrial, Intervention, Outcome, Reference

logger = logging.getLogger(__name__)


# ── Date parsing ───────────────────────────────────────────────────────────────

_YYYY_MM_RE = re.compile(r"^\d{4}-\d{2}$")
_YYYY_RE = re.compile(r"^\d{4}$")


def _parse_date(value: Any) -> Optional[date]:
    """
    Robustly parse a date value from the API.

    Handles:
      "2024-01-15"          → date(2024, 1, 15)
      "2024-01"             → date(2024, 1, 1)   (first of month)
      "2024"                → date(2024, 1, 1)   (first of year)
      "January 15, 2024"    → date(2024, 1, 15)  (via dateutil)
      {"date": "2024-01-15", ...}                (struct form from API)
      None / ""             → None
    """
    if value is None:
        return None

    # The API sometimes wraps dates in a struct: {"date": "YYYY-MM-DD", "type": "..."}
    if isinstance(value, dict):
        value = value.get("date")
    if not value:
        return None

    s = str(value).strip()

    if _YYYY_MM_RE.match(s):
        return date.fromisoformat(f"{s}-01")
    if _YYYY_RE.match(s):
        return date(int(s), 1, 1)

    try:
        return du_parser.parse(s).date()
    except (ValueError, TypeError):
        logger.debug("Unparseable date string: %r", s)
        return None


# ── Section extractors ─────────────────────────────────────────────────────────

def _get(obj: dict, *keys: str, default: Any = None) -> Any:
    """Safe nested dict getter; returns *default* if any key is missing."""
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key, default)
        if cur is None:
            return default
    return cur


def _extract_references(protocol: dict):
    raw = _get(protocol, "referencesModule", "references", default=[])
    refs = []
    for r in raw or []:
        pmid_raw = r.get("pmid")
        try:
            pmid = int(pmid_raw) if pmid_raw is not None else None
        except (ValueError, TypeError):
            pmid = None
        refs.append(
            {
                'citation': r.get("citation"),
                'type': r.get("type"),
                'pmid': pmid,
            }
        )
    return refs


def _extract_primary_outcomes(protocol: dict):
    raw = _get(protocol, "outcomesModule", "primaryOutcomes", default=[])
    return [
        {
            'measure': o.get("measure"),
            'description': o.get("description"),
            'timeFrame': o.get("timeFrame"),
        }
        for o in (raw or [])
    ]


def _extract_secondary_outcomes(protocol: dict):
    raw = _get(protocol, "outcomesModule", "secondaryOutcomes", default=[])
    return [
        {
            'measure': o.get("measure"),
            'description': o.get("description"),
            'timeFrame': o.get("timeFrame"),
        }
        for o in (raw or [])
    ]


def _extract_interventions(protocol: dict):
    raw = _get(protocol, "armsInterventionsModule", "interventions", default=[])
    return [
        {
            'type': i.get("type"),
            'name': i.get("name"),
            'description': i.get("description"),
        }
        for i in (raw or [])
    ]


def _extract_collaborator_names(protocol: dict) -> list[str]:
    collaborators = _get(protocol, "sponsorCollaboratorsModule", "collaborators", default=[])
    return [c["name"] for c in (collaborators or []) if c.get("name")]


# ── Main transform ─────────────────────────────────────────────────────────────

def transform_study(raw_study: dict):
    """
    Map one raw API study dict to a ``ClinicalTrial`` model.

    Returns ``None`` (and logs a warning) for studies that are missing
    required fields (``nctId`` or ``startDate``).
    """
    protocol: dict = raw_study.get("protocolSection", {})

    # ── Identification ────────────────────────────────────────────────────────
    id_mod = protocol.get("identificationModule", {})
    nct_id: Optional[str] = id_mod.get("nctId")
    if not nct_id:
        logger.warning("Skipping study with no nctId: %s", str(raw_study)[:120])
        return None

    # ── Status / Dates ────────────────────────────────────────────────────────
    status_mod = protocol.get("statusModule", {})
    start_date = _parse_date(_get(status_mod, "startDateStruct"))
    logger.info("Parsed start date for %s: %s", nct_id, start_date)
    if start_date is None:
        start_date = status_mod.get("lastUpdateSubmitDate", None)
        if start_date is None:
            logger.warning("Skipping %s: missing/unparseable startDate", nct_id)
            return None

    last_update = _parse_date(_get(status_mod, "lastUpdatePostDateStruct"))
    if last_update is None:
        # Fall back to today so the NOT NULL constraint is satisfied
        from datetime import date as _date
        last_update = _date.today()
        logger.debug("%s: no lastUpdatePostDate, defaulting to today", nct_id)

    # ── Sponsor / Collaborators ───────────────────────────────────────────────
    sponsor_mod = protocol.get("sponsorCollaboratorsModule", {})
    responsible_party = sponsor_mod.get("responsibleParty", {})

    # ── Design ────────────────────────────────────────────────────────────────
    design_mod = protocol.get("designModule", {})
    design_info = design_mod.get("designInfo", {})
    masking_info = design_info.get("maskingInfo", {})
    enrollment_info = design_mod.get("enrollmentInfo", {})

    # ── Eligibility ───────────────────────────────────────────────────────────
    elig_mod = protocol.get("eligibilityModule", {})

    # ── Description ───────────────────────────────────────────────────────────
    desc_mod = protocol.get("descriptionModule", {})

    return {
    "nct_id": nct_id,
    "lastUpdatePostDate": last_update,
    "startDate": start_date,
    "completionDate": _parse_date(_get(status_mod, "completionDateStruct")),
    "primaryCompletionDate": _parse_date(_get(status_mod, "primaryCompletionDateStruct")),
    "overallStatus": status_mod.get("overallStatus"),

    "officialTitle": id_mod.get("officialTitle"),
    "organization": _get(id_mod, "organization", "fullName"),

    "leadSponsorName": _get(sponsor_mod, "leadSponsor", "name"),
    "leadSponsorCollaborators": _extract_collaborator_names(protocol),
    "investigatorFullName": responsible_party.get("investigatorFullName"),

    "conditionsModule": _get(protocol, "conditionsModule", "conditions", default=[]) or [],

    "designModule_studyType": design_mod.get("studyType"),
    "designModule_designInfo_allocation": design_info.get("allocation"),
    "designModule_designInfo_interventionModel": design_info.get("interventionModel"),
    "designModule_designInfo_primaryPurpose": design_info.get("primaryPurpose"),
    "designModule_designInfo_maskingInfo_masking": masking_info.get("masking"),
    "designModule_enrollmentInfo_count": enrollment_info.get("count"),

    "armsInterventionsModule_interventions": _extract_interventions(protocol),
    "outcomesModule_primaryOutcomes": _extract_primary_outcomes(protocol),
    "outcomesModule_secondaryOutcomes": _extract_secondary_outcomes(protocol),

    "eligibilityCriteria": elig_mod.get("eligibilityCriteria"),
    "eligibilityCriteria_minimumAge": elig_mod.get("minimumAge"),
    "eligibilityCriteria_sex": elig_mod.get("sex"),
    "eligibilityCriteria_stdAges": elig_mod.get("stdAges") or [],
    "eligibilityCriteria_healthyVolunteers": elig_mod.get("healthyVolunteers"),

    "detailedDescription": desc_mod.get("detailedDescription"),
    "references": _extract_references(protocol),
}

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def transform_studies(raw_studies: list[dict]) -> list[ClinicalTrial]:
    """
    Transform a list of raw API study dicts.  Invalid records are
    dropped; the count of dropped records is logged for observability.
    """
    trials: list= []
    dropped = 0
    for raw in raw_studies:
        trial = transform_study(raw)
        if trial is not None:
            trials.append(trial)
        else:
            dropped += 1

    logger.info(
        "Transform complete: %d valid, %d dropped (%.1f%%)",
        len(trials),
        dropped,
        100 * dropped / max(len(raw_studies), 1),
    )
    print(json.dumps(trials[0], default=json_serial)) # Debug: print first transformed trial
    return trials
