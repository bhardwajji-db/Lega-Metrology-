from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class RuleDomain(str, Enum):
    LEGAL_METROLOGY = "LEGAL_METROLOGY"
    FSSAI = "FSSAI"

class ComplianceStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NEEDS_REVIEW = "NEEDS_REVIEW"

class RuleDefinition(BaseModel):
    id: str
    domain: RuleDomain
    title: str
    requirement: str
    applicability_description: str
    source_name: str
    source_reference: str
    source_url: str
    authority: str = "Department of Consumer Affairs / FSSAI"
    amendment_version: str = "Current Consolidated Version"
    effective_date: str = "Effective"
    currently_effective: bool = True
    future_effective_notes: Optional[str] = None
    last_verified: str = "September 2026"
    screening_scope: str = "Statutory Presence & Format Screening"
    severity: str = "medium"  # high, medium, low
    evidence_fields: List[str]
    version: str = "1.0"
    status: str = "ACTIVE"
