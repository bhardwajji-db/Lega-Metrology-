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
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

class RuleCategory(str, Enum):
    ALL = "ALL"
    FOOD = "FOOD"
    NON_FOOD = "NON_FOOD"
    COSMETICS = "COSMETICS"
    MEDICAL_DEVICES = "MEDICAL_DEVICES"
    EXPORT = "EXPORT"

class RuleExecutionTrace(BaseModel):
    rule_id: str
    rule_name: str = ""
    rule_version: str = "2011.amended"
    category: str = "ALL"
    effective_from: str = "2011-04-01"
    effective_to: Optional[str] = None
    applicable: bool = True
    applicability_reason: str = "Rule applicable under packaging context"
    prerequisites_satisfied: bool = True
    prerequisites_met: bool = True
    prerequisites_details: List[str] = []
    required_fields: List[str] = []
    evaluated_fields: List[str] = []
    inputs: Dict[str, Any] = {}
    extracted_values: Dict[str, Any] = {}
    evidence_found: bool = False
    conditions_evaluated: List[str] = []
    exceptions_applied: List[str] = []
    exemptions_applied: List[str] = []
    exemption_applied: Optional[str] = None
    verdict: str = "PASS"
    output_status: str = "PASS"
    reason: str = ""
    explanation: str = ""
    execution_ms: float = 0.0
    recommendation: Optional[str] = None
    evaluated_at: str = ""

class RuleConflictItem(BaseModel):
    conflict_id: Optional[str] = None
    rule_ids: List[str]
    conflict_type: str  # CHRONOLOGICAL_INCONSISTENCY, MATHEMATICAL_MISMATCH, IMPORT_DECLARATION_MISMATCH, etc.
    description: str
    severity: str = "HIGH"
    action_required: Optional[str] = None
    resolution_hint: Optional[str] = None

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
    effective_from: str = "2011-04-01"
    effective_to: Optional[str] = None
    currently_effective: bool = True
    future_effective_notes: Optional[str] = None
    last_verified: str = "September 2026"
    screening_scope: str = "Statutory Presence & Format Screening"
    severity: str = "medium"  # high, medium, low
    evidence_fields: List[str]
    version: str = "2011.amended"
    rule_version: str = "2011.amended"
    status: str = "ACTIVE"
    category_applicability: List[str] = ["ALL"]  # ALL, FOOD, NON_FOOD, COSMETICS, MEDICAL_DEVICES, EXPORT
    applies_to_imported: bool = False
    applies_to_export: bool = False
    conditions: List[str] = []
    exceptions: List[str] = []
    exemptions: List[str] = []
    prerequisites: List[str] = []
    dependent_rules: List[str] = []
