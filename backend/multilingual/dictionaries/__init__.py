"""
MetrCheck AI — Multilingual Dictionary Loader & Registry
"""

import os
import json
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

_DICTIONARIES_CACHE: Dict[str, Dict[str, Any]] = {}
_DICT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_all_dictionaries() -> Dict[str, Dict[str, Any]]:
    """Loads all 10 language JSON dictionaries into a cached structure."""
    global _DICTIONARIES_CACHE
    if _DICTIONARIES_CACHE:
        return _DICTIONARIES_CACHE

    for lang in ["en", "hi", "bn", "mr", "gu", "pa", "ta", "te", "kn", "ml"]:
        file_path = os.path.join(_DICT_DIR, f"{lang}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    _DICTIONARIES_CACHE[lang] = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load dictionary for {lang}: {e}")
                _DICTIONARIES_CACHE[lang] = {"language_code": lang, "keywords": {}}
        else:
            logger.warning(f"Dictionary file not found for {lang} at {file_path}")
            _DICTIONARIES_CACHE[lang] = {"language_code": lang, "keywords": {}}

    return _DICTIONARIES_CACHE


def get_keywords_for_field(field_name: str) -> List[Tuple[str, str]]:
    """
    Returns a list of (keyword, lang_code) tuples across all 10 languages for a statutory field.
    """
    dicts = load_all_dictionaries()
    results = []
    for lang, data in dicts.items():
        kws = data.get("keywords", {}).get(field_name, [])
        for kw in kws:
            results.append((kw, lang))
    return results


def get_dictionary(lang_code: str) -> Dict[str, Any]:
    """Retrieve dictionary for a specific language code."""
    dicts = load_all_dictionaries()
    return dicts.get((lang_code or "en").lower(), dicts.get("en", {}))
