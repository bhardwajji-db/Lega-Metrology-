"""
MetrCheck AI — Centralized 10-Language & Script Registry

Defines the canonical metadata for all 10 supported languages:
1. English (en) - Latin
2. Hindi (hi) - Devanagari
3. Bengali (bn) - Bengali
4. Marathi (mr) - Devanagari
5. Gujarati (gu) - Gujarati
6. Punjabi (pa) - Gurmukhi
7. Tamil (ta) - Tamil
8. Telugu (te) - Telugu
9. Kannada (kn) - Kannada
10. Malayalam (ml) - Malayalam
"""

from typing import Dict, Any, List, Optional, Tuple

SUPPORTED_LANGUAGES: Dict[str, Dict[str, Any]] = {
    "en": {
        "code": "en",
        "name": "English",
        "native_name": "English",
        "script": "Latin",
        "flag": "🇬🇧",
        "paddle_lang": "en",
        "ocr_version": "PP-OCRv4",
        "is_default": True
    },
    "hi": {
        "code": "hi",
        "name": "Hindi",
        "native_name": "हिन्दी",
        "script": "Devanagari",
        "flag": "🇮🇳",
        "paddle_lang": "hi",
        "ocr_version": "PP-OCRv5",
        "is_default": False
    },
    "bn": {
        "code": "bn",
        "name": "Bengali",
        "native_name": "বাংলা",
        "script": "Bengali",
        "flag": "🇮🇳",
        "paddle_lang": "bn",
        "ocr_version": "PP-OCRv3",
        "is_default": False
    },
    "mr": {
        "code": "mr",
        "name": "Marathi",
        "native_name": "मराठी",
        "script": "Devanagari",
        "flag": "🇮🇳",
        "paddle_lang": "mr",
        "ocr_version": "PP-OCRv5",
        "is_default": False
    },
    "gu": {
        "code": "gu",
        "name": "Gujarati",
        "native_name": "ગુજરાતી",
        "script": "Gujarati",
        "flag": "🇮🇳",
        "paddle_lang": "gu",
        "ocr_version": "PP-OCRv3",
        "is_default": False
    },
    "pa": {
        "code": "pa",
        "name": "Punjabi",
        "native_name": "ਪੰਜਾਬੀ",
        "script": "Gurmukhi",
        "flag": "🇮🇳",
        "paddle_lang": "pa",
        "ocr_version": "PP-OCRv3",
        "is_default": False
    },
    "ta": {
        "code": "ta",
        "name": "Tamil",
        "native_name": "தமிழ்",
        "script": "Tamil",
        "flag": "🇮🇳",
        "paddle_lang": "ta",
        "ocr_version": "PP-OCRv5",
        "is_default": False
    },
    "te": {
        "code": "te",
        "name": "Telugu",
        "native_name": "తెలుగు",
        "script": "Telugu",
        "flag": "🇮🇳",
        "paddle_lang": "te",
        "ocr_version": "PP-OCRv5",
        "is_default": False
    },
    "kn": {
        "code": "kn",
        "name": "Kannada",
        "native_name": "ಕನ್ನಡ",
        "script": "Kannada",
        "flag": "🇮🇳",
        "paddle_lang": "ka",  # Note: PaddleOCR uses 'ka' for Kannada
        "ocr_version": "PP-OCRv3",
        "is_default": False
    },
    "ml": {
        "code": "ml",
        "name": "Malayalam",
        "native_name": "മലയാളം",
        "script": "Malayalam",
        "flag": "🇮🇳",
        "paddle_lang": "ml",
        "ocr_version": "PP-OCRv3",
        "is_default": False
    }
}

# Unicode Code Point Ranges for deterministic script classification
SCRIPT_UNICODE_RANGES: Dict[str, List[Tuple[int, int]]] = {
    "Latin": [
        (0x0041, 0x005A),  # A-Z
        (0x0061, 0x007A),  # a-z
        (0x00C0, 0x00FF),  # Latin-1 Supplement
        (0x0100, 0x017F),  # Latin Extended-A
    ],
    "Devanagari": [
        (0x0900, 0x097F),  # Devanagari main block
        (0xA8E0, 0xA8FF),  # Devanagari Extended
    ],
    "Bengali": [
        (0x0980, 0x09FF),  # Bengali
    ],
    "Gurmukhi": [
        (0x0A00, 0x0A7F),  # Gurmukhi / Punjabi
    ],
    "Gujarati": [
        (0x0A80, 0x0AFF),  # Gujarati
    ],
    "Tamil": [
        (0x0B80, 0x0BFF),  # Tamil
    ],
    "Telugu": [
        (0x0C00, 0x0C7F),  # Telugu
    ],
    "Kannada": [
        (0x0C80, 0x0CFF),  # Kannada
    ],
    "Malayalam": [
        (0x0D00, 0x0D7F),  # Malayalam
    ]
}

# Script to associated language codes
SCRIPT_TO_LANGUAGES: Dict[str, List[str]] = {
    "Latin": ["en"],
    "Devanagari": ["hi", "mr"],
    "Bengali": ["bn"],
    "Gujarati": ["gu"],
    "Gurmukhi": ["pa"],
    "Tamil": ["ta"],
    "Telugu": ["te"],
    "Kannada": ["kn"],
    "Malayalam": ["ml"]
}

# Indic numerals to ASCII numeral mapping per script
SCRIPT_NUMERALS: Dict[str, Dict[str, str]] = {
    "Devanagari": {
        '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
        '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'
    },
    "Bengali": {
        '০': '0', '১': '1', '২': '2', '৩': '3', '৪': '4',
        '৫': '5', '৬': '6', '৭': '7', '৮': '8', '৯': '9'
    },
    "Gurmukhi": {
        '੦': '0', '੧': '1', '੨': '2', '੩': '3', '੪': '4',
        '੫': '5', '੬': '6', '੭': '7', '੮': '8', '੯': '9'
    },
    "Gujarati": {
        '૦': '0', '૧': '1', '૨': '2', '૩': '3', '૪': '4',
        '૫': '5', '૬': '6', '૭': '7', '૮': '8', '૯': '9'
    },
    "Tamil": {
        '௦': '0', '௧': '1', '௨': '2', '௩': '3', '௪': '4',
        '௫': '5', '௬': '6', '௭': '7', '௮': '8', '௯': '9'
    },
    "Telugu": {
        '౦': '0', '౧': '1', '౨': '2', '౩': '3', '౪': '4',
        '౫': '5', '౬': '6', '౭': '7', '౮': '8', '౯': '9'
    },
    "Kannada": {
        '೦': '0', '೧': '1', '೨': '2', '೩': '3', '೪': '4',
        '೫': '5', '೬': '6', '೭': '7', '೮': '8', '೯': '9'
    },
    "Malayalam": {
        '൦': '0', '൧': '1', '൨': '2', '൩': '3', '൪': '4',
        '൫': '5', '൬': '6', '൭': '7', '൮': '8', '൯': '9'
    }
}


def get_language_info(lang_code: str) -> Optional[Dict[str, Any]]:
    """Retrieve metadata for a language code (e.g. 'hi', 'en')."""
    return SUPPORTED_LANGUAGES.get((lang_code or "").lower().strip())


def get_supported_languages_list() -> List[Dict[str, Any]]:
    """Return list of all supported languages."""
    return list(SUPPORTED_LANGUAGES.values())


def normalize_language_code(code: Optional[str]) -> str:
    """Normalize language code to supported canonical 2-letter ISO code or 'en'."""
    if not code:
        return "en"
    c = code.lower().strip()
    alias_map = {
        "eng": "en", "english": "en",
        "hin": "hi", "hindi": "hi",
        "ben": "bn", "bengali": "bn", "bangla": "bn",
        "mar": "mr", "marathi": "mr",
        "guj": "gu", "gujarati": "gu",
        "pan": "pa", "punjabi": "pa", "gurmukhi": "pa",
        "tam": "ta", "tamil": "ta",
        "tel": "te", "telugu": "te",
        "kan": "kn", "kannada": "kn",
        "mal": "ml", "malayalam": "ml"
    }
    canonical = alias_map.get(c, c)
    return canonical if canonical in SUPPORTED_LANGUAGES else "en"


def is_supported_language(code: Optional[str]) -> bool:
    """Check if a language code is supported."""
    if not code:
        return False
    return (code.lower().strip() in SUPPORTED_LANGUAGES)


def get_language_name(code: Optional[str]) -> str:
    """Return human readable English name for language code."""
    info = get_language_info(code or "en")
    return info["name"] if info else "English"


def get_native_name(code: Optional[str]) -> str:
    """Return native script name for language code."""
    info = get_language_info(code or "en")
    return info["native_name"] if info else "English"


def get_paddle_lang_code(code: Optional[str]) -> str:
    """Return PaddleOCR language argument (e.g. 'devanagari', 'ka', 'ta', 'te', 'bn', 'gu', 'pa', 'ml', 'en')."""
    info = get_language_info(code or "en")
    if not info:
        return "en"
    lang = info["code"]
    if lang in ("hi", "mr"):
        return "devanagari"
    if lang == "kn":
        return "ka"
    return info.get("paddle_lang", "en")


def get_numeral_map(script: str) -> Dict[str, str]:
    """Return Indic numeral translation map for a script."""
    return SCRIPT_NUMERALS.get(script, {})

