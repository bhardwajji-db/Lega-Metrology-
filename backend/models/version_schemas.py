from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from models.schemas import ComplianceCheck, ComplianceIssue, RuleScore, CategoryScore, RiskAssessment, ConfidenceSummary, ProductInfo, ComplianceResult, EvidenceItem


class FieldDiffItem(BaseModel):
    """Detailed difference record for a single statutory declaration field between two versions."""
    field: str
    field_label: str
    change_type: str  # ADDED, REMOVED, CHANGED, UNCHANGED, NEEDS_REVIEW
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    old_normalized_value: Optional[str] = None
    new_normalized_value: Optional[str] = None
    delta_info: Optional[Dict[str, Any]] = None  # e.g., {"amount_delta": 10.0, "percent_delta": 25.0, "unit": "INR"}
    requires_review: bool = False
    explanation: str = ""
    evidence_a: Optional[List[EvidenceItem]] = None
    evidence_b: Optional[List[EvidenceItem]] = None


class IngredientItemDiff(BaseModel):
    """Individual ingredient item diff status."""
    name: str
    status: str  # ADDED, REMOVED, UNCHANGED, MODIFIED
    details: Optional[str] = None


class IngredientsDiff(BaseModel):
    """Structured ingredients list comparison."""
    status: str  # UNCHANGED, CHANGED, ADDED, REMOVED, REORDERED_ONLY, UNCERTAIN
    added_ingredients: List[str] = []
    removed_ingredients: List[str] = []
    common_ingredients: List[str] = []
    is_order_changed: bool = False
    raw_diff_summary: str = ""
    items: List[IngredientItemDiff] = []


class NutrientDiffItem(BaseModel):
    """Single nutrient comparison record (e.g. Energy, Protein, Fat, Sodium)."""
    nutrient_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    old_amount: Optional[float] = None
    new_amount: Optional[float] = None
    amount_delta: Optional[float] = None
    unit: str = ""
    change_type: str = "UNCHANGED"  # UNCHANGED, CHANGED, ADDED, REMOVED


class NutritionDiff(BaseModel):
    """Structured nutrition information comparison."""
    status: str = "UNCHANGED"  # UNCHANGED, CHANGED, ADDED, REMOVED, UNCERTAIN
    nutrients: List[NutrientDiffItem] = []
    summary: str = ""


class RuleStateDiff(BaseModel):
    """Statutory rule transition between Version A and Version B."""
    rule_id: str
    rule_name: str
    domain: str  # LEGAL_METROLOGY, FSSAI
    old_status: str  # PASS, FAIL, WARNING, NEEDS_REVIEW, INSUFFICIENT_EVIDENCE, NOT_APPLICABLE
    new_status: str
    transition_type: str  # FIXED, REGRESSED, UNCHANGED, NEWLY_EVALUATED
    explanation: str = ""


class IssueResolutionItem(BaseModel):
    """Issue-resolution tracking between versions."""
    issue_id: str
    rule_id: Optional[str] = None
    field: Optional[str] = None
    resolution_status: str  # RESOLVED, STILL_PRESENT, CHANGED, NEW_ISSUE, UNRESOLVED_REVIEW
    old_issue_text: Optional[str] = None
    new_issue_text: Optional[str] = None
    severity: str = "MEDIUM"
    explanation: str = ""


class VersionSnapshot(BaseModel):
    """Snapshot metadata for a single product version or packaging iteration."""
    version_id: str
    version_label: str
    version_type: str  # ANALYSIS, ARTWORK
    product_name: str
    timestamp: str
    score: float = 0.0
    risk_level: str = "LOW"
    image_url: Optional[str] = None
    owner_user_id: Optional[str] = None
    organization_id: Optional[str] = None
    product_info: Optional[ProductInfo] = None
    compliance_result: Optional[ComplianceResult] = None
    iteration_number: Optional[int] = None
    parent_id: Optional[str] = None


class VersionTimelineEvent(BaseModel):
    """Chronological event in product / packaging audit history."""
    event_id: str
    event_type: str  # VERSION_CREATED, ARTWORK_UPLOADED, ANALYSIS_RUN, CORRECTION_SUBMITTED, SIGN_OFF_APPROVED, COMPARISON_PERFORMED
    title: str
    description: str
    timestamp: str
    version_id: str
    actor_username: Optional[str] = None
    score: Optional[float] = None
    risk_level: Optional[str] = None
    metadata: Dict[str, Any] = {}


class VersionComparisonRequest(BaseModel):
    """Request payload to compare Version A and Version B."""
    version_a_id: str
    version_b_id: str
    version_type_a: str = "ANALYSIS"  # ANALYSIS, ARTWORK
    version_type_b: str = "ANALYSIS"  # ANALYSIS, ARTWORK


class VersionComparisonResult(BaseModel):
    """Complete Version A vs Version B comparison output."""
    comparison_id: str
    version_a: VersionSnapshot
    version_b: VersionSnapshot
    created_at: str
    
    # High-level comparison summary
    score_a: float
    score_b: float
    score_delta: float
    risk_level_a: str
    risk_level_b: str
    risk_shift: str  # IMPROVED, DEGRADED, UNCHANGED
    
    critical_issues_a: int
    critical_issues_b: int
    missing_declarations_a: int
    missing_declarations_b: int
    
    # Categorized Field Diffs
    declaration_diffs: List[FieldDiffItem] = []
    added_declarations: List[FieldDiffItem] = []
    removed_declarations: List[FieldDiffItem] = []
    changed_declarations: List[FieldDiffItem] = []
    unchanged_declarations: List[FieldDiffItem] = []
    review_required_declarations: List[FieldDiffItem] = []
    
    # Specialized Field Diffs
    mrp_diff: Optional[FieldDiffItem] = None
    quantity_diff: Optional[FieldDiffItem] = None
    manufacturer_diff: Optional[FieldDiffItem] = None
    fssai_diff: Optional[FieldDiffItem] = None
    ingredients_diff: Optional[IngredientsDiff] = None
    nutrition_diff: Optional[NutritionDiff] = None
    
    # Rule & Issue Tracking
    rule_diffs: List[RuleStateDiff] = []
    issue_resolutions: List[IssueResolutionItem] = []
    resolved_issues_count: int = 0
    remaining_issues_count: int = 0
    new_issues_count: int = 0
    
    # Summary Notes
    summary_verdict: str = ""
    notes: List[str] = []
