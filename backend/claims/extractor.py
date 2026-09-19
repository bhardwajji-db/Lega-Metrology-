"""
MetrCheck AI — Claim Extraction Engine
Extracts promotional and regulatory package claims from existing OCR words and panels.
Reuses existing OCR output, word bounding boxes, and image panel metadata.
Enforces security constraints against prompt injections and malicious OCR text.
"""

import re
import html
from typing import List, Dict, Any, Optional, Tuple
from models.schemas import OCRWord, ProductImageEvidence
from claims.models import ClaimCategory, ClaimFinding, ClaimConfidenceBreakdown, ClaimAssessment, ClaimStatus
from claims.rule_engine import claim_rule_registry, RegulatoryRule

# Maximum length for untrusted package text to prevent DoS
MAX_CLAIM_TEXT_LEN = 160

# Absolute claim keywords that require heightened scrutiny
ABSOLUTE_KEYWORDS = {
    "100%", "100 percent", "zero", "0%", "no", "free", "pure", "only",
    "best", "number 1", "no. 1", "no 1", "#1", "completely", "guaranteed", "all"
}

# Comparative claim keywords
COMPARATIVE_KEYWORDS = {
    "no. 1", "no 1", "number 1", "#1", "best", "better", "superior",
    "leading", "most trusted", "more than", "highest"
}

# High risk keywords (medical, disease cure, clinically proven, doctor recommended)
HIGH_RISK_KEYWORDS = {
    "cure", "cures", "treat", "treats", "prevent", "prevents", "disease",
    "cancer", "diabetes", "anti-covid", "anti covid", "infection",
    "clinically proven", "scientifically proven", "doctor recommended",
    "doctor's choice", "guaranteed weight loss", "burns fat", "100% disease protection"
}

# Prompt injection signatures to neutralize safely
INJECTION_SIGNATURES = [
    r'ignore\s+previous\s+instructions',
    r'system\s+prompt',
    r'you\s+are\s+now',
    r'disregard\s+all',
    r'<script[\s\S]*?>',
    r'javascript:',
    r'drop\s+table',
    r'union\s+select'
]


def sanitize_package_text(raw_text: str) -> str:
    """Sanitizes untrusted package text, neutralizing injections while preserving product declaration."""
    if not raw_text:
        return ""
    # Strip HTML tags and entities
    clean = html.escape(raw_text)
    # Neutralize injection attempts by replacing keywords with safe tokens
    for pattern in INJECTION_SIGNATURES:
        clean = re.sub(pattern, "[FILTERED_UNTRUSTED_INPUT]", clean, flags=re.IGNORECASE)
    # Remove control characters
    clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', clean)
    return clean.strip()


class ExtractedRawClaim:
    def __init__(
        self,
        claim_text: str,
        normalized_claim: str,
        category: ClaimCategory,
        source_panel: str = "FRONT",
        image_index: int = 0,
        bounding_box: Optional[List[int]] = None,
        ocr_confidence: float = 85.0,
        matched_rule: Optional[RegulatoryRule] = None,
        is_absolute: bool = False,
        is_comparative: bool = False,
        is_high_risk: bool = False
    ):
        self.claim_text = claim_text
        self.normalized_claim = normalized_claim
        self.category = category
        self.source_panel = source_panel
        self.image_index = image_index
        self.bounding_box = bounding_box
        self.ocr_confidence = ocr_confidence
        self.matched_rule = matched_rule
        self.is_absolute = is_absolute
        self.is_comparative = is_comparative
        self.is_high_risk = is_high_risk


class ClaimExtractor:
    def __init__(self):
        self.rule_registry = claim_rule_registry

    def extract_claims(
        self,
        ocr_text: str,
        images: Optional[List[ProductImageEvidence]] = None
    ) -> List[ExtractedRawClaim]:
        """
        Extract claims from OCR text and per-image evidence panels.
        Reuses existing OCR bounding boxes and confidence scores.
        """
        raw_claims: List[ExtractedRawClaim] = []
        seen_normalized: set = set()

        # Phase 1: Scan per-image panel tokens and lines for spatial provenance
        if images and len(images) > 0:
            for img_idx, img_ev in enumerate(images):
                panel_label = (img_ev.label or f"Panel {img_idx+1}").upper()
                panel_text = img_ev.ocr_text or ""
                words = img_ev.words or []
                panel_claims = self._extract_from_panel(panel_text, words, panel_label, img_idx)
                for c in panel_claims:
                    if c.normalized_claim not in seen_normalized:
                        seen_normalized.add(c.normalized_claim)
                        raw_claims.append(c)

        # Phase 2: If no image panels provided or additional claims in combined text
        if not raw_claims and ocr_text:
            text_claims = self._extract_from_text(ocr_text, panel="FRONT", image_index=0)
            for c in text_claims:
                if c.normalized_claim not in seen_normalized:
                    seen_normalized.add(c.normalized_claim)
                    raw_claims.append(c)

        return raw_claims

    def _extract_from_panel(
        self,
        text: str,
        words: List[OCRWord],
        panel: str,
        image_index: int
    ) -> List[ExtractedRawClaim]:
        """Extract claims from a specific package panel with word-level bounding boxes."""
        extracted: List[ExtractedRawClaim] = []
        if not text:
            return extracted

        sanitized_text = sanitize_package_text(text)
        rules = self.rule_registry.get_all_rules()

        # Check all active configured regulatory rules
        for rule in rules:
            if not rule.enabled:
                continue
            for pattern in rule.patterns:
                # Search using word boundaries where appropriate
                regex_pattern = r'(?:\b|^)' + re.escape(pattern) + r'(?:\b|$)'
                match = re.search(regex_pattern, sanitized_text, re.IGNORECASE)
                if match:
                    matched_text = match.group(0).strip()
                    if len(matched_text) > MAX_CLAIM_TEXT_LEN:
                        matched_text = matched_text[:MAX_CLAIM_TEXT_LEN]

                    norm = pattern.lower().strip()
                    bbox, ocr_conf = self._find_bounding_box_for_phrase(norm, words)

                    is_abs = rule.is_absolute or any(k in norm for k in ABSOLUTE_KEYWORDS)
                    is_cmp = rule.is_comparative or any(k in norm for k in COMPARATIVE_KEYWORDS)
                    is_hr = rule.is_high_risk or any(k in norm for k in HIGH_RISK_KEYWORDS)

                    extracted.append(ExtractedRawClaim(
                        claim_text=matched_text,
                        normalized_claim=norm,
                        category=rule.category,
                        source_panel=panel,
                        image_index=image_index,
                        bounding_box=bbox,
                        ocr_confidence=ocr_conf,
                        matched_rule=rule,
                        is_absolute=is_abs,
                        is_comparative=is_cmp,
                        is_high_risk=is_hr
                    ))
                    break  # Matched this rule, move to next rule

        # Also search for high-risk / absolute claim patterns not covered by explicit rules
        extracted.extend(self._extract_open_patterns(sanitized_text, words, panel, image_index))

        return extracted

    def _extract_from_text(
        self,
        text: str,
        panel: str = "FRONT",
        image_index: int = 0
    ) -> List[ExtractedRawClaim]:
        """Fallback extraction for text-only input without OCR word boxes."""
        sanitized_text = sanitize_package_text(text)
        extracted: List[ExtractedRawClaim] = []
        rules = self.rule_registry.get_all_rules()

        for rule in rules:
            if not rule.enabled:
                continue
            for pattern in rule.patterns:
                regex_pattern = r'(?:\b|^)' + re.escape(pattern) + r'(?:\b|$)'
                match = re.search(regex_pattern, sanitized_text, re.IGNORECASE)
                if match:
                    matched_text = match.group(0).strip()
                    norm = pattern.lower().strip()
                    is_abs = rule.is_absolute or any(k in norm for k in ABSOLUTE_KEYWORDS)
                    is_cmp = rule.is_comparative or any(k in norm for k in COMPARATIVE_KEYWORDS)
                    is_hr = rule.is_high_risk or any(k in norm for k in HIGH_RISK_KEYWORDS)

                    extracted.append(ExtractedRawClaim(
                        claim_text=matched_text,
                        normalized_claim=norm,
                        category=rule.category,
                        source_panel=panel,
                        image_index=image_index,
                        bounding_box=None,
                        ocr_confidence=90.0,
                        matched_rule=rule,
                        is_absolute=is_abs,
                        is_comparative=is_cmp,
                        is_high_risk=is_hr
                    ))
                    break

        extracted.extend(self._extract_open_patterns(sanitized_text, [], panel, image_index))
        return extracted

    def _extract_open_patterns(
        self,
        text: str,
        words: List[OCRWord],
        panel: str,
        image_index: int
    ) -> List[ExtractedRawClaim]:
        """Detect additional open-pattern claims using grammatical patterns (e.g. 100% X, Zero X, Cures X)."""
        extra: List[ExtractedRawClaim] = []

        # 1. Open Absolute Claims: e.g. "100% [A-Za-z]+", "Zero [A-Za-z]+"
        abs_matches = re.finditer(r'\b(100%\s+[a-zA-Z]{3,20}|zero\s+[a-zA-Z]{3,20}|completely\s+[a-zA-Z]{3,20})\b', text, re.IGNORECASE)
        for m in abs_matches:
            raw_c = m.group(1).strip()
            norm = raw_c.lower()
            if not self.rule_registry.find_matching_rule(norm):
                bbox, conf = self._find_bounding_box_for_phrase(norm, words)
                extra.append(ExtractedRawClaim(
                    claim_text=raw_c,
                    normalized_claim=norm,
                    category=ClaimCategory.ABSOLUTE,
                    source_panel=panel,
                    image_index=image_index,
                    bounding_box=bbox,
                    ocr_confidence=conf,
                    matched_rule=None,
                    is_absolute=True,
                    is_comparative=False,
                    is_high_risk=False
                ))

        # 2. Open Comparative Claims: e.g. "No. 1 [A-Za-z]+", "Best in [A-Za-z]+"
        cmp_matches = re.finditer(r'\b(no\.?\s*1\s+[a-zA-Z]{3,20}|best\s+(?:in|for)\s+[a-zA-Z]{3,20})\b', text, re.IGNORECASE)
        for m in cmp_matches:
            raw_c = m.group(1).strip()
            norm = raw_c.lower()
            if not self.rule_registry.find_matching_rule(norm):
                bbox, conf = self._find_bounding_box_for_phrase(norm, words)
                extra.append(ExtractedRawClaim(
                    claim_text=raw_c,
                    normalized_claim=norm,
                    category=ClaimCategory.COMPARATIVE,
                    source_panel=panel,
                    image_index=image_index,
                    bounding_box=bbox,
                    ocr_confidence=conf,
                    matched_rule=None,
                    is_absolute=True,
                    is_comparative=True,
                    is_high_risk=False
                ))

        # 3. Open Medical / Cure claims: e.g. "Cures [A-Za-z]+", "Prevents [A-Za-z]+"
        med_matches = re.finditer(r'\b(cures?\s+[a-zA-Z]{3,20}|prevents?\s+[a-zA-Z]{3,20}|treats?\s+[a-zA-Z]{3,20})\b', text, re.IGNORECASE)
        for m in med_matches:
            raw_c = m.group(1).strip()
            norm = raw_c.lower()
            if not self.rule_registry.find_matching_rule(norm):
                bbox, conf = self._find_bounding_box_for_phrase(norm, words)
                extra.append(ExtractedRawClaim(
                    claim_text=raw_c,
                    normalized_claim=norm,
                    category=ClaimCategory.MEDICAL,
                    source_panel=panel,
                    image_index=image_index,
                    bounding_box=bbox,
                    ocr_confidence=conf,
                    matched_rule=None,
                    is_absolute=False,
                    is_comparative=False,
                    is_high_risk=True
                ))

        return extra

    def _find_bounding_box_for_phrase(
        self,
        phrase: str,
        words: List[OCRWord]
    ) -> Tuple[Optional[List[int]], float]:
        """Locates the bounding box and average confidence for a phrase within OCR words."""
        if not words:
            return None, 88.0

        phrase_tokens = [re.sub(r'[^\w\d%]', '', t.lower()) for t in phrase.split() if t.strip()]
        if not phrase_tokens:
            return None, 88.0

        matched_words: List[OCRWord] = []
        for i in range(len(words)):
            w_clean = re.sub(r'[^\w\d%]', '', words[i].text.lower())
            if w_clean == phrase_tokens[0] or phrase_tokens[0] in w_clean:
                candidate_words = [words[i]]
                match_all = True
                for k in range(1, len(phrase_tokens)):
                    if i + k < len(words):
                        next_w = re.sub(r'[^\w\d%]', '', words[i + k].text.lower())
                        if phrase_tokens[k] in next_w or next_w in phrase_tokens[k]:
                            candidate_words.append(words[i + k])
                        else:
                            match_all = False
                            break
                    else:
                        match_all = False
                        break
                if match_all:
                    matched_words = candidate_words
                    break

        if not matched_words:
            # Fallback: find any word matching the primary token
            for w in words:
                w_clean = re.sub(r'[^\w\d%]', '', w.text.lower())
                if any(t in w_clean for t in phrase_tokens):
                    matched_words.append(w)
                    if len(matched_words) >= len(phrase_tokens):
                        break

        if matched_words:
            min_x = min(w.bbox[0] for w in matched_words)
            min_y = min(w.bbox[1] for w in matched_words)
            max_x = max(w.bbox[2] for w in matched_words)
            max_y = max(w.bbox[3] for w in matched_words)
            avg_conf = sum(w.confidence for w in matched_words) / len(matched_words)
            return [min_x, min_y, max_x, max_y], round(avg_conf, 1)

        return None, 85.0


claim_extractor = ClaimExtractor()
