"""
MetrCheck AI — Multilingual Intelligence Package

Provides:
- Centralized 10-language registry
- Deterministic script and language detection
- Indic numeral, unit, and date normalization
- Multilingual statutory field dictionaries and extraction
- Localized compliance explanations and multilingual PDF reports
"""

from multilingual.registry import (
    SUPPORTED_LANGUAGES,
    SCRIPT_UNICODE_RANGES,
    SCRIPT_TO_LANGUAGES,
    get_language_info,
    get_supported_languages_list,
    normalize_language_code
)

__all__ = [
    "SUPPORTED_LANGUAGES",
    "SCRIPT_UNICODE_RANGES",
    "SCRIPT_TO_LANGUAGES",
    "get_language_info",
    "get_supported_languages_list",
    "normalize_language_code"
]
