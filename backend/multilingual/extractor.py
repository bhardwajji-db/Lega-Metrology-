"""
MetrCheck AI — Multilingual Canonical Statutory Field Extraction Engine

Bridges packaging text in 10 supported languages into canonical internal fields:
- MRP
- NET_QUANTITY
- MANUFACTURER / MARKETED_BY
- DATES (Mfg / Pkg / Expiry / Best Before)
- CONSUMER_CARE (Phone, Email, Address)
- FSSAI_LICENSE
- INGREDIENTS
- NUTRITION
- ALLERGENS
- COUNTRY_OF_ORIGIN

Features:
- Deterministic data-driven extraction from centralized JSON dictionaries
- Full Indic digit, unit, currency, and date normalization
- Preservation of original OCR text, bounding boxes, language, script, and separate confidences
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from models.schemas import ProductInfo, FieldProvenance, ProductImageEvidence, OCRWord
from multilingual.registry import SUPPORTED_LANGUAGES, normalize_language_code
from multilingual.detector import detect_token_script_and_language, detect_document_languages
from multilingual.normalizer import (
    normalize_indic_digits,
    normalize_currency,
    normalize_units,
    normalize_multilingual_date,
    normalize_text_comprehensive
)
from multilingual.dictionaries import load_all_dictionaries
from ocr.repair import repair_fssai_license, repair_net_quantity, repair_mrp

logger = logging.getLogger(__name__)


class MultilingualExtractor:
    """
    Language-aware statutory declaration candidate extractor.
    Extracts canonical field values from multilingual packaging text and produces detailed provenance.
    """

    def __init__(self):
        self.dictionaries = load_all_dictionaries()

    def extract_multilingual_fields(
        self,
        text: str,
        images: Optional[List[ProductImageEvidence]] = None
    ) -> Dict[str, Any]:
        """
        Extract statutory fields from raw multilingual packaging text.
        Returns a dictionary of canonical extracted fields, confidences, and provenance records.
        """
        raw_text = str(text or "")
        normalized_data = normalize_text_comprehensive(raw_text)
        norm_text = normalized_data["normalized_text"]

        # Run document language detection
        doc_lang_meta = detect_document_languages(raw_text)

        extracted: Dict[str, Any] = {
            "other_declarations": {},
            "declaration_confidences": {},
            "field_provenance": {},
            "multilingual_metadata": doc_lang_meta
        }
        confidences: Dict[str, float] = {}
        provenance: Dict[str, FieldProvenance] = {}

        # -------------------------------------------------------------
        # 1. Multilingual MRP Extraction
        # -------------------------------------------------------------
        mrp_val, mrp_src, mrp_lang, mrp_conf = self._extract_mrp(raw_text, norm_text)
        if mrp_val:
            extracted["mrp"] = mrp_val
            confidences["mrp"] = mrp_conf
            tok_s = detect_token_script_and_language(mrp_src)
            provenance["mrp"] = FieldProvenance(
                field_name="mrp",
                raw_value=mrp_src,
                normalized_value=mrp_val,
                source_text=mrp_src,
                confidence=mrp_conf,
                match_method="MULTILINGUAL_DICTIONARY",
                language=mrp_lang if mrp_lang != "neutral" else tok_s["language"],
                script=tok_s["script"]
            )

        # -------------------------------------------------------------
        # 2. Multilingual Net Quantity Extraction
        # -------------------------------------------------------------
        qty_val, qty_src, qty_lang, qty_conf = self._extract_net_quantity(raw_text, norm_text)
        if qty_val:
            extracted["net_quantity"] = qty_val
            confidences["net_quantity"] = qty_conf
            tok_q = detect_token_script_and_language(qty_src)
            provenance["net_quantity"] = FieldProvenance(
                field_name="net_quantity",
                raw_value=qty_src,
                normalized_value=qty_val,
                source_text=qty_src,
                confidence=qty_conf,
                match_method="MULTILINGUAL_DICTIONARY",
                language=qty_lang if qty_lang != "neutral" else tok_q["language"],
                script=tok_q["script"]
            )

        # -------------------------------------------------------------
        # 3. Multilingual Dates (Mfg, Pkg, Expiry, Best Before)
        # -------------------------------------------------------------
        dates = self._extract_dates(raw_text, norm_text)
        for date_key, (val, src, d_lang, d_conf) in dates.items():
            if val:
                extracted[date_key] = val
                if date_key == "manufacturing_date":
                    extracted["mfg_date"] = val
                elif date_key == "expiry_date":
                    extracted["exp_date"] = val
                confidences[date_key] = d_conf
                tok_d = detect_token_script_and_language(src)
                provenance[date_key] = FieldProvenance(
                    field_name=date_key,
                    raw_value=src,
                    normalized_value=val,
                    source_text=src,
                    confidence=d_conf,
                    match_method="MULTILINGUAL_DICTIONARY",
                    language=d_lang if d_lang != "neutral" else tok_d["language"],
                    script=tok_d["script"]
                )

        # -------------------------------------------------------------
        # 4. Multilingual Ingredients Header & Text
        # -------------------------------------------------------------
        ingr_val, ingr_src, ingr_lang, ingr_conf = self._extract_section(raw_text, norm_text, "ingredients")
        if ingr_val:
            extracted["ingredients"] = ingr_val
            confidences["ingredients"] = ingr_conf
            tok_i = detect_token_script_and_language(ingr_src)
            provenance["ingredients"] = FieldProvenance(
                field_name="ingredients",
                raw_value=ingr_src,
                normalized_value=ingr_val,
                source_text=ingr_src,
                confidence=ingr_conf,
                match_method="MULTILINGUAL_DICTIONARY",
                language=ingr_lang if ingr_lang != "neutral" else tok_i["language"],
                script=tok_i["script"]
            )

        # -------------------------------------------------------------
        # 5. Multilingual Consumer Care Details
        # -------------------------------------------------------------
        cc_info = self._extract_consumer_care(raw_text, norm_text)
        if cc_info.get("consumer_care"):
            extracted["consumer_care"] = cc_info["consumer_care"]
            confidences["consumer_care"] = cc_info.get("confidence", 90.0)
            if cc_info.get("phone"):
                extracted["consumer_care_phone"] = cc_info["phone"]
            if cc_info.get("email"):
                extracted["consumer_care_email"] = cc_info["email"]
            tok_c = detect_token_script_and_language(cc_info.get("source_text", ""))
            provenance["consumer_care"] = FieldProvenance(
                field_name="consumer_care",
                raw_value=cc_info.get("source_text", ""),
                normalized_value=cc_info["consumer_care"],
                source_text=cc_info.get("source_text", ""),
                confidence=cc_info.get("confidence", 90.0),
                match_method="MULTILINGUAL_DICTIONARY",
                language=tok_c["language"],
                script=tok_c["script"]
            )

        # -------------------------------------------------------------
        # 6. Multilingual Manufacturer & Marketed By
        # -------------------------------------------------------------
        mfg_val, mfg_src, mfg_lang, mfg_conf = self._extract_entity(raw_text, norm_text, "manufacturer")
        if mfg_val:
            extracted["manufacturer"] = mfg_val
            extracted["manufacturer_name"] = mfg_val
            extracted["manufacturer_address"] = mfg_val
            confidences["manufacturer"] = mfg_conf
            tok_m = detect_token_script_and_language(mfg_src)
            provenance["manufacturer"] = FieldProvenance(
                field_name="manufacturer",
                raw_value=mfg_src,
                normalized_value=mfg_val,
                source_text=mfg_src,
                confidence=mfg_conf,
                match_method="MULTILINGUAL_DICTIONARY",
                language=mfg_lang if mfg_lang != "neutral" else tok_m["language"],
                script=tok_m["script"]
            )

        mkt_val, mkt_src, mkt_lang, mkt_conf = self._extract_entity(raw_text, norm_text, "marketed_by")
        if mkt_val:
            extracted["marketed_by"] = mkt_val
            extracted["marketed_by_name"] = mkt_val
            confidences["marketed_by"] = mkt_conf
            tok_mk = detect_token_script_and_language(mkt_src)
            provenance["marketed_by"] = FieldProvenance(
                field_name="marketed_by",
                raw_value=mkt_src,
                normalized_value=mkt_val,
                source_text=mkt_src,
                confidence=mkt_conf,
                match_method="MULTILINGUAL_DICTIONARY",
                language=mkt_lang if mkt_lang != "neutral" else tok_mk["language"],
                script=tok_mk["script"]
            )

        # -------------------------------------------------------------
        # 7. FSSAI License Extraction
        # -------------------------------------------------------------
        fssai_val = repair_fssai_license(norm_text)
        if fssai_val:
            extracted["fssai_license"] = fssai_val
            confidences["fssai_license"] = 95.0
            provenance["fssai_license"] = FieldProvenance(
                field_name="fssai_license",
                raw_value=fssai_val,
                normalized_value=fssai_val,
                source_text=fssai_val,
                confidence=95.0,
                match_method="MULTILINGUAL_DICTIONARY",
                language=doc_lang_meta.get("primary_language", "en"),
                script="Latin"
            )

        # -------------------------------------------------------------
        # 8. Multilingual Nutritional Information & Allergens
        # -------------------------------------------------------------
        nutr_val, nutr_src, nutr_lang, nutr_conf = self._extract_section(raw_text, norm_text, "nutritional_info")
        if nutr_val:
            extracted["nutritional_info"] = nutr_val
            extracted["nutrition_panel_detected"] = True
            confidences["nutritional_info"] = nutr_conf

        allg_val, allg_src, allg_lang, allg_conf = self._extract_section(raw_text, norm_text, "allergens")
        if allg_val:
            extracted["allergen_info"] = allg_val
            confidences["allergen_info"] = allg_conf

        # -------------------------------------------------------------
        # 9. Spatial Provenance Binding (Word Tokens & Bounding Boxes)
        # -------------------------------------------------------------
        if images:
            self._bind_image_provenance(provenance, images, confidences)

        extracted["declaration_confidences"] = confidences
        extracted["field_provenance"] = provenance
        return extracted

    def extract_from_text(self, text: str) -> Dict[str, Any]:
        """Convenience method for text-only extraction with provenance."""
        res = self.extract_multilingual_fields(text)
        res["_provenance"] = res.get("field_provenance", {})
        return res

    # ── Helpers for statutory field extraction ────────────────────────────

    def _extract_mrp(self, raw_text: str, norm_text: str) -> Tuple[Optional[str], str, str, float]:
        """Extract MRP across all 10 languages with Indic numeral normalization."""
        # Check all keywords in dictionaries
        all_kws: List[Tuple[str, str]] = []
        for lang, d in self.dictionaries.items():
            for kw in d.get("keywords", {}).get("mrp", []):
                all_kws.append((kw, lang))

        # Sort keywords longest first
        all_kws.sort(key=lambda x: len(x[0]), reverse=True)

        lines = norm_text.split("\n")
        raw_lines = raw_text.split("\n")

        for idx, line in enumerate(lines):
            raw_line = raw_lines[idx] if idx < len(raw_lines) else line
            for kw, lang in all_kws:
                # Match keyword case-insensitively
                kw_pos = line.lower().find(kw.lower())
                if kw_pos != -1:
                    # Found statutory anchor, extract price from this line or adjacent text
                    window = line[kw_pos:]
                    repaired = repair_mrp(window)
                    if repaired and any(c.isdigit() for c in repaired):
                        return repaired, raw_line, lang, 94.0

        # Pattern fallback across text for localized price formats (e.g. ₹ 120, रु 500, Rs. 99)
        mrp_fallback = re.search(r'(?:₹|Rs\.?|INR|रु\.?|रू\.?|টাকা|ਰੁ\.?|ரூ\.?|రూ\.?|ರೂ\.?|രൂപ)\s*(\d+(?:\.\d{1,2})?)', norm_text, re.IGNORECASE)
        if mrp_fallback:
            val = f"₹{mrp_fallback.group(1)}"
            return val, mrp_fallback.group(0), "neutral", 88.0

        return None, "", "en", 0.0

    def _extract_net_quantity(self, raw_text: str, norm_text: str) -> Tuple[Optional[str], str, str, float]:
        """Extract Net Quantity / Weight across all 10 languages with unit standardization."""
        serving_context_re = re.compile(
            r'(?:per\s*serve|serving\s*size|per\s*100\s*g|portion|%?\s*rda|nutrition|energy|kcal|carb|fat|protein)',
            re.IGNORECASE
        )

        all_kws: List[Tuple[str, str]] = []
        for lang, d in self.dictionaries.items():
            for kw in d.get("keywords", {}).get("net_quantity", []):
                all_kws.append((kw, lang))
        all_kws.sort(key=lambda x: len(x[0]), reverse=True)

        lines = norm_text.split("\n")
        raw_lines = raw_text.split("\n")

        for idx, line in enumerate(lines):
            if serving_context_re.search(line):
                continue
            raw_line = raw_lines[idx] if idx < len(raw_lines) else line

            for kw, lang in all_kws:
                kw_pos = line.lower().find(kw.lower())
                if kw_pos != -1:
                    window = line[kw_pos:min(len(line), kw_pos + 80)]
                    qty_m = re.search(
                        r'(\d+(?:\.\d+)?)\s*(g|gm|gms|grams|kg|kgs|ml|mls|l|ltr|litre|liter|piece|pcs|u|n|count)\b',
                        window,
                        re.IGNORECASE
                    )
                    if qty_m:
                        repaired = repair_net_quantity(f"{qty_m.group(1)} {qty_m.group(2)}")
                        if repaired:
                            return repaired, raw_line, lang, 94.0

        # Fallback: standalone weight / volume in non-serving lines
        for idx, line in enumerate(lines):
            if serving_context_re.search(line) or re.search(r'\b(?:19\d\d|20\d\d|kcal|cal)\b', line, re.IGNORECASE):
                continue
            raw_line = raw_lines[idx] if idx < len(raw_lines) else line
            sq = re.search(r'\b(\d{1,4}(?:\.\d{1,2})?)\s*(g|gm|gms|grams|kg|kgs|ml|mls|l|ltr)\b', line, re.IGNORECASE)
            if sq:
                repaired = repair_net_quantity(f"{sq.group(1)} {sq.group(2)}")
                if repaired:
                    return repaired, raw_line, "neutral", 88.0

        return None, "", "en", 0.0

    def _extract_dates(self, raw_text: str, norm_text: str) -> Dict[str, Tuple[Optional[str], str, str, float]]:
        """Extract localized manufacturing, packaging, expiry, and best before dates."""
        results: Dict[str, Tuple[Optional[str], str, str, float]] = {
            "manufacturing_date": (None, "", "en", 0.0),
            "packaging_date": (None, "", "en", 0.0),
            "expiry_date": (None, "", "en", 0.0),
            "best_before": (None, "", "en", 0.0),
        }

        date_field_map = {
            "manufacturing_date": "manufacturing_date",
            "packaging_date": "packaging_date",
            "expiry_date": "expiry_date",
            "best_before": "best_before"
        }

        lines = norm_text.split("\n")
        raw_lines = raw_text.split("\n")

        for f_key in date_field_map:
            all_kws: List[Tuple[str, str]] = []
            for lang, d in self.dictionaries.items():
                for kw in d.get("keywords", {}).get(f_key, []):
                    all_kws.append((kw, lang))
            all_kws.sort(key=lambda x: len(x[0]), reverse=True)

            found = False
            for idx, line in enumerate(lines):
                if found:
                    break
                raw_line = raw_lines[idx] if idx < len(raw_lines) else line
                for kw, lang in all_kws:
                    kw_pos = line.lower().find(kw.lower())
                    if kw_pos != -1:
                        window = line[kw_pos:min(len(line), kw_pos + 60)]
                        norm_d = normalize_multilingual_date(window)
                        if norm_d and any(c.isdigit() for c in norm_d):
                            results[f_key] = (norm_d, raw_line, lang, 92.0)
                            found = True
                            break

        return results

    def _extract_section(self, raw_text: str, norm_text: str, section_key: str) -> Tuple[Optional[str], str, str, float]:
        """Extract text section starting with a statutory localized heading."""
        all_kws: List[Tuple[str, str]] = []
        for lang, d in self.dictionaries.items():
            for kw in d.get("keywords", {}).get(section_key, []):
                all_kws.append((kw, lang))
        all_kws.sort(key=lambda x: len(x[0]), reverse=True)

        lines = norm_text.split("\n")
        raw_lines = raw_text.split("\n")

        for idx, line in enumerate(lines):
            raw_line = raw_lines[idx] if idx < len(raw_lines) else line
            for kw, lang in all_kws:
                kw_pos = line.lower().find(kw.lower())
                if kw_pos != -1:
                    # Capture heading line and subsequent lines
                    captured_lines = [raw_line[kw_pos:]]
                    for next_idx in range(idx + 1, min(len(lines), idx + 4)):
                        nxt = raw_lines[next_idx].strip()
                        if nxt and not any(stop_kw in nxt.lower() for stop_kw in ["mrp", "mfg", "fssai", "batch", "net wt"]):
                            captured_lines.append(nxt)
                        else:
                            break
                    res_text = " ".join(captured_lines).strip()
                    if len(res_text) >= 5:
                        return res_text, raw_line, lang, 92.0

        return None, "", "en", 0.0

    def _extract_consumer_care(self, raw_text: str, norm_text: str) -> Dict[str, Any]:
        """Extract consumer helpline, email, and care details across languages."""
        res: Dict[str, Any] = {}
        all_kws: List[Tuple[str, str]] = []
        for lang, d in self.dictionaries.items():
            for kw in d.get("keywords", {}).get("consumer_care", []):
                all_kws.append((kw, lang))
        all_kws.sort(key=lambda x: len(x[0]), reverse=True)

        # 1. Search for phone
        phone_match = re.search(r'\b(?:1800[-\s]?\d{3}[-\s]?\d{3,4}|[6-9]\d{9}|\+91[-\s]?[6-9]\d{9})\b', norm_text)
        if phone_match:
            res["phone"] = phone_match.group(0).strip()

        # 2. Search for email
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', raw_text)
        if email_match:
            res["email"] = email_match.group(0).strip()

        # 3. Search for heading
        lines = norm_text.split("\n")
        raw_lines = raw_text.split("\n")
        for idx, line in enumerate(lines):
            raw_line = raw_lines[idx] if idx < len(raw_lines) else line
            for kw, lang in all_kws:
                if kw.lower() in line.lower():
                    res["consumer_care"] = raw_line
                    res["source_text"] = raw_line
                    res["confidence"] = 92.0
                    return res

        if res.get("phone") or res.get("email"):
            parts = []
            if res.get("phone"):
                parts.append(f"Phone: {res['phone']}")
            if res.get("email"):
                parts.append(f"Email: {res['email']}")
            res["consumer_care"] = ", ".join(parts)
            res["source_text"] = res["consumer_care"]
            res["confidence"] = 90.0

        return res

    def _extract_entity(self, raw_text: str, norm_text: str, entity_type: str) -> Tuple[Optional[str], str, str, float]:
        """Extract manufacturer or marketed by name across languages."""
        all_kws: List[Tuple[str, str]] = []
        for lang, d in self.dictionaries.items():
            for kw in d.get("keywords", {}).get(entity_type, []):
                all_kws.append((kw, lang))
        all_kws.sort(key=lambda x: len(x[0]), reverse=True)

        lines = norm_text.split("\n")
        raw_lines = raw_text.split("\n")

        for idx, line in enumerate(lines):
            raw_line = raw_lines[idx] if idx < len(raw_lines) else line
            for kw, lang in all_kws:
                kw_pos = line.lower().find(kw.lower())
                if kw_pos != -1:
                    # Look for entity name after anchor or on next line
                    name_part = raw_line[kw_pos + len(kw):].strip(" :-,.")
                    if len(name_part) >= 4:
                        return name_part, raw_line, lang, 90.0
                    elif idx + 1 < len(raw_lines) and len(raw_lines[idx + 1].strip()) >= 4:
                        return raw_lines[idx + 1].strip(), raw_line, lang, 88.0

        return None, "", "en", 0.0

    def _bind_image_provenance(
        self,
        provenance: Dict[str, FieldProvenance],
        images: List[ProductImageEvidence],
        confidences: Dict[str, float]
    ) -> None:
        """Associate extracted field values with image bounding boxes, scripts, and tokens."""
        for img_idx, img in enumerate(images):
            for w_idx, w in enumerate(img.words):
                w_norm = normalize_indic_digits(w.text).lower()
                tok_info = detect_token_script_and_language(w.text)

                # Bind MRP
                if "mrp" in provenance and not provenance["mrp"].source_bbox:
                    mrp_val = provenance["mrp"].normalized_value or ""
                    num_val = re.sub(r'[^\d]', '', mrp_val)
                    if num_val and num_val in w_norm:
                        provenance["mrp"].image_index = img_idx
                        provenance["mrp"].image_label = img.label
                        provenance["mrp"].source_bbox = list(w.bbox)
                        provenance["mrp"].source_token_ids = [f"tok_{img_idx}_{w_idx}"]

                # Bind Net Quantity
                if "net_quantity" in provenance and not provenance["net_quantity"].source_bbox:
                    qty_val = provenance["net_quantity"].normalized_value or ""
                    num_qty = re.sub(r'[^\d]', '', qty_val)
                    if num_qty and num_qty in w_norm:
                        provenance["net_quantity"].image_index = img_idx
                        provenance["net_quantity"].image_label = img.label
                        provenance["net_quantity"].source_bbox = list(w.bbox)
                        provenance["net_quantity"].source_token_ids = [f"tok_{img_idx}_{w_idx}"]


multilingual_extractor = MultilingualExtractor()
