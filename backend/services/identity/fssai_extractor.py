"""
MetrCheck AI — Dedicated FSSAI Information Extractor
Detects FSSAI and Food Safety Licence / Registration declarations, extracts 14-digit identifiers,
identifies nearby statutory context, and performs state code and license tier validation.
"""

import re
import logging
from typing import Optional, List, Dict, Any, Tuple
from models.schemas import OCRWord, ProductImageEvidence
from services.identity.schemas import FieldEvidenceItem, FieldStatus

logger = logging.getLogger(__name__)

# FSSAI State Code Registry (Digits 2-3 of standard 14-digit license)
FSSAI_STATE_CODES: Dict[str, str] = {
    "00": "Central Licensing Authority",
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "25": "Daman and Diu",
    "26": "Dadra and Nagar Haveli",
    "27": "Maharashtra",
    "28": "Andhra Pradesh",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Ladakh",
}

FSSAI_PATTERNS = [
    # Explicit FSSAI label followed by number (supports lic, lc, li, registration)
    re.compile(r'(?:fssai|fssal|tssai|issai|fssat|fssa)[\s.:\-_/]*(?:lic(?:ence|ense)?[\s.:\-_/]*(?:no\.?|num\.?)?|lc[\s.:\-_/]*(?:no\.?|num\.?)?|li[\s.:\-_/]*(?:no\.?|num\.?)?|registration[\s.:\-_/]*no\.?|no\.?)?[\s.:\-_/]*\b(1\d{13}|2\d{13})\b', re.IGNORECASE),
    # Licence No. followed by 14-digit number starting with 1 or 2
    re.compile(r'\b(?:lic(?:ence|ense)?[\s.:\-_/]*(?:no\.?|num\.?)?|registration[\s.:\-_/]*no\.?)[\s.:\-_/]*\b(1\d{13}|2\d{13})\b', re.IGNORECASE),
    # Standalone 14-digit number with fssai within 80 chars
    re.compile(r'(?:(?:fssai|fssal|fssat|fssa)[^\n]{0,80}?)\b(1\d{13}|2\d{13})\b', re.IGNORECASE),
    # Number followed by fssai
    re.compile(r'\b(1\d{13}|2\d{13})\b[^\n]{0,60}?(?:fssai|fssal|fssat|fssa)', re.IGNORECASE),
]


class FSSAIInformationExtractor:
    """
    Dedicated FSSAI extraction and validation engine.
    """

    @classmethod
    def validate_structure(cls, license_num: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validates 14-digit format and decodes state and tier.
        Returns: (is_valid, state_name, license_type)
        """
        clean = re.sub(r'\D', '', str(license_num or ""))
        if len(clean) != 14:
            return False, None, None

        first_digit = clean[0]
        if first_digit not in ("1", "2"):
            return False, None, None
        license_type = "STATE_OR_CENTRAL_LICENSE" if first_digit == "1" else "BASIC_REGISTRATION"
        state_code = clean[1:3]
        state_name = FSSAI_STATE_CODES.get(state_code, f"State Code {state_code}")

        if state_code == "00":
            license_type = "CENTRAL_LICENSE"

        return True, state_name, license_type

    @classmethod
    def extract_fssai(
        cls,
        text: str,
        images: Optional[List[ProductImageEvidence]] = None
    ) -> Tuple[FieldEvidenceItem, Optional[str], Optional[str]]:
        """
        Extract FSSAI license number and associated evidence.
        Returns: (FieldEvidenceItem, state_name, license_type)
        """
        if not text or not str(text).strip():
            return FieldEvidenceItem(status=FieldStatus.NOT_FOUND), None, None

        text_str = str(text)
        detected_license: Optional[str] = None
        nearby_text: Optional[str] = None
        match_confidence: float = 0.0

        # Step 1: Scan with targeted regexes
        for pat in FSSAI_PATTERNS:
            m = pat.search(text_str)
            if m:
                cand = m.group(1).strip()
                if len(cand) == 14 and cand.isdigit():
                    detected_license = cand
                    start = max(0, m.start() - 30)
                    end = min(len(text_str), m.end() + 30)
                    nearby_text = text_str[start:end].replace('\n', ' ').strip()
                    match_confidence = 94.0
                    break

        # Step 2: Fallback scan for standalone 14-digit tokens near "fssai"
        if not detected_license and ("fssai" in text_str.lower() or "lic" in text_str.lower()):
            for m in re.finditer(r'\b(1\d{13}|2\d{13})\b', text_str):
                cand = m.group(1)
                # Ensure context mentions food or licensing
                window = text_str[max(0, m.start() - 100):min(len(text_str), m.end() + 100)].lower()
                if any(k in window for k in ("fssai", "lic", "license", "food", "fssl")):
                    detected_license = cand
                    nearby_text = text_str[max(0, m.start() - 40):min(len(text_str), m.end() + 40)].replace('\n', ' ').strip()
                    match_confidence = 88.0
                    break

        # Step 2B: High-recall contextual OCR noise repair (O/0, l/1, S/5, spaces, hyphens)
        if not detected_license:
            try:
                from ocr.repair import repair_fssai_license
                repaired = repair_fssai_license(text_str)
                if repaired and len(repaired) == 14 and repaired.isdigit():
                    detected_license = repaired
                    match_confidence = 86.0
                    nearby_text = f"Contextual OCR repair detected licence: {repaired}"
            except Exception as e:
                logger.debug(f"[FSSAI] repair_fssai_license failed: {e}")

        if not detected_license:
            # If the word "fssai" is present but no 14-digit number could be parsed
            if "fssai" in text_str.lower():
                return FieldEvidenceItem(
                    value=None,
                    status=FieldStatus.REVIEW_REQUIRED,
                    explanation="FSSAI indicator detected on packaging, but 14-digit license number is unreadable or missing.",
                    confidence=45.0,
                    source="OCR"
                ), None, None

            return FieldEvidenceItem(
                value=None,
                status=FieldStatus.NOT_FOUND,
                explanation="No FSSAI licence or registration declaration found on label.",
                confidence=0.0,
                source="OCR"
            ), None, None

        # Step 3: Validate structure
        is_valid, state_name, lic_type = cls.validate_structure(detected_license)

        # Step 4: Locate bounding box from image evidence tokens
        best_box: Optional[List[int]] = None
        source_img_id: Optional[str] = "Back"

        if images:
            for ev in images:
                if not ev.words:
                    continue
                for w in ev.words:
                    if detected_license in w.text or w.text in detected_license:
                        best_box = w.bbox
                        source_img_id = ev.label or ev.filename
                        match_confidence = max(match_confidence, w.confidence)
                        break
                if best_box:
                    break

        status = FieldStatus.FOUND if match_confidence >= 70.0 else FieldStatus.LOW_CONFIDENCE
        if not is_valid:
            status = FieldStatus.REVIEW_REQUIRED

        item = FieldEvidenceItem(
            value=detected_license,
            normalized_value=detected_license,
            confidence=round(match_confidence, 1),
            source="OCR",
            bounding_box=best_box,
            image_id=source_img_id,
            status=status,
            explanation=f"FSSAI Licence Number ({state_name or 'General'}) extracted from label text.",
            nearby_text=nearby_text
        )

        return item, state_name, lic_type


fssai_extractor = FSSAIInformationExtractor()
