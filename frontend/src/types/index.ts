export interface OCRWord {
  text: string;
  confidence: number;
  bbox: number[]; // [x1, y1, x2, y2]
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
  other_declarations: Record<string, string>;
  declaration_confidences?: Record<string, number>;
  field_provenance?: Record<string, FieldProvenance>;
  extraction_mode: string;
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
}

export interface EvidenceItem {
  id?: string;
  image_index: number;
  image_label: string;
  text: string;
  normalized_value?: string | null;
  bbox?: number[] | null; // [x1, y1, x2, y2]
  geometry_type?: 'WORD_UNION' | 'LINE' | 'TOKEN' | 'NONE';
  match_method?: 'DIRECT_OCR' | 'MULTI_TOKEN_OCR' | 'CONTEXTUAL_OCR' | 'SEMANTIC_PANEL' | 'EXACT_TOKEN' | 'TEXT_NORMALIZED' | 'TOKEN_SEQUENCE' | 'FIELD_MATCH' | 'NONE';
  confidence: number;
  evidence_status: 'VERIFIED' | 'CONTEXTUAL' | 'NEEDS_REVIEW' | 'NO_EVIDENCE' | 'NOT_APPLICABLE' | 'UNAVAILABLE';
  evidence_type?: 'DIRECT_OCR' | 'DERIVED_FIELD' | 'PROVISO_DELEGATION' | 'NONE';
  explanation?: string | null;
  source_token_ids?: string[];
  field_type?: 'FIELD' | 'PANEL' | 'REGION';
  quality_score?: number | null;
  analysis_id?: string | null;
}

export interface ComplianceCheck {
  rule_id: string;
  field: string;
  field_label: string;
  required: boolean;
  detected: boolean;
  detected_value: string | null;
  severity: string;
  status: string;
  description: string;
  source: string;
  explanation: string | null;
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
  rule_id: string;
  field: string;
  field_label: string;
  required: boolean;
  severity: string;
  description: string;
  source: string;
  recommendation: string;
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
