"""
Transform a raw ClinicalTrials.gov API study dict into normalized records
ready for BigQuery insertion.

Returns a dict with keys mapping to target tables:
  - 'trial':         the main row for clinical_trials_gov_stg
  - 'locations':     rows for trial_locations
  - 'mesh_terms':    rows for trial_mesh_terms
  - 'arm_groups':    rows for trial_arm_groups
  - 'interventions': rows for trial_interventions
  - 'outcomes':      rows for trial_outcomes
  - 'officials':     rows for trial_officials

Returns None only when nct_id is missing.
"""

import logging
import re
from datetime import date, datetime
from typing import Optional
from typing import Any, Optional


logger = logging.getLogger(__name__)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _get(d: dict, *keys, default=None):
    """Safely traverse nested dicts; returns `default` on any missing key."""
    current: Any = d
    for k in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(k)
        if current is None:
            return default
    return current if current is not None else default


def _parse_date(date_struct: Optional[dict]) -> Optional[date]:
    """
    Parse a CT.gov dateStruct into a Python date.

    Handles full dates (YYYY-MM-DD), year-month (YYYY-MM), and year-only (YYYY).
    Partial dates default to the 1st of the month / January 1st.
    Returns None on missing or unparseable input.
    """
    if not date_struct:
        return None
    raw = date_struct.get("date") if isinstance(date_struct, dict) else date_struct
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    logger.warning("Unparseable date: %r", raw)
    return None


_AGE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s+(\w+)", re.IGNORECASE)
_AGE_UNIT_TO_YEARS = {
    "year": 1.0, "years": 1.0,
    "month": 1 / 12, "months": 1 / 12,
    "week": 1 / 52.143, "weeks": 1 / 52.143,
    "day": 1 / 365.25, "days": 1 / 365.25,
    "hour": 1 / (365.25 * 24), "hours": 1 / (365.25 * 24),
    "minute": 1 / (365.25 * 24 * 60), "minutes": 1 / (365.25 * 24 * 60),
}


def _parse_age_to_years(age_str: Optional[str]) -> Optional[float]:
    """Convert strings like '30 Years', '6 Months', '2 Weeks' to years (float)."""
    if not age_str or not isinstance(age_str, str):
        return None
    m = _AGE_RE.match(age_str.strip())
    if not m:
        return None
    value, unit = m.groups()
    multiplier = _AGE_UNIT_TO_YEARS.get(unit.lower())
    if multiplier is None:
        logger.debug("Unknown age unit: %r", unit)
        return None
    return float(value) * multiplier


# ─── Child-table extractors ──────────────────────────────────────────────────

def _extract_locations(protocol: dict, nct_id: str, last_update: Optional[date]) -> list[dict]:
    """One row per study site. Powers geo / matching queries."""
    locations = _get(protocol, "contactsLocationsModule", "locations", default=[]) or []
    out = []
    for loc in locations:
        geo = loc.get("geoPoint") or {}
        out.append({
            "nct_id": nct_id,
            "facility": loc.get("facility"),
            "city": loc.get("city"),
            "state": loc.get("state"),
            "country": loc.get("country"),
            "zip": loc.get("zip"),
            "status": loc.get("status"),  # per-site recruiting status
            "latitude": geo.get("lat"),
            "longitude": geo.get("lon"),
            "last_update_post_date": last_update,  # for partitioning and incremental updates
            "contacts": [
                {
                    "name": c.get("name"),
                    "role": c.get("role"),
                    "phone": c.get("phone"),
                    "email": c.get("email"),
                }
                for c in (loc.get("contacts") or [])
            ],
        })
    return out


def _extract_mesh_terms(derived: dict, nct_id: str, last_update: Optional[date]) -> list[dict]:
    """One row per MeSH term, flagged with browse_type and ancestor status."""
    out = []
    for browse_module_key in ("conditionBrowseModule", "interventionBrowseModule"):
        module = derived.get(browse_module_key) or {}
        browse_type = "condition" if browse_module_key == "conditionBrowseModule" else "intervention"
        for term in (module.get("meshes") or []):
            out.append({
                "nct_id": nct_id,
                "mesh_id": term.get("id"),
                "mesh_term": term.get("term"),
                "browse_type": browse_type,
                "is_ancestor": False,
                "last_update_post_date": last_update,
            })
        for term in (module.get("ancestors") or []):
            out.append({
                "nct_id": nct_id,
                "mesh_id": term.get("id"),
                "mesh_term": term.get("term"),
                "browse_type": browse_type,
                "is_ancestor": True,
                "last_update_post_date": last_update,
            })
    return out


def _extract_arm_groups(protocol: dict, nct_id: str, last_update: Optional[date]) -> list[dict]:
    arms = _get(protocol, "armsInterventionsModule", "armGroups", default=[]) or []
    return [
        {
            "nct_id": nct_id,
            "label": a.get("label"),
            "type": a.get("type"),
            "description": a.get("description"),
            "intervention_names": a.get("interventionNames") or [],
            "last_update_post_date": last_update,
        }
        for a in arms
    ]


def _extract_interventions(protocol: dict, nct_id: str, last_update: Optional[date]) -> list[dict]:
    interventions = _get(protocol, "armsInterventionsModule", "interventions", default=[]) or []
    return [
        {
            "nct_id": nct_id,
            "type": iv.get("type"),
            "name": iv.get("name"),
            "description": iv.get("description"),
            "other_names": iv.get("otherNames") or [],
            "arm_group_labels": iv.get("armGroupLabels") or [],
            "last_update_post_date": last_update,
        }
        for iv in interventions
    ]


def _extract_outcomes(protocol: dict, nct_id: str, last_update: Optional[date]) -> list[dict]:
    """Unified outcomes table: primary / secondary / other in one place."""
    out = []
    outcomes_mod = protocol.get("outcomesModule") or {}
    for kind, key in (("primary", "primaryOutcomes"),
                      ("secondary", "secondaryOutcomes"),
                      ("other", "otherOutcomes")):
        for o in (outcomes_mod.get(key) or []):
            out.append({
                "nct_id": nct_id,
                "outcome_type": kind,
                "measure": o.get("measure"),
                "description": o.get("description"),
                "time_frame": o.get("timeFrame"),
                "last_update_post_date": last_update,
            })
    return out


def _extract_officials(protocol: dict, nct_id: str, last_update: Optional[date]) -> list[dict]:
    """All PIs / study chairs / directors, not just the responsible party."""
    officials = _get(protocol, "contactsLocationsModule", "overallOfficials", default=[]) or []
    return [
        {
            "nct_id": nct_id,
            "name": o.get("name"),
            "affiliation": o.get("affiliation"),
            "role": o.get("role"),
            "last_update_post_date": last_update,
        }
        for o in officials
    ]


def _extract_collaborators(protocol: dict) -> list[dict]:
    """Keep the class (NIH / INDUSTRY / OTHER), not just the name."""
    collaborators = _get(protocol, "sponsorCollaboratorsModule", "collaborators", default=[]) or []
    return [
        {"name": c.get("name"), "class": c.get("class")}
        for c in collaborators
        if c.get("name")
    ]


def _extract_references(protocol: dict) -> list[dict]:
    refs = _get(protocol, "referencesModule", "references", default=[]) or []
    out = []
    for r in refs:
        pmid = r.get("pmid")
        try:
            pmid_int = int(pmid) if pmid is not None else None
        except (TypeError, ValueError):
            pmid_int = None
        out.append({
            "citation": r.get("citation"),
            "type": r.get("type"),
            "pmid": pmid_int,
        })
    return out


def _extract_secondary_ids(protocol: dict) -> list[dict]:
    ids = _get(protocol, "identificationModule", "secondaryIdInfos", default=[]) or []
    return [
        {"id": i.get("id"), "type": i.get("type"), "link": i.get("link")}
        for i in ids
    ]


def _extract_central_contacts(protocol: dict) -> list[dict]:
    contacts = _get(protocol, "contactsLocationsModule", "centralContacts", default=[]) or []
    return [
        {
            "name": c.get("name"),
            "role": c.get("role"),
            "phone": c.get("phone"),
            "email": c.get("email"),
        }
        for c in contacts
    ]


# ─── Main transform ──────────────────────────────────────────────────────────

def _transform_study(raw_study: dict) -> Optional[dict]:
    """
    Map one raw CT.gov study dict to a structured record set across multiple
    target tables.

    Returns None only when nct_id is missing (the one hard required field).
    Missing dates, sponsor info, etc. are allowed through as NULL.
    """
    protocol = raw_study.get("protocolSection") or {}
    derived = raw_study.get("derivedSection") or {}

    # ── Identification ─────────────────────────────────────────────────────
    id_mod = protocol.get("identificationModule") or {}
    nct_id: Optional[str] = id_mod.get("nctId")
    if not nct_id:
        logger.warning("Skipping study with no nctId")
        return None

    # ── Status / Dates ─────────────────────────────────────────────────────
    status_mod = protocol.get("statusModule") or {}
    # Note: no longer skip on missing startDate; allow NULL downstream.
    start_date = _parse_date(status_mod.get("startDateStruct"))
    last_update = _parse_date(status_mod.get("lastUpdatePostDateStruct"))
    if last_update is None:
        logger.debug("%s: missing lastUpdatePostDate", nct_id)

    # ── Sponsor / Collaborators ────────────────────────────────────────────
    sponsor_mod = protocol.get("sponsorCollaboratorsModule") or {}
    lead_sponsor = sponsor_mod.get("leadSponsor") or {}
    responsible_party = sponsor_mod.get("responsibleParty") or {}

    # ── Design ─────────────────────────────────────────────────────────────
    design_mod = protocol.get("designModule") or {}
    design_info = design_mod.get("designInfo") or {}
    masking_info = design_info.get("maskingInfo") or {}
    enrollment_info = design_mod.get("enrollmentInfo") or {}

    # ── Eligibility ────────────────────────────────────────────────────────
    elig_mod = protocol.get("eligibilityModule") or {}
    min_age_raw = elig_mod.get("minimumAge")
    max_age_raw = elig_mod.get("maximumAge")

    # ── Description / Conditions / Oversight ──────────────────────────────
    desc_mod = protocol.get("descriptionModule") or {}
    cond_mod = protocol.get("conditionsModule") or {}
    oversight_mod = protocol.get("oversightModule") or {}

    # ── Main trial row ─────────────────────────────────────────────────────
    trial = {
        # Identification
        "nct_id": nct_id,
        "brief_title": id_mod.get("briefTitle"),
        "official_title": id_mod.get("officialTitle"),
        "acronym": id_mod.get("acronym"),
        "organization": _get(id_mod, "organization", "fullName"),
        "organization_class": _get(id_mod, "organization", "class"),
        "secondary_ids": _extract_secondary_ids(protocol),

        # Status / Dates
        "overall_status": status_mod.get("overallStatus"),
        "has_results": raw_study.get("hasResults", False),
        "start_date": start_date,
        "start_date_type": _get(status_mod, "startDateStruct", "type"),
        "completion_date": _parse_date(status_mod.get("completionDateStruct")),
        "primary_completion_date": _parse_date(status_mod.get("primaryCompletionDateStruct")),
        "study_first_post_date": _parse_date(status_mod.get("studyFirstPostDateStruct")),
        "last_update_post_date": last_update,

        # Sponsor
        "lead_sponsor_name": lead_sponsor.get("name"),
        "lead_sponsor_class": lead_sponsor.get("class"),
        "collaborators": _extract_collaborators(protocol),
        "responsible_party_investigator": responsible_party.get("investigatorFullName"),
        "responsible_party_affiliation": responsible_party.get("investigatorAffiliation"),
        "responsible_party_type": responsible_party.get("type"),

        # Design
        "study_type": design_mod.get("studyType"),
        "phases": design_mod.get("phases") or [],
        "allocation": design_info.get("allocation"),
        "intervention_model": design_info.get("interventionModel"),
        "primary_purpose": design_info.get("primaryPurpose"),
        "masking": masking_info.get("masking"),
        "enrollment_count": enrollment_info.get("count"),
        "enrollment_type": enrollment_info.get("type"),  # ESTIMATED vs ACTUAL

        # Conditions / Keywords
        "conditions": cond_mod.get("conditions") or [],
        "keywords": cond_mod.get("keywords") or [],

        # Eligibility (raw text + structured for filters)
        "eligibility_criteria": elig_mod.get("eligibilityCriteria"),
        "min_age_raw": min_age_raw,
        "max_age_raw": max_age_raw,
        "min_age_years": _parse_age_to_years(min_age_raw),
        "max_age_years": _parse_age_to_years(max_age_raw),
        "sex": elig_mod.get("sex"),
        "std_ages": elig_mod.get("stdAges") or [],
        "healthy_volunteers": elig_mod.get("healthyVolunteers"),

        # Description
        "brief_summary": desc_mod.get("briefSummary"),
        "detailed_description": desc_mod.get("detailedDescription"),

        # Oversight / Regulatory
        "is_fda_regulated_drug": oversight_mod.get("isFdaRegulatedDrug"),
        "is_fda_regulated_device": oversight_mod.get("isFdaRegulatedDevice"),
        "has_dmc": oversight_mod.get("oversightHasDmc"),

        # Contacts (central, not site-specific — site contacts live in locations)
        "central_contacts": _extract_central_contacts(protocol),

        # Publications / references
        "references": _extract_references(protocol),
    }

    return {
        "trial": trial,
        "locations": _extract_locations(protocol, nct_id, last_update),
        "mesh_terms": _extract_mesh_terms(derived, nct_id, last_update),
        "arm_groups": _extract_arm_groups(protocol, nct_id, last_update),
        "interventions": _extract_interventions(protocol, nct_id, last_update),
        "outcomes": _extract_outcomes(protocol, nct_id, last_update),
        "officials": _extract_officials(protocol, nct_id, last_update),
    }
    
    
def transform_studies(raw_studies: list[dict]) -> list[dict]:
    """
    Transform a list of raw API study dicts.  Invalid records are
    dropped; the count of dropped records is logged for observability.
    """
    trials: list= []
    dropped = 0
    for raw in raw_studies:
        trial = _transform_study(raw)
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
    #print(json.dumps(trials[0], default=json_serial)) # Debug: print first transformed trial
    return trials