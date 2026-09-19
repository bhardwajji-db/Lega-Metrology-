export interface MultilingualLanguageInfo {
  code: string;
  name: string;
  script: string;
  confidence: number;
  token_count: number;
}

export interface SupportedReportLanguage {
  code: string;
  label: string;
  native: string;
}

export const SUPPORTED_REPORT_LANGUAGES: SupportedReportLanguage[] = [
  { code: 'en', label: 'English', native: 'English' },
  { code: 'hi', label: 'Hindi', native: 'हिन्दी' },
  { code: 'bn', label: 'Bengali', native: 'বাংলা' },
  { code: 'mr', label: 'Marathi', native: 'मराठी' },
  { code: 'gu', label: 'Gujarati', native: 'ગુજરાતી' },
  { code: 'pa', label: 'Punjabi', native: 'ਪੰਜਾਬੀ' },
  { code: 'ta', label: 'Tamil', native: 'தமிழ்' },
  { code: 'te', label: 'Telugu', native: 'తెలుగు' },
  { code: 'kn', label: 'Kannada', native: 'ಕನ್ನಡ' },
  { code: 'ml', label: 'Malayalam', native: 'മലയാളം' },
];

export interface MultilingualMetadata {
  primary_language: string;
  primary_script: string;
  detected_languages: MultilingualLanguageInfo[];
  detected_scripts: string[];
  mixed_language: boolean;
  language_confidence: number;
}

export interface OCRWord {
  text: string;
  confidence: number;
  bbox: number[]; // [x1, y1, x2, y2]
  language?: string | null;
  script?: string | null;
}

export interface OCRResult {
  full_text: string;
  words: OCRWord[];
  language: string;
  processing_time: number;
  average_confidence?: number;
  word_count?: number;
  engine?: string;
  preprocessing_variant?: string;
  regions_processed?: number;
  ocr_passes?: number;
  multilingual?: MultilingualMetadata | null;
}

export interface ProductInfo {
  product_name: string | null;
  brand: string | null;
  manufacturer: string | null;
  marketed_by?: string | null;
  net_quantity: string | null;
  mrp: string | null;
  manufacturing_date: string | null;
  manufacture_date?: string | null;
  packaging_date?: string | null;
  expiry_date: string | null;
  use_by_date?: string | null;
  best_before?: string | null;
  relative_shelf_life?: string | null;
  batch_number: string | null;
  fssai_license: string | null;
  consumer_care: string | null;
  consumer_care_phone?: string | null;
  consumer_care_email?: string | null;
  country_of_origin: string | null;
  ingredients: string | null;
  nutritional_info: string | null;
  nutrition_panel_detected?: boolean | null;
  nutrition_facts?: Record<string, string> | null;
  allergen_info: string | null;
  barcode_detected?: string | null;
  other_declarations: Record<string, string>;
  declaration_confidences?: Record<string, number>;
  field_provenance?: Record<string, FieldProvenance>;
  extraction_mode: string;
  multilingual?: MultilingualMetadata | null;
}

export interface FieldProvenance {
  field_name: string;
  raw_value?: string | null;
  normalized_value?: string | null;
  image_index: number;
  image_label: string;
  source_text: string;
  source_token_ids?: string[];
  source_bbox?: number[] | null;
  confidence: number;
  match_method: string;
  language?: string | null;
  script?: string | null;
  language_confidence?: number | null;
}

export interface ExtractionCandidateItem {
  value: string;
  raw_text?: string;
  confidence: number;
  source?: string | null;
  panel?: string | null;
  bbox?: number[] | null;
  is_primary?: boolean;
}

export interface EvidenceItem {
  id?: string;
  image_index?: number;
  image_label?: string;
  field_name?: string;
  extracted_text?: string;
  panel?: string;
  text?: string;
  normalized_value?: string | null;
  bbox?: number[] | null; // [x1, y1, x2, y2]
  bounding_box?: { x: number; y: number; width: number; height: number } | null;
  geometry_type?: 'WORD_UNION' | 'LINE' | 'TOKEN' | 'NONE';
  match_method?: string;
  confidence?: number;
  ocr_confidence?: number;
  reliability_score?: number;
  reliability_tier?: 'HIGH' | 'MEDIUM' | 'LOW' | 'NEEDS_VERIFICATION' | string;
  linked_rule_id?: string | null;
  linked_field?: string | null;
  regulation_reference?: string | null;
  evidence_status?: 'VERIFIED' | 'CONTEXTUAL' | 'NEEDS_REVIEW' | 'NO_EVIDENCE' | 'NOT_APPLICABLE' | 'UNAVAILABLE';
  evidence_type?: 'DIRECT_OCR' | 'DERIVED_FIELD' | 'PROVISO_DELEGATION' | 'NONE';
  explanation?: string | null;
  source_token_ids?: string[];
  field_type?: 'FIELD' | 'PANEL' | 'REGION';
  quality_score?: number | null;
  analysis_id?: string | null;
  language?: string | null;
  script?: string | null;
  language_confidence?: number | null;
}

export interface ComplianceCheck {
  rule_id: string;
  field: string;
  field_label: string;
  required: boolean;
  detected: boolean;
  detected_value: string | null;
  extracted_value?: string | null;
  severity: string;
  status: string;
  description: string;
  source: string;
  explanation: string | null;
  pass_reason?: string | null;
  fail_reason?: string | null;
  review_reason?: string | null;
  linked_rule_id?: string | null;
  linked_field?: string | null;
  regulation_reference?: string | null;
  field_status?: 'PRESENT' | 'MISSING' | 'AMBIGUOUS' | 'CONFLICT' | 'UNCERTAIN' | string | null;
  reliability_score?: number | null;
  reliability_tier?: 'HIGH' | 'MEDIUM' | 'LOW' | 'NEEDS_VERIFICATION' | string | null;
  candidates?: ExtractionCandidateItem[] | null;
  recommendation: string | null;
  domain?: 'LEGAL_METROLOGY' | 'FSSAI';
  source_name?: string | null;
  source_reference?: string | null;
  source_url?: string | null;
  confidence?: number | null;
  evidence_image_label?: string | null;
  evidence_region?: string | null;
  reason?: string | null;
  bbox?: number[] | null; // [x1, y1, x2, y2]
  bbox_x?: number | null;
  bbox_y?: number | null;
  bbox_width?: number | null;
  bbox_height?: number | null;
  evidence?: EvidenceItem[];
  execution_trace?: RuleExecutionTrace | null;
  rule_version?: string | null;
}

export interface RuleExecutionTrace {
  rule_id: string;
  rule_version: string;
  category: string;
  effective_from: string;
  effective_to?: string | null;
  evaluated_fields: string[];
  inputs: Record<string, any>;
  prerequisites_met: boolean;
  conditions_evaluated: string[];
  exemption_applied?: string | null;
  output_status: string;
  execution_ms: number;
  explanation: string;
}

export interface RuleConflictItem {
  conflict_type: string;
  rule_ids: string[];
  description: string;
  severity: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  resolution_hint?: string | null;
}

export interface HeatmapBox {
  field_name: string;
  rule_id?: string | null;
  status: 'PASS' | 'FAIL' | 'REVIEW' | string;
  reliability_score: number;
  reliability_tier: string;
  bbox: { x: number; y: number; width: number; height: number };
  extracted_text: string;
  intensity: number;
}

export interface EvidenceHeatmapResponse {
  front_boxes: HeatmapBox[];
  back_boxes: HeatmapBox[];
  total_regions: number;
}

export interface PanelComplianceHeatmapResponse {
  front_panel: { total_fields: number; passed: number; failed: number; review: number; status: string };
  back_panel: { total_fields: number; passed: number; failed: number; review: number; status: string };
  zones: Record<string, any>;
}

export interface EvidenceAuditLogItem {
  id: string;
  analysis_id: string;
  rule_id?: string | null;
  field_name?: string | null;
  action: string;
  old_value?: string | null;
  new_value?: string | null;
  reason?: string | null;
  user_id: string;
  user_role: string;
  timestamp: string;
}

export interface ComplianceIssue {
  what: string;
  expected: string;
  why: string;
  action: string;
  severity?: string;
  field?: string;
  domain?: string;
}

export type ActionCategory = 
  | 'VERIFY_MANUALLY'
  | 'RECAPTURE_IMAGE'
  | 'CORRECT_LABEL'
  | 'VERIFY_APPLICABILITY'
  | 'VERIFY_OFFICIAL_RECORD'
  | 'NO_ACTION';

export type RecommendationPriority = 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';

export interface Recommendation {
  rule_id: string;
  domain: string;
  status: string;
  priority: RecommendationPriority;
  action_category: ActionCategory;
  title: string;
  issue: string;
  recommended_action: string;
  corrective_action?: string | null;
  verification_step?: string | null;
  evidence_image_label?: string | null;
  evidence_region?: string | null;
  confidence?: number | null;
  source_name?: string | null;
  source_reference?: string | null;
  source_url?: string | null;
  requires_human_review?: boolean;
  bbox?: number[] | null; // [x1, y1, x2, y2]
  bbox_x?: number | null;
  bbox_y?: number | null;
  bbox_width?: number | null;
  bbox_height?: number | null;
  evidence?: EvidenceItem[];
}

export interface RuleScore {
  rule_id: string;
  rule_name: string;
  domain: string;
  base_weight: number;
  multiplier: number;
  weighted_points_earned: number;
  max_weighted_points: number;
  status: string;
  percentage: number;
}

export interface CategoryScore {
  category: string;
  earned_points: number;
  max_points: number;
  score: number;
  total_rules: number;
  passed_rules: number;
  failed_rules: number;
  review_rules: number;
}

export interface ConfidenceSummary {
  ocr_avg_confidence: number;
  extraction_avg_confidence: number;
  evidence_reliability_avg: number;
  aggregate_confidence: number;
  confidence_tier: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  has_conflicting_candidates: boolean;
}

export interface RiskFactor {
  factor_id: string;
  title: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | string;
  description: string;
  source_reference: string;
  impact_on_score: number;
}

export interface RiskAssessment {
  risk_level: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | string;
  level?: string;
  grounded_explanation: string;
  missing_declaration_count: number;
  critical_violation_count: number;
  review_required_count: number;
  insufficient_evidence_count: number;
  risk_factors: RiskFactor[];
  confidence_adjusted_score: number;
}

export interface ScoringConfiguration {
  scoring_version: string;
  status_multipliers: Record<string, number>;
  severity_weights: Record<string, number>;
  risk_thresholds: Record<string, number>;
  confidence_penalty_factor: number;
  description: string;
}

export interface ScoreHistoryEntry {
  analysis_id: string;
  product_name: string;
  score: number;
  risk_level: string;
  created_at: string;
  rule_scores?: Record<string, RuleScore>;
  category_scores?: Record<string, CategoryScore>;
}

export interface ProductRiskHistory {
  product_name: string;
  total_analyses: number;
  average_score: number;
  current_risk_level: string;
  history: ScoreHistoryEntry[];
  score_trend: number[];
}

export interface BatchRiskDistribution {
  total_screened: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  average_score: number;
  risk_percentages: Record<string, number>;
}

export interface ComplianceResult {
  checks: ComplianceCheck[];
  score: number;
  status: string;
  total_rules: number;
  passed_rules: number;
  failed_rules: number;
  warning_rules?: number;
  needs_review_rules?: number;
  not_applicable_rules?: number;
  issues: ComplianceIssue[];
  recommendations?: Recommendation[];
  conflicts?: RuleConflictItem[];
  rule_scores?: Record<string, RuleScore>;
  category_scores?: Record<string, CategoryScore>;
  risk_assessment?: RiskAssessment;
  confidence_summary?: ConfidenceSummary;
  scoring_version?: string;
}

export interface ImageQualityMetrics {
  blur_score: number;
  motion_blur_score: number;
  exposure_mean: number;
  exposure_std: number;
  glare_score: number;
  skew_angle_deg: number;
  contrast_score: number;
  min_text_height_px: number;
}

export interface ImageQualityDefect {
  defect_type: string;
  severity: string;
  message: string;
  metric_value?: number | null;
  bbox?: number[] | null;
}

export interface ImageQualityResult {
  overall_score: number;
  decision: 'ACCEPT' | 'WARNING' | 'REJECT';
  is_acceptable: boolean;
  metrics: ImageQualityMetrics;
  defects: ImageQualityDefect[];
  summary: string;
}

export interface PerspectiveCorrectionResult {
  applied: boolean;
  detected_quadrilateral?: number[][] | null;
  skew_angle_deg: number;
  trapezoid_score: number;
  confidence: number;
  non_destructive_matrix?: number[][] | null;
}

export interface PackageBoundaryResult {
  detected: boolean;
  bbox?: number[] | null;
  normalized_bbox?: number[] | null;
  polygon?: number[][] | null;
  contour_points?: number[][] | null;
  area_ratio: number;
  aspect_ratio: number;
  confidence: number;
  confidence_tier: string;
}

export interface PanelClassificationResult {
  primary_panel: 'FRONT' | 'BACK' | 'SIDE' | 'TOP' | 'BOTTOM' | 'PRINCIPAL_DISPLAY_PANEL' | 'UNKNOWN';
  confidence: number;
  confidence_tier: string;
  supporting_signals: string[];
  candidate_scores: Record<string, number>;
  facets_detected?: Array<{ facet_name: string; bbox: number[] }> | null;
}

export interface SemanticRegionResult {
  region_type: string;
  detected: boolean;
  confidence: number;
  confidence_tier: string;
  bbox?: number[] | null;
  normalized_bbox?: number[] | null;
  polygon?: number[][] | null;
  detection_method: string;
  matched_keywords: string[];
  associated_text: string;
  is_table_structure: boolean;
  evidence_id?: string | null;
}

export interface SymbolDetectionResult {
  symbol_type: string;
  detected: boolean;
  confidence: number;
  confidence_tier: string;
  bbox?: number[] | null;
  normalized_bbox?: number[] | null;
  color_scheme?: string | null;
  detection_method: string;
  notes?: string | null;
  evidence_id?: string | null;
}

export interface LogoDetectionResult {
  logo_name: string;
  detected: boolean;
  confidence: number;
  bbox?: number[] | null;
  normalized_bbox?: number[] | null;
  detection_method: string;
  evidence_id?: string | null;
}

export interface BarcodeDetectionResult {
  detected: boolean;
  barcode_type: string;
  bbox?: number[] | null;
  normalized_bbox?: number[] | null;
  orientation: string;
  decoded_value?: string | null;
  confidence: number;
  confidence_tier: string;
  detection_method: string;
}

export interface QRDetectionResult {
  detected: boolean;
  bbox?: number[] | null;
  normalized_bbox?: number[] | null;
  decoded_payload?: string | null;
  is_safe_payload: boolean;
  confidence: number;
  confidence_tier: string;
  detection_method: string;
  warning?: string | null;
}

export interface TextRegionInfo {
  region_id: string;
  bbox: number[];
  normalized_bbox: number[];
  text: string;
  token_count: number;
  confidence: number;
  estimated_font_height_px: number;
  is_small_text: boolean;
  orientation: number;
  script?: string | null;
  language?: string | null;
}

export interface VisionTimingMetrics {
  quality_gate_ms: number;
  geometry_ms: number;
  package_boundary_ms: number;
  panel_classification_ms: number;
  text_regions_ms: number;
  semantic_regions_ms: number;
  symbols_ms: number;
  barcodes_ms: number;
  total_vision_ms: number;
}

export interface VisionAnalysisResult {
  image_index: number;
  image_label: string;
  source_filename: string;
  quality: ImageQualityResult;
  geometry: PerspectiveCorrectionResult;
  package_boundary: PackageBoundaryResult;
  panel_classification: PanelClassificationResult;
  semantic_regions: SemanticRegionResult[];
  symbols: SymbolDetectionResult[];
  logos: LogoDetectionResult[];
  barcode: BarcodeDetectionResult;
  qr_code: QRDetectionResult;
  text_regions: TextRegionInfo[];
  timing: VisionTimingMetrics;
  evidence_items?: EvidenceItem[];
  overall_confidence: number;
  overall_confidence_tier: string;
  status: string;
  error_message?: string | null;
}

export interface ProductImageEvidence {
  filename: string;
  image_url: string;
  label: string;
  ocr_text: string;
  words?: OCRWord[];
  word_count?: number;
  average_confidence?: number;
  preprocessing_variant?: string;
  image_quality?: Record<string, any>;
  quality_warning?: string | null;
  vision_analysis?: VisionAnalysisResult | null;
}

export interface CalibrationResult {
  status: 'PHYSICAL_MEASUREMENT_VERIFIED' | 'PHYSICAL_MEASUREMENT_ESTIMATED' | 'CALIBRATION_MISSING' | 'CALIBRATION_INVALID' | 'MEASUREMENT_UNRELIABLE';
  target_type?: string | null;
  pixels_per_mm?: number | null;
  target_bbox?: number[] | null;
  confidence?: number | null;
  message: string;
}

export interface FSSAIVerificationResult {
  licence_number?: string | null;
  status: 'VERIFIED' | 'NOT_FOUND' | 'INVALID_FORMAT' | 'SERVICE_UNAVAILABLE' | 'NOT_VERIFIED' | 'NOT_APPLICABLE';
  provider: string;
  business_name?: string | null;
  licence_type?: string | null;
  valid_upto?: string | null;
  verification_timestamp?: string | null;
  message: string;
  is_live: boolean;
  error_details?: string | null;
}

export interface GS1VerificationResult {
  gtin?: string | null;
  status: 'VERIFIED' | 'NOT_FOUND' | 'MISMATCH' | 'INVALID_FORMAT' | 'SERVICE_UNAVAILABLE' | 'NOT_VERIFIED' | 'NOT_APPLICABLE';
  provider: string;
  brand_name?: string | null;
  product_description?: string | null;
  company_name?: string | null;
  verification_timestamp?: string | null;
  message: string;
  is_live: boolean;
  error_details?: string | null;
}

export interface FontSizeAnalysis {
  net_quantity_font_height_mm?: number | null;
  mrp_font_height_mm?: number | null;
  min_required_font_height_mm: number;
  is_font_compliant: boolean;
  readability_score: number;
  readability_tier: 'EXCELLENT' | 'GOOD' | 'MODERATE' | 'POOR';
  rule_12_verdict: string;
  details: string;
  calibration_status?: string;
  pixels_per_mm?: number | null;
  calibration_target?: string | null;
  measurement_method?: string;
}

export interface AnalysisResponse {
  id: string;
  product_name: string;
  image_url: string;
  images?: ProductImageEvidence[];
  ocr_result: OCRResult;
  product_info: ProductInfo;
  compliance_result: ComplianceResult;
  recommendations?: Recommendation[];
  created_at: string;
  image_quality_warning?: string | null;
  font_size_analysis?: FontSizeAnalysis;
  fssai_verification?: FSSAIVerificationResult | null;
  gs1_verification?: GS1VerificationResult | null;
  calibration_result?: CalibrationResult | null;
  owner_user_id?: string | null;
  multilingual?: MultilingualMetadata | null;
  vision_analysis?: VisionAnalysisResult | null;
  external_verification?: ExternalVerificationSummary | null;
  product_identity?: ProductIdentity | null;
  barcode_scan_results?: BarcodeItem[];
  cross_validation?: CrossValidationSummary | null;
  external_product_verification?: ExternalProductVerificationPipelineResult | null;
  claims_analysis?: ClaimAnalysisResult | null;
}

export type ClaimCategory =
  | 'NUTRITIONAL'
  | 'HEALTH'
  | 'MEDICAL'
  | 'INGREDIENT'
  | 'QUALITY'
  | 'ABSOLUTE'
  | 'COMPARATIVE'
  | 'CERTIFICATION'
  | 'ENVIRONMENTAL'
  | 'ORIGIN'
  | 'MANUFACTURING'
  | 'PRODUCT_PERFORMANCE'
  | 'SAFETY'
  | 'OTHER';

export type ClaimStatus =
  | 'SUPPORTED'
  | 'INSUFFICIENT_EVIDENCE'
  | 'POTENTIAL_CONTRADICTION'
  | 'HIGH_RISK_REVIEW'
  | 'NOT_ASSESSABLE';

export type EvidenceLinkType =
  | 'SUPPORTED_BY'
  | 'CONTRADICTED_BY'
  | 'REQUIRES_EXTERNAL_VERIFICATION';

export interface ClaimEvidenceItem {
  id: string;
  type: string;
  text: string;
  panel: string;
  image_index: number;
  confidence: number;
  bounding_box?: [number, number, number, number] | null;
  relationship: EvidenceLinkType;
  explanation?: string | null;
}

export interface ClaimConfidenceBreakdown {
  ocr_confidence: number;
  extraction_confidence: number;
  evidence_confidence: number;
  assessment_confidence: number;
  cross_panel_consistency: number;
  overall_confidence: number;
}

export interface ClaimAssessment {
  status: ClaimStatus;
  reason: string;
  detailed_explanation: string;
  rule_id?: string | null;
  rule_source?: string | null;
  rule_reference?: string | null;
  jurisdiction: string;
  requires_human_review: boolean;
  is_absolute: boolean;
  is_comparative: boolean;
  is_high_risk: boolean;
  verdict_distinction: string;
}

export interface ClaimFinding {
  claim_id: string;
  claim_text: string;
  normalized_claim: string;
  category: ClaimCategory;
  secondary_categories?: ClaimCategory[];
  source_panel: string;
  image_index: number;
  bounding_box?: [number, number, number, number] | null;
  confidence: number;
  confidence_breakdown: ClaimConfidenceBreakdown;
  evidence: ClaimEvidenceItem[];
  assessment: ClaimAssessment;
  model_version?: string;
}

export interface ClaimSummary {
  total_detected: number;
  supported: number;
  insufficient_evidence: number;
  potential_contradictions: number;
  high_risk_review: number;
  not_assessable: number;
  requires_human_review_count: number;
}

export interface ClaimAnalysisResult {
  claims_detected: number;
  summary: ClaimSummary;
  claims: ClaimFinding[];
  processing_time_ms: number;
  analyzed_panels: string[];
  engine_version: string;
}

export interface HistoryItem {
  id: string;
  product_name: string;
  score: number;
  status: string;
  created_at: string;
  image_url: string;
  owner_user_id?: string | null;
}

export interface DashboardStats {
  total_analyzed: number;
  compliant: number;
  needs_review?: number;
  failures?: number;
  violations: number;
  average_score: number;
  recent: HistoryItem[];
  packages_screened?: number;
  compliant_packages?: number;
  review_findings?: number;
  failed_findings?: number;
}

export interface ComplianceRule {
  id: string;
  rule_id?: string;
  title: string;
  field?: string;
  field_label?: string;
  domain: 'LEGAL_METROLOGY' | 'FSSAI' | string;
  category_applicability: 'ALL' | 'FOOD' | 'NON_FOOD' | 'COSMETICS' | 'MEDICAL_DEVICES' | 'EXPORT' | string;
  effective_from: string;
  effective_to?: string | null;
  rule_version: string;
  severity: string;
  requirement: string;
  source_name: string;
  source_reference: string;
  source_url?: string | null;
  evidence_fields: string[];
  conditions?: string[];
  exceptions?: string[];
  exemptions?: string[];
  prerequisites?: string[];
  dependent_rules?: string[];
  description?: string;
  source?: string;
  recommendation?: string;
}

export interface RuleTestRequest {
  rule_id: string;
  product_info: Record<string, any>;
  ocr_text?: string;
  context_override?: Record<string, any> | null;
}

export interface RuleTestResponse {
  rule_id: string;
  rule_name: string;
  domain: string;
  status: string;
  reason: string;
  detected_value?: string | null;
  pass_reason?: string | null;
  fail_reason?: string | null;
  review_reason?: string | null;
  execution_trace: RuleExecutionTrace;
  is_simulation: boolean;
}

export type AnalysisStage = 
  | 'uploading'
  | 'preprocessing' 
  | 'ocr'
  | 'combining'
  | 'extracting'
  | 'compliance'
  | 'report';

export interface DemoCaseMeta {
  id: string;
  name: string;
  brand?: string;
  category: string;
  purpose: string;
  description: string;
  panels: string[];
  expected_score?: number;
  expected_status?: string;
  badge_type: 'compliant' | 'warning' | 'violation' | 'success' | 'danger';
  tags?: string[];
}

export type WorkspaceType = 'MERCHANT' | 'AUDIT' | 'ENFORCEMENT';

export type WorkspaceCoreAction = 'PREVENT' | 'VERIFY' | 'INVESTIGATE';

export interface WorkspaceDefinition {
  id: WorkspaceType;
  label: string;
  shortLabel: string;
  tagline: string;
  coreAction: WorkspaceCoreAction;
  badge: string;
  iconName: 'Store' | 'SearchCheck' | 'ShieldAlert';
  description: string;
  capabilities: string[];
  allowedRoles: BackendRole[];
}

export type UserRole = 'ENFORCEMENT_OFFICER' | 'COMPLIANCE_INSPECTOR' | 'MERCHANT_PUBLIC';

export interface RoleInfo {
  role: UserRole;
  label: string;
  badge: string;
  officerId?: string;
  jurisdiction?: string;
  description: string;
}

// ── Auth (backend /api/auth & /api/admin) ──────────────────────────────
export type BackendRole = 'ADMIN' | 'ENFORCEMENT_OFFICER' | 'AUDIT_OFFICER' | 'MERCHANT_PUBLIC';

export interface AuthUser {
  username: string;
  full_name: string | null;
  role: BackendRole;
  created_at?: string;
  role_label?: string;
  jurisdiction?: string;
  email?: string | null;
  status?: 'ACTIVE' | 'INVITED' | 'SUSPENDED';
  invited_at?: string;
  activated_at?: string;
  is_admin?: boolean;
}

export interface AccountAuditLog {
  id: number;
  actor_username: string;
  target_username?: string | null;
  event_type?: string;
  action?: string;
  details?: string | null;
  ip_address?: string | null;
  created_at: string;
}

export interface InvitationVerification {
  valid: boolean;
  username?: string;
  full_name?: string;
  email?: string;
  role?: BackendRole;
  role_label?: string;
}

// ── Dashboard trends / status breakdown ─────────────────────────────────
export interface TrendPoint {
  date: string;
  total: number;
  compliant: number;
  violations: number;
  needs_review: number;
}

export interface StatusBreakdown {
  status: string;
  count: number;
}

// ── Enforcement ──────────────────────────────────────────────────────────
export interface PenaltyEstimate {
  analysis_id: string;
  product_name: string;
  score: number;
  status: string;
  violations: Array<{ rule_id: string; field: string; severity: string }>;
  base_penalty: number;
  repeat_offender_multiplier: number;
  estimated_penalty: number;
  currency: string;
  legal_basis: string[];
  disclaimer: string;
}

export interface ShowCauseNotice {
  notice_id: string;
  generated_at: string;
  analysis_id: string;
  product_name: string;
  manufacturer: string | null;
  violations_summary: Array<{ rule_id: string; field: string; finding: string; penalty_estimate: number }>;
  total_penalty_estimate: number;
  response_days: number;
  authority: string;
  legal_basis: string[];
}

// ── Pre-Print Packaging Compliance (Section 8) ──────────────────────────
export interface ArtworkLayoutRegion {
  region_id: string;
  region_type: string;
  bbox_normalized: number[];
  bbox_pixels?: number[];
  confidence: number;
  text_content?: string;
  font_size_pt_estimated?: number | null;
}

export interface ArtworkPageInfo {
  page_number: number;
  width: number;
  height: number;
  dpi: number;
  preview_image_path?: string | null;
  extracted_text?: string;
  text_source: 'PDF_VECTOR' | 'OCR' | 'HYBRID';
  layout_regions: ArtworkLayoutRegion[];
  word_count: number;
}

export interface PlacementCheckResult {
  check_name: string;
  field_name: string;
  passed: boolean;
  status: 'PASS' | 'FAIL' | 'REVIEW' | 'NOT_APPLICABLE';
  finding: string;
  recommended_zone: string;
  actual_zone?: string | null;
  legal_citation: string;
  bbox_normalized?: number[] | null;
}

export interface FontSizeEstimateResult {
  field_name: string;
  text_sample: string;
  estimated_height_mm: number;
  estimated_pt_size: number;
  mandated_minimum_mm: number;
  is_compliant: boolean;
  confidence: number;
  estimation_method: string;
  disclaimer: string;
  bbox_normalized?: number[] | null;
}

export interface DesignerCorrectionItem {
  item_id: string;
  field_name: string;
  severity: 'CRITICAL' | 'MAJOR' | 'MINOR' | 'INFO';
  issue: string;
  suggested_action: string;
  affected_area?: string | null;
  legal_reference: string;
  is_blocking_for_print: boolean;
}

export interface PreprintApprovalRecord {
  approval_id: string;
  artwork_id: string;
  reviewer_id: string;
  reviewer_name: string;
  reviewer_role: string;
  decision: 'APPROVED' | 'REJECTED' | 'REQUEST_CHANGES';
  comments: string;
  timestamp: string;
  conditions?: string[];
  legal_disclaimer_acknowledged: boolean;
}

export interface PreprintApprovalRequest {
  reviewer_id?: string;
  reviewer_name: string;
  reviewer_role: string;
  decision: 'APPROVED' | 'REJECTED' | 'REQUEST_CHANGES';
  comments: string;
  conditions?: string[];
  legal_disclaimer_acknowledged: boolean;
}

export interface ArtworkDocument {
  id: string;
  filename: string;
  file_path: string;
  file_type: string;
  file_size: number;
  page_count: number;
  dimensions: Record<string, any>;
  dpi: number;
  source_identity: string;
  compliance_ruleset: string;
  parent_artwork_id?: string | null;
  iteration_number: number;
  workflow_status: 'DRAFT' | 'ACTION_REQUIRED' | 'CHANGES_REQUESTED' | 'READY_FOR_PRINT' | 'REJECTED';
  approval_status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'CHANGES_REQUESTED';
  approval_record?: PreprintApprovalRecord | null;
  analysis_result?: PreprintAnalysisResponse | null;
  pages_data?: ArtworkPageInfo[];
  owner_user_id?: string;
  created_at: string;
  updated_at: string;
}

export interface PreprintUploadResponse {
  success: boolean;
  artwork_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  page_count: number;
  dimensions: Record<string, any>;
  dpi: number;
  pages: ArtworkPageInfo[];
  message: string;
}

export interface ScoringBreakdown {
  final_score: number;
  risk_level: string;
  confidence_penalty?: number;
  category_scores?: Record<string, CategoryScore>;
  rule_scores?: Record<string, RuleScore>;
  confidence_summary?: ConfidenceSummary;
}

export interface PreprintAnalysisResponse {
  artwork_id: string;
  filename: string;
  file_type: string;
  page_count: number;
  source_identity: string;
  compliance_ruleset: string;
  iteration_number: number;
  parent_artwork_id?: string | null;
  overall_status: 'COMPLIANT' | 'NEEDS_REVIEW' | 'NON_COMPLIANT';
  overall_score: number;
  workflow_status: 'DRAFT' | 'ACTION_REQUIRED' | 'CHANGES_REQUESTED' | 'READY_FOR_PRINT' | 'REJECTED';
  missing_declarations: string[];
  mandatory_checklist: Record<string, boolean>;
  placement_checks: PlacementCheckResult[];
  font_size_estimates: FontSizeEstimateResult[];
  designer_corrections: DesignerCorrectionItem[];
  pages: ArtworkPageInfo[];
  product_info: ProductInfo;
  compliance_result: ComplianceResult;
  scoring_breakdown: ScoringBreakdown;
  ready_for_print_eligible: boolean;
  print_blocking_issues_count: number;
  summary_notes: string[];
}

// ── Section 9 Version Comparison Schemas ─────────────────────────────────
export interface FieldDiffItem {
  field: string;
  field_label: string;
  change_type: 'ADDED' | 'REMOVED' | 'CHANGED' | 'UNCHANGED' | 'NEEDS_REVIEW';
  old_value?: string | null;
  new_value?: string | null;
  old_normalized_value?: string | null;
  new_normalized_value?: string | null;
  delta_info?: {
    amount_delta?: number;
    percent_delta?: number;
    unit?: string;
    currency?: string;
  } | null;
  requires_review: boolean;
  explanation: string;
  evidence_a?: EvidenceItem[] | null;
  evidence_b?: EvidenceItem[] | null;
}

export interface IngredientItemDiff {
  name: string;
  status: 'ADDED' | 'REMOVED' | 'UNCHANGED' | 'MODIFIED';
  details?: string | null;
}

export interface IngredientsDiff {
  status: 'UNCHANGED' | 'CHANGED' | 'ADDED' | 'REMOVED' | 'REORDERED_ONLY' | 'UNCERTAIN';
  added_ingredients: string[];
  removed_ingredients: string[];
  common_ingredients: string[];
  is_order_changed: boolean;
  raw_diff_summary: string;
  items: IngredientItemDiff[];
}

export interface NutrientDiffItem {
  nutrient_name: string;
  old_value?: string | null;
  new_value?: string | null;
  old_amount?: number | null;
  new_amount?: number | null;
  amount_delta?: number | null;
  unit: string;
  change_type: 'UNCHANGED' | 'CHANGED' | 'ADDED' | 'REMOVED';
}

export interface NutritionDiff {
  status: 'UNCHANGED' | 'CHANGED' | 'ADDED' | 'REMOVED' | 'UNCERTAIN';
  nutrients: NutrientDiffItem[];
  summary: string;
}

export interface RuleStateDiff {
  rule_id: string;
  rule_name: string;
  domain: string;
  old_status: string;
  new_status: string;
  transition_type: 'FIXED' | 'REGRESSED' | 'UNCHANGED' | 'NEWLY_EVALUATED' | 'MODIFIED';
  explanation: string;
}

export interface IssueResolutionItem {
  issue_id: string;
  rule_id?: string | null;
  field?: string | null;
  resolution_status: 'RESOLVED' | 'STILL_PRESENT' | 'CHANGED' | 'NEW_ISSUE' | 'UNRESOLVED_REVIEW';
  old_issue_text?: string | null;
  new_issue_text?: string | null;
  severity: string;
  explanation: string;
}

export interface VersionSnapshot {
  version_id: string;
  version_label: string;
  version_type: 'ANALYSIS' | 'ARTWORK';
  product_name: string;
  timestamp: string;
  score: number;
  risk_level: string;
  image_url?: string | null;
  owner_user_id?: string | null;
  product_info?: ProductInfo | null;
  compliance_result?: ComplianceResult | null;
  iteration_number?: number | null;
  parent_id?: string | null;
}

export interface VersionTimelineEvent {
  event_id: string;
  event_type: 'VERSION_CREATED' | 'ARTWORK_UPLOADED' | 'ANALYSIS_RUN' | 'CORRECTION_SUBMITTED' | 'SIGN_OFF_APPROVED' | 'COMPARISON_PERFORMED';
  title: string;
  description: string;
  timestamp: string;
  version_id: string;
  actor_username?: string | null;
  score?: number | null;
  risk_level?: string | null;
  metadata: Record<string, any>;
}

export interface VersionComparisonRequest {
  version_a_id: string;
  version_b_id: string;
  version_type_a?: string;
  version_type_b?: string;
}

export interface VersionComparisonResult {
  comparison_id: string;
  version_a: VersionSnapshot;
  version_b: VersionSnapshot;
  created_at: string;
  score_a: number;
  score_b: number;
  score_delta: number;
  risk_level_a: string;
  risk_level_b: string;
  risk_shift: 'IMPROVED' | 'DEGRADED' | 'UNCHANGED';
  critical_issues_a: number;
  critical_issues_b: number;
  missing_declarations_a: number;
  missing_declarations_b: number;
  declaration_diffs: FieldDiffItem[];
  added_declarations: FieldDiffItem[];
  removed_declarations: FieldDiffItem[];
  changed_declarations: FieldDiffItem[];
  unchanged_declarations: FieldDiffItem[];
  review_required_declarations: FieldDiffItem[];
  mrp_diff?: FieldDiffItem | null;
  quantity_diff?: FieldDiffItem | null;
  manufacturer_diff?: FieldDiffItem | null;
  fssai_diff?: FieldDiffItem | null;
  ingredients_diff?: IngredientsDiff | null;
  nutrition_diff?: NutritionDiff | null;
  rule_diffs: RuleStateDiff[];
  issue_resolutions: IssueResolutionItem[];
  resolved_issues_count: number;
  remaining_issues_count: number;
  new_issues_count: number;
  summary_verdict: string;
  notes: string[];
}

// ════════════════════════════════════════════════════════════════════════════
// SECTION 10: HUMAN VERIFICATION / OFFICER WORKFLOW TYPES
// ════════════════════════════════════════════════════════════════════════════

export type ReviewStatus = 
  | 'PENDING_REVIEW' 
  | 'ASSIGNED' 
  | 'IN_REVIEW' 
  | 'CORRECTION_REQUIRED' 
  | 'VERIFIED_PASS' 
  | 'VERIFIED_FAIL' 
  | 'VERIFIED_NEEDS_REVIEW' 
  | 'REJECTED' 
  | 'ESCALATED' 
  | 'REOPENED' 
  | 'CLOSED';

export type HumanVerifiedStatus = 
  | 'VERIFIED_PASS' 
  | 'VERIFIED_FAIL' 
  | 'VERIFIED_NEEDS_REVIEW' 
  | 'REJECTED' 
  | 'NOT_VERIFIED';

export interface FieldCorrectionItem {
  field_name: string;
  field_label: string;
  original_value?: string | null;
  corrected_value: string;
  reason?: string | null;
  officer_username: string;
  officer_role: string;
  timestamp: string;
  evidence_id?: string | null;
}

export interface OfficerCommentItem {
  comment_id: string;
  comment_type: 'GENERAL' | 'CORRECTION' | 'REJECTION' | 'ESCALATION' | 'REOPEN' | 'SIGN_OFF';
  text: string;
  officer_username: string;
  officer_role: string;
  timestamp: string;
}

export interface ReviewHistoryEvent {
  event_id: string;
  action: string;
  actor_username: string;
  actor_role: string;
  details: string;
  previous_state?: string | null;
  new_state?: string | null;
  timestamp: string;
  metadata: Record<string, any>;
}

export interface ReviewItem {
  review_id: string;
  analysis_id: string;
  target_type: string;
  product_name: string;
  status: ReviewStatus;
  assigned_officer?: string | null;
  assigned_by?: string | null;
  assigned_at?: string | null;
  created_at: string;
  updated_at: string;
  verified_by?: string | null;
  verified_at?: string | null;
  final_human_status?: string | null;
  ai_score: number;
  ai_risk_level: string;
  ai_status: string;
  critical_issues_count: number;
  review_reasons: string[];
  age_hours: number;
}

export interface ReviewDetailResponse {
  review_id: string;
  analysis_id: string;
  target_type: string;
  product_name: string;
  status: ReviewStatus;
  assigned_officer?: string | null;
  assigned_by?: string | null;
  assigned_at?: string | null;
  created_at: string;
  updated_at: string;
  verified_by?: string | null;
  verified_at?: string | null;
  final_human_status?: string | null;
  ai_score: number;
  ai_risk_level: string;
  ai_status: string;
  human_score?: number | null;
  human_risk_level?: string | null;
  critical_issues_count: number;
  review_reasons: string[];
  ai_snapshot: Record<string, any>;
  human_verified_result?: Record<string, any> | null;
  field_corrections: FieldCorrectionItem[];
  evidence_modifications: Array<Record<string, any>>;
  comments: OfficerCommentItem[];
  history: ReviewHistoryEvent[];
}

export interface OfficerWorkloadItem {
  officer_username: string;
  officer_name: string;
  officer_role: string;
  total_assigned: number;
  pending_count: number;
  in_review_count: number;
  completed_count: number;
  escalated_count: number;
}

export interface OfficerDashboardSummary {
  total_queue: number;
  pending_review: number;
  assigned: number;
  in_review: number;
  verified: number;
  rejected: number;
  escalated: number;
  reopened: number;
  workload: OfficerWorkloadItem[];
}

export interface AIvsHumanDiffItem {
  field_name: string;
  field_label: string;
  ai_value?: string | null;
  human_value?: string | null;
  is_changed: boolean;
  change_type: 'UNCHANGED' | 'CORRECTED' | 'ADDED' | 'REMOVED';
  officer_username?: string | null;
  timestamp?: string | null;
  reason?: string | null;
}

export interface AIvsHumanComparison {
  analysis_id: string;
  review_id: string;
  ai_score: number;
  human_score: number;
  score_delta: number;
  ai_risk_level: string;
  human_risk_level: string;
  ai_status: string;
  human_status: string;
  total_fields_evaluated: number;
  corrected_fields_count: number;
  field_diffs: AIvsHumanDiffItem[];
  summary: string;
}

// ── Section 13: External Verification & Cross-Checking Types ──

export type CrossCheckStatus =
  | 'MATCH'
  | 'PARTIAL_MATCH'
  | 'MISMATCH'
  | 'NOT_APPLICABLE'
  | 'UNVERIFIED'
  | 'NOT_FOUND'
  | 'REVIEW_REQUIRED';

export type ApiAvailabilityState = 'ONLINE' | 'OFFLINE' | 'UNCONFIGURED' | 'DEGRADED';

export type VerificationConfidenceTier = 'HIGH' | 'MEDIUM' | 'LOW' | 'ZERO';

export interface CrossCheckFieldResult {
  check_type: string;
  field_name: string;
  extracted_value?: string | null;
  registry_value?: string | null;
  status: CrossCheckStatus;
  similarity_score: number;
  matched_tokens: string[];
  discrepancy_details?: string | null;
  verification_source: string;
  is_critical_mismatch: boolean;
}

export interface VerificationConfidence {
  score: number;
  tier: VerificationConfidenceTier;
  checksum_passed: boolean;
  registry_confirmed: boolean;
  field_agreement_rate: number;
  cache_freshness_sec?: number | null;
  factors?: Record<string, any>;
  verdict: string;
}

export interface ApiAvailabilityStatus {
  service_name: string;
  state: ApiAvailabilityState;
  endpoint?: string | null;
  last_checked?: string | null;
  latency_ms?: number | null;
  message: string;
}

export interface ExternalVerificationSummary {
  fssai_verification?: FSSAIVerificationResult | null;
  gs1_verification?: GS1VerificationResult | null;
  qr_payload?: string | null;
  barcode_detected?: string | null;
  cross_checks: CrossCheckFieldResult[];
  overall_consistency_status: CrossCheckStatus;
  confidence: VerificationConfidence;
  api_availability: Record<string, ApiAvailabilityStatus>;
  offline_mode: boolean;
  verification_timestamp: string;
  verification_sources: string[];
  discrepancies: string[];
  summary_verdict: string;
}

// ============================================================================
// BARCODE & PRODUCT IDENTITY TYPES
// ============================================================================

export interface FieldEvidenceItem {
  value?: string | null;
  normalized_value?: string | null;
  confidence?: number;
  source?: string;
  bounding_box?: number[] | null;
  image_id?: string | null;
  status?: string;
  explanation?: string | null;
  nearby_text?: string | null;
  raw_tokens?: string[];
}

export interface QRContentData {
  raw_value: string;
  content_type?: string;
  is_safe_url?: boolean;
  parsed_url?: string | null;
  hostname?: string | null;
  gs1_ai_data?: Record<string, any> | null;
  bounding_box?: number[] | null;
  image_id?: string | null;
  confidence?: number;
  status?: string;
  security_warning?: string | null;
}

export interface BarcodeIdentityData {
  raw_value: string;
  symbology?: string;
  is_valid_checksum?: boolean;
  country_of_origin?: string | null;
  country_flag?: string | null;
  gs1_prefix?: string | null;
  bounding_box?: number[] | null;
  image_id?: string | null;
  confidence?: number;
  status?: string;
  registered_brand?: string | null;
  registered_product?: string | null;
  registered_net_quantity?: string | null;
  registered_company?: string | null;
  provenance_label?: string | null;
}

export interface BarcodeItem {
  raw_value: string;
  symbology: string;
  is_valid_checksum?: boolean;
  country_of_origin?: string | null;
  country_flag?: string | null;
  gs1_prefix?: string | null;
  bounding_box?: number[] | null;
  image_id?: string | null;
  confidence?: number;
  status?: string;
  digital_link_data?: any;
  fssai_from_barcode?: string | null;
  product_name?: string | null;
  brand_name?: string | null;
  company_name?: string | null;
  net_quantity?: string | null;
  category?: string | null;
  image_url?: string | null;
  registered_data?: any;
}

export interface ConflictItem {
  field_name: string;
  source_a: string;
  value_a: any;
  source_b: string;
  value_b: any;
  severity?: string;
  description?: string;
}

export interface CrossValidationSummary {
  status?: string;
  has_conflicts?: boolean;
  conflicts?: ConflictItem[];
  fssai_cross_check?: any;
  barcode_cross_check?: any;
  summary_message?: string;
}

export interface DateDeclarations {
  manufacture_date?: FieldEvidenceItem;
  date_of_manufacture?: FieldEvidenceItem;
  expiry_date?: FieldEvidenceItem;
  best_before?: FieldEvidenceItem;
}

export interface ConsumerCareDeclarations {
  helpline?: FieldEvidenceItem;
  phone?: FieldEvidenceItem;
  email?: FieldEvidenceItem;
  address?: FieldEvidenceItem;
}

export interface FoodDeclarations {
  is_food?: boolean;
  fssai_license?: FieldEvidenceItem;
  veg_nonveg?: FieldEvidenceItem;
  veg_nonveg_status?: any;
  ingredients?: any;
  nutritional_info?: FieldEvidenceItem;
  allergens?: any;
}

export interface OtherDeclarations {
  [key: string]: any;
}

export interface ProductIdentity {
  product_name?: FieldEvidenceItem;
  brand_name?: FieldEvidenceItem;
  product_variant?: FieldEvidenceItem;
  product_category?: FieldEvidenceItem;
  mrp?: FieldEvidenceItem;
  net_quantity?: FieldEvidenceItem;
  fssai_license_number?: FieldEvidenceItem;
  fssai_number?: string | null;
  fssai_provenance_label?: string | null;
  fssai_external_verified?: boolean;
  fssai_state_name?: string | null;
  fssai_license_type?: string | null;
  fssai_verification_details?: Record<string, any> | null;
  barcode_gtin?: string | null;
  barcode_provenance_label?: string | null;
  barcode_external_verified?: boolean;
  barcodes?: BarcodeIdentityData[];
  qr_codes?: QRContentData[];
  dates?: DateDeclarations;
  consumer_care?: ConsumerCareDeclarations;
  customer_care?: ConsumerCareDeclarations;
  food_declarations?: FoodDeclarations;
  other_declarations?: OtherDeclarations;
  cross_validation?: CrossValidationSummary;
  all_declarations?: Record<string, any>;
  fssai_verification?: any;
  barcode_verification?: any;
  conflicts?: ConflictItem[];
  manufacturer?: FieldEvidenceItem;
  packer?: FieldEvidenceItem;
  importer?: FieldEvidenceItem;
  marketer?: FieldEvidenceItem;
  complete_address?: FieldEvidenceItem;
  country_of_origin?: FieldEvidenceItem;
  unit?: FieldEvidenceItem;
  batch_number?: FieldEvidenceItem;
  image_quality_status?: string;
  quality_reasons?: string[];
}

export type ExternalVerificationStatusType =
  | 'OCR_DETECTED'
  | 'FORMAT_VALID'
  | 'EXTERNALLY_VERIFIED'
  | 'EXTERNAL_LOOKUP_FAILED'
  | 'EXTERNAL_DATA_NOT_FOUND'
  | 'EXTERNAL_VERIFICATION_UNAVAILABLE';

export type ComparisonResultType =
  | 'MATCH'
  | 'MISMATCH'
  | 'NOT_COMPARABLE'
  | 'NOT_FOUND'
  | 'NOT_VERIFIED';

export interface FSSAIExtractionData {
  number: string;
  source: string;
  confidence: number;
  format_valid: boolean;
  raw_context?: string | null;
  state_code?: string | null;
  state_name?: string | null;
  registration_type?: string | null;
  bounding_box?: number[] | null;
}

export interface BarcodeExtractionData {
  value: string;
  type: string;
  source: string;
  format_valid: boolean;
  checksum_valid?: boolean | null;
  country_of_origin?: string | null;
  bounding_box?: number[] | null;
}

export interface ExternalFSSAIData {
  status: ExternalVerificationStatusType;
  source: string;
  business_name?: string | null;
  registered_address?: string | null;
  licence_status?: string | null;
  licence_type?: string | null;
  valid_upto?: string | null;
  lookup_timestamp?: string | null;
  failure_reason?: string | null;
  manual_verification_url?: string | null;
  manual_verification_instructions?: string | null;
  provenance?: string | null;
}

export interface ExternalProductData {
  status: ExternalVerificationStatusType;
  source: string;
  product_name?: string | null;
  brand?: string | null;
  manufacturer?: string | null;
  net_quantity?: string | null;
  category?: string | null;
  mrp?: string | null;
  lookup_timestamp?: string | null;
  failure_reason?: string | null;
  manual_verification_url?: string | null;
  manual_verification_instructions?: string | null;
  provenance?: string | null;
}

export interface CrossSourceFieldComparison {
  field: string;
  package_value?: string | null;
  external_value?: string | null;
  result: ComparisonResultType;
  details?: string | null;
}

export interface ExternalProductVerificationPipelineResult {
  fssai_extraction?: FSSAIExtractionData | null;
  external_fssai?: ExternalFSSAIData | null;
  barcode_extractions?: BarcodeExtractionData[];
  external_product?: ExternalProductData | null;
  cross_source_comparisons?: CrossSourceFieldComparison[];
  overall_pipeline_status: string;
  summary_notes?: string[];
}

export interface ListingFieldComparisonItem {
  field: string;
  field_label: string;
  status: 'MATCH' | 'MISMATCH' | 'INSUFFICIENT_DATA';
  package_value?: string | null;
  listing_value?: string | null;
  explanation: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
}

export interface ListingCheckResponse {
  id: string;
  source_mode: string;
  source_url?: string | null;
  listing_text: string;
  extracted_info: ProductInfo;
  compliance_result: ComplianceResult;
  score: number;
  status: string;
  comparison_performed: boolean;
  package_analysis_id?: string | null;
  package_product_name?: string | null;
  field_comparisons: ListingFieldComparisonItem[];
  match_count: number;
  mismatch_count: number;
  insufficient_data_count: number;
  cross_verdict?: 'COMPLIANT_MATCH' | 'MISMATCH_DETECTED' | 'INSUFFICIENT_ONLINE_DATA' | 'NO_OVERLAPPING_FIELDS' | null;
  created_at: string;
}


