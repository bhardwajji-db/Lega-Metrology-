import re
import cv2
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from vision.schemas import SemanticRegionResult
from vision.utils import normalize_bbox, box_union, pad_bbox
from vision.config import vision_config

class SemanticRegionDetector:
    """
    Detects functional semantic zones on packaging labels:
    - MRP region
    - Net Quantity region
    - Date & Batch stamp region
    - Manufacturer / Packer / Importer information region
    - Consumer care / Helpline region
    - Nutrition facts table region
    - Ingredients section region
    - Allergen warning region
    Combines spatial layout, table grid morphology, OCR tokens, and multilingual statutory keywords.
    """

    KEYWORD_MAP = {
        "mrp": [
            "mrp", "maximum retail price", "max retail price", "incl of all taxes",
            "incl all taxes", "rs.", "rs ", "₹", "अधिकतम खुदरा मूल्य", "कमाल किरकोळ किंमत",
            "সর্বোচ্চ খুচরা মূল্য", "મહત્તમ છૂટક કિંમત", "ਵੱਧ ਤੋਂ ਵੱਧ ਪ੍ਰਚੂਨ ਕੀਮਤ",
            "அதிகபட்ச சில்லறை விலை", "గరిష్ట రిటైల్ ధర", "ಗರಿಷ್ಠ ಚಿಲ್ಲರೆ ಬೆಲೆ", "പരമാവധി ചില്ലറ വിൽപ്പന വില"
        ],
        "net_quantity": [
            "net qty", "net quantity", "net wt", "net weight", "net content", "net vol",
            "शुद्ध मात्रा", "निव्वळ प्रमाण", "নিট পরিমাণ", "ચોખ્ખો જથ્થો", "ਸ਼ੁੱਧ ਮਾਤਰਾ",
            "நிகர அளவு", "నికర పరిమాణం", "ನಿವ್ವಳ ಪ್ರಮಾಣ", "ശുദ്ധമായ അളവ്", "unit sale price", "usp"
        ],
        "date_stamp": [
            "mfg date", "date of mfg", "pkd date", "date of pkd", "manufacture date",
            "packing date", "best before", "expiry date", "use by", "exp date", "batch no",
            "lot no", "निर्माण की तारीख", "उत्पादन दिनांक", "প্যাকিংয়ের তারিখ", "તારીખ",
            "ਮਿਤੀ", "தேதி", "తేదీ", "ದಿನಾಂಕ", "തീയതി"
        ],
        "manufacturer": [
            "manufactured by", "mfg by", "packed by", "pkd by", "marketed by", "mkt by",
            "imported by", "registered office", "regd off", "regd office", "corporate office",
            "निर्माता", "उत्पादक", "প্রস্তুতকারক", "ઉત્પાદક", "ਨਿਰਮਾਤਾ", "உற்பத்தியாளர்",
            "తయారీదారు", "ತಯಾರಕರು", "നിർമ്മാതാവ്"
        ],
        "consumer_care": [
            "consumer care", "customer care", "helpline", "toll free", "feedback",
            "complaints", "reach us at", "call us", "email us", "care@","उपभोक्ता देखभाल",
            "ग्राहक सेवा", "গ্রাহক পরিষেবা", "ગ્રાહક સેવા", "ਗਾਹਕ ਸੇਵਾ", "வாடிக்கையாளர் சேவை",
            "వినియోగదారుల సంరక్షణ", "ಗ್ರಾಹಕರ ಕಾಳಜಿ", "ഉപഭോക്തൃ സംരക്ഷണം"
        ],
        "ingredients": [
            "ingredients", "ingredient", "composition", "contains", "made from",
            "सामग्री", "घटक", "উপাদান", "ઘટકો", "ਸਮੱਗਰੀ", "பொருட்கள்", "పదార్థాలు",
            "ಪದಾರ್ಥಗಳು", "ചേരുവകൾ"
        ],
        "allergen": [
            "allergen", "allergy advice", "contains wheat", "contains milk", "contains nuts",
            "contains soy", "contains gluten", "may contain", "एलर्जी", "অ্যালার্জি",
            "એલર્જી", "ਐਲਰਜੀ", "ஒவ்வாமை", "అలెర్జీ", "ಅಲರ್ಜಿ", "അലർജി"
        ],
        "nutrition_table": [
            "nutrition", "nutritional", "nutritional information", "nutrition facts",
            "energy", "protein", "carbohydrate", "fat", "saturated fat", "trans fat",
            "sugar", "sodium", "per 100g", "per serve", "पोषण", "পুষ্টি", "પોષણ",
            "ਪੋਸ਼ਣ", "ஊட்டச்சத்து", "పోషకాహారం", "ಪೌಷ್ಟಿಕಾಂಶ", "പോഷകാഹാരം"
        ]
    }

    @classmethod
    def detect_all_regions(
        cls,
        img_bgr: np.ndarray,
        words: List[Dict[str, Any]]
    ) -> List[SemanticRegionResult]:
        if img_bgr is None or img_bgr.size == 0 or not words:
            return []

        h, w = img_bgr.shape[:2]
        results: List[SemanticRegionResult] = []

        # 1. Morphological Nutrition Table Detection
        table_region = cls._detect_table_morphology(img_bgr, words)
        if table_region:
            results.append(table_region)

        # 2. Text/Token Based Semantic Regions
        for r_type in ["mrp", "net_quantity", "date_stamp", "manufacturer", "consumer_care", "ingredients", "allergen"]:
            reg = cls._detect_token_region(r_type, words, w, h)
            if reg:
                results.append(reg)

        return results

    @classmethod
    def _detect_table_morphology(cls, img_bgr: np.ndarray, words: List[Dict[str, Any]]) -> Optional[SemanticRegionResult]:
        """Detect structured table grids via morphological horizontal and vertical line kernel analysis."""
        try:
            h, w = img_bgr.shape[:2]
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 4)

            h_k = cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, w // 25), 1))
            v_k = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(15, h // 30)))
            h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_k)
            v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_k)
            table_mask = cv2.bitwise_or(h_lines, v_lines)

            contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in contours:
                bx, by, bw, bh = cv2.boundingRect(c)
                # Table candidate size check (at least 20% width and 10% height)
                if bw > w * 0.20 and bh > h * 0.10:
                    bbox = [max(0, bx - 5), max(0, by - 5), min(w, bx + bw + 5), min(h, by + bh + 5)]
                    # Check if tokens inside mention nutrition terms
                    contained_words = [
                        wd for wd in words
                        if bbox[0] <= wd.get('bbox', [0,0,0,0])[0] and wd.get('bbox', [0,0,0,0])[2] <= bbox[2]
                        and bbox[1] <= wd.get('bbox', [0,0,0,0])[1] and wd.get('bbox', [0,0,0,0])[3] <= bbox[3]
                    ]
                    text_inside = " ".join(wd.get('text', '') for wd in contained_words).lower()
                    has_nutr_kw = any(kw in text_inside for kw in cls.KEYWORD_MAP["nutrition_table"])

                    conf = 0.92 if has_nutr_kw else 0.72
                    return SemanticRegionResult(
                        region_type="nutrition_table",
                        detected=True,
                        confidence=conf,
                        confidence_tier=vision_config.get_confidence_tier(conf),
                        bbox=bbox,
                        normalized_bbox=normalize_bbox(bbox, w, h),
                        detection_method="MORPHOLOGICAL_GRID_ANALYSIS",
                        matched_keywords=[kw for kw in cls.KEYWORD_MAP["nutrition_table"] if kw in text_inside],
                        associated_text=text_inside[:120],
                        is_table_structure=True,
                        evidence_id="ev_nutr_table_01"
                    )
        except Exception:
            pass
        return None

    @classmethod
    def _detect_token_region(
        cls,
        region_type: str,
        words: List[Dict[str, Any]],
        img_w: int,
        img_h: int
    ) -> Optional[SemanticRegionResult]:
        keywords = cls.KEYWORD_MAP.get(region_type, [])
        matching_word_boxes: List[List[int]] = []
        matched_kws: List[str] = []
        matched_texts: List[str] = []

        num_words = len(words)
        matched_indices = set()

        # Clean helper
        def clean_txt(t: str) -> str:
            return re.sub(r'[:;,.\-_()#]', '', str(t).lower()).strip()

        for idx in range(num_words):
            # Check 1-gram, 2-gram, 3-gram, 4-gram
            for ngram_len in [1, 2, 3, 4]:
                if idx + ngram_len <= num_words:
                    window_words = words[idx : idx + ngram_len]
                    window_clean = " ".join(clean_txt(w.get('text', '')) for w in window_words)
                    window_raw = " ".join(str(w.get('text', '')) for w in window_words).lower()

                    for kw in keywords:
                        kw_clean = clean_txt(kw)
                        if (kw_clean and kw_clean in window_clean) or (kw in window_raw):
                            for w_idx, w in enumerate(window_words):
                                matched_indices.add(idx + w_idx)
                                bbox = w.get('bbox', [0, 0, 0, 0])
                                if len(bbox) == 4 and bbox not in matching_word_boxes:
                                    matching_word_boxes.append(bbox)
                            if kw not in matched_kws:
                                matched_kws.append(kw)
                            
                            # Add consecutive words on roughly same line or adjacent lines (value tokens)
                            for offset in range(ngram_len, ngram_len + 4):
                                if idx + offset < num_words:
                                    next_w = words[idx + offset]
                                    n_box = next_w.get('bbox', [0, 0, 0, 0])
                                    if len(n_box) == 4:
                                        base_box = window_words[0].get('bbox', [0, 0, 0, 0])
                                        if abs(n_box[1] - base_box[1]) < 60:
                                            matching_word_boxes.append(n_box)
                                            matched_indices.add(idx + offset)
                            break

        if not matching_word_boxes:
            return None

        # Sort texts by appearance
        for i in sorted(matched_indices):
            matched_texts.append(str(words[i].get('text', '')))

        # Compute bounding union with mild padding
        union_box = box_union(matching_word_boxes, img_w, img_h)
        if not union_box:
            return None

        padded_box = pad_bbox(union_box, 10, 8, img_w, img_h)
        norm_box = normalize_bbox(padded_box, img_w, img_h)

        conf = min(0.95, 0.70 + (len(matched_kws) * 0.08))
        return SemanticRegionResult(
            region_type=region_type,
            detected=True,
            confidence=round(conf, 2),
            confidence_tier=vision_config.get_confidence_tier(conf),
            bbox=padded_box,
            normalized_bbox=norm_box,
            detection_method="MULTILINGUAL_TOKEN_PROXIMITY",
            matched_keywords=list(set(matched_kws)),
            associated_text=" ".join(matched_texts[:12]),
            is_table_structure=False,
            evidence_id=f"ev_{region_type}_01"
        )

semantic_region_detector = SemanticRegionDetector()
