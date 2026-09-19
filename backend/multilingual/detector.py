"""
MetrCheck AI — Deterministic Script & Language Detection Layer

Features:
- Deterministic Unicode code-point script classification
- Token-level and document-level script & language identification
- Statistical confidence estimation
- Mixed-language packaging detection
- Lexical Hindi vs Marathi Devanagari disambiguation
- Language-neutral token filtering (numbers, symbols, punctuation)
"""

import re
from typing import Dict, Any, List, Optional, Tuple, Set
from multilingual.registry import (
    SUPPORTED_LANGUAGES,
    SCRIPT_UNICODE_RANGES,
    SCRIPT_TO_LANGUAGES,
    normalize_language_code
)

# Lexical markers for Devanagari Hindi vs Marathi disambiguation
MARATHI_MARKERS: Set[str] = {
    'किंमत', 'किं.', 'वजन', 'घटक', 'उत्पादक', 'नोंदणी', 'पत्ता', 'तक्रार', 
    'वापर', 'महिने', 'आहे', 'आणि', 'पासून', 'ग्राहकांसाठी', 'तारीख', 
    'विक्री', 'मर्यादा', 'उत्पादन', 'पॅकिंग', 'सर्व', 'करांसह', 'अधिकतम',
    'कस्टमर', 'केअर', 'ईमेल', 'फोन', 'क्रमांक', 'निर्देश'
}

HINDI_MARKERS: Set[str] = {
    'मूल्य', 'कीमत', 'मात्रा', 'सामग्री', 'निर्माता', 'पंजीकरण', 'पता', 
    'शिकायत', 'उपयोग', 'महीने', 'है', 'और', 'से', 'उपभोक्ता', 'तारीख', 
    'बिक्री', 'अवधि', 'उत्पादन', 'पैकिंग', 'सभी', 'करों', 'सहित', 'अधिकतम',
    'खुदरा', 'वजन', 'सेवा', 'संपर्क', 'संख्या', 'निर्देश'
}

# Language-neutral patterns (pure digits, punctuation, currency symbols, standard weights)
NEUTRAL_PATTERN = re.compile(
    r'^[\d\s\.,:;\/\-\+\(\)\[\]\{\}\#\*\%\$\€\£\¥\₹\₹\^\_\=\|\<\>\'\"\`\@\!\?\~]+$',
    re.UNICODE
)


def detect_character_script(char: str) -> Optional[str]:
    """Identify the script of a single character using Unicode code point ranges."""
    if not char:
        return None
    code_point = ord(char)
    for script_name, ranges in SCRIPT_UNICODE_RANGES.items():
        for start, end in ranges:
            if start <= code_point <= end:
                return script_name
    return None


def detect_token_script_and_language(token_text: str) -> Dict[str, Any]:
    """
    Identify script, language, and statistical confidence for an individual token.
    Returns:
        {
            "text": str,
            "script": str,  # 'Latin', 'Devanagari', 'Tamil', ..., or 'Neutral'
            "language": str,  # 'en', 'hi', 'mr', 'ta', ..., or 'neutral'
            "confidence": float  # 0.0 - 1.0
        }
    """
    t = str(token_text or "").strip()
    if not t or NEUTRAL_PATTERN.match(t):
        return {
            "text": t,
            "script": "Neutral",
            "language": "neutral",
            "confidence": 1.0
        }

    script_counts: Dict[str, int] = {}
    total_script_chars = 0

    for ch in t:
        s = detect_character_script(ch)
        if s:
            script_counts[s] = script_counts.get(s, 0) + 1
            total_script_chars += 1

    if not script_counts or total_script_chars == 0:
        return {
            "text": t,
            "script": "Unknown",
            "language": "und",
            "confidence": 0.50
        }

    # Primary script by majority character count
    primary_script = max(script_counts, key=script_counts.get)
    char_confidence = round(script_counts[primary_script] / total_script_chars, 2)

    # Map script to language
    if primary_script == "Latin":
        return {
            "text": t,
            "script": "Latin",
            "language": "en",
            "confidence": max(0.60, char_confidence)
        }
    elif primary_script == "Devanagari":
        # Disambiguate Hindi vs Marathi
        t_clean = re.sub(r'[^\u0900-\u097F]', '', t)
        if t_clean in MARATHI_MARKERS and t_clean not in HINDI_MARKERS:
            return {"text": t, "script": "Devanagari", "language": "mr", "confidence": min(0.95, char_confidence * 1.0)}
        elif t_clean in HINDI_MARKERS and t_clean not in MARATHI_MARKERS:
            return {"text": t, "script": "Devanagari", "language": "hi", "confidence": min(0.95, char_confidence * 1.0)}
        else:
            # Ambiguous single Devanagari token -> default to 'hi' with moderate confidence or joint tag
            return {"text": t, "script": "Devanagari", "language": "hi", "confidence": min(0.85, char_confidence * 0.9)}
    elif primary_script == "Bengali":
        return {"text": t, "script": "Bengali", "language": "bn", "confidence": char_confidence}
    elif primary_script == "Gujarati":
        return {"text": t, "script": "Gujarati", "language": "gu", "confidence": char_confidence}
    elif primary_script == "Gurmukhi":
        return {"text": t, "script": "Gurmukhi", "language": "pa", "confidence": char_confidence}
    elif primary_script == "Tamil":
        return {"text": t, "script": "Tamil", "language": "ta", "confidence": char_confidence}
    elif primary_script == "Telugu":
        return {"text": t, "script": "Telugu", "language": "te", "confidence": char_confidence}
    elif primary_script == "Kannada":
        return {"text": t, "script": "Kannada", "language": "kn", "confidence": char_confidence}
    elif primary_script == "Malayalam":
        return {"text": t, "script": "Malayalam", "language": "ml", "confidence": char_confidence}

    return {
        "text": t,
        "script": primary_script,
        "language": "und",
        "confidence": char_confidence
    }


def detect_document_languages(text: str) -> Dict[str, Any]:
    """
    Perform deterministic, statistical script and language detection across a full text or list of tokens.
    
    Returns structured multilingual summary:
    {
        "primary_language": "en" | "hi" | ...,
        "primary_script": "Latin" | "Devanagari" | ...,
        "detected_languages": [
            {
                "code": "hi",
                "name": "Hindi",
                "script": "Devanagari",
                "confidence": 0.95,
                "token_count": 42
            },
            ...
        ],
        "detected_scripts": ["Devanagari", "Latin"],
        "mixed_language": True / False,
        "language_confidence": 0.94
    }
    """
    raw = str(text or "")
    if not raw.strip():
        return {
            "primary_language": "en",
            "primary_script": "Latin",
            "detected_languages": [
                {
                    "code": "en",
                    "name": "English",
                    "script": "Latin",
                    "confidence": 1.0,
                    "token_count": 0
                }
            ],
            "detected_scripts": ["Latin"],
            "mixed_language": False,
            "language_confidence": 1.0
        }

    # Split into words/tokens
    tokens = raw.split()
    script_token_counts: Dict[str, int] = {}
    lang_token_counts: Dict[str, int] = {}
    script_char_counts: Dict[str, int] = {}
    total_classified_tokens = 0
    total_classified_chars = 0

    devanagari_words: List[str] = []

    for tok in tokens:
        res = detect_token_script_and_language(tok)
        script = res["script"]
        lang = res["language"]

        if script != "Neutral" and script != "Unknown":
            script_token_counts[script] = script_token_counts.get(script, 0) + 1
            total_classified_tokens += 1
            
            if script == "Devanagari":
                devanagari_words.append(tok)
            else:
                lang_token_counts[lang] = lang_token_counts.get(lang, 0) + 1

        for ch in tok:
            s = detect_character_script(ch)
            if s:
                script_char_counts[s] = script_char_counts.get(s, 0) + 1
                total_classified_chars += 1

    # Devanagari text-level lexical disambiguation (Hindi vs Marathi)
    if "Devanagari" in script_token_counts:
        marathi_hits = sum(1 for w in devanagari_words if any(m in w for m in MARATHI_MARKERS))
        hindi_hits = sum(1 for w in devanagari_words if any(m in w for m in HINDI_MARKERS))
        dev_total = script_token_counts["Devanagari"]

        if marathi_hits > hindi_hits:
            lang_token_counts["mr"] = dev_total
        elif hindi_hits > marathi_hits:
            lang_token_counts["hi"] = dev_total
        else:
            # Equal or ambiguous -> default to 'hi' or split
            lang_token_counts["hi"] = dev_total

    if not script_token_counts:
        # Default to English / Latin if only neutral tokens (numbers/symbols) exist
        return {
            "primary_language": "en",
            "primary_script": "Latin",
            "detected_languages": [
                {
                    "code": "en",
                    "name": "English",
                    "script": "Latin",
                    "confidence": 0.90,
                    "token_count": len(tokens)
                }
            ],
            "detected_scripts": ["Latin"],
            "mixed_language": False,
            "language_confidence": 0.90
        }

    # Build detected languages list sorted by token count
    detected_langs_list: List[Dict[str, Any]] = []
    for l_code, count in sorted(lang_token_counts.items(), key=lambda x: x[1], reverse=True):
        info = SUPPORTED_LANGUAGES.get(l_code)
        if not info:
            continue
        # Statistical confidence based on proportion of total classified characters & tokens
        char_count_for_script = script_char_counts.get(info["script"], 0)
        char_ratio = (char_count_for_script / total_classified_chars) if total_classified_chars > 0 else 0.5
        token_ratio = (count / total_classified_tokens) if total_classified_tokens > 0 else 0.5
        stat_conf = round(min(0.99, max(0.65, (char_ratio * 0.6) + (token_ratio * 0.4))), 2)

        detected_langs_list.append({
            "code": l_code,
            "name": info["name"],
            "script": info["script"],
            "confidence": stat_conf,
            "token_count": count
        })

    if not detected_langs_list:
        detected_langs_list.append({
            "code": "en",
            "name": "English",
            "script": "Latin",
            "confidence": 0.85,
            "token_count": len(tokens)
        })

    primary_lang = detected_langs_list[0]["code"]
    primary_script = detected_langs_list[0]["script"]
    primary_conf = detected_langs_list[0]["confidence"]
    
    # Mixed-language detection threshold: secondary language has at least 3 tokens and >= 10% of total classified tokens
    mixed_language = False
    if len(detected_langs_list) > 1:
        sec = detected_langs_list[1]
        if sec["token_count"] >= 2 and (sec["token_count"] / total_classified_tokens) >= 0.08:
            mixed_language = True

    return {
        "primary_language": primary_lang,
        "primary_script": primary_script,
        "detected_languages": detected_langs_list,
        "detected_scripts": list(script_token_counts.keys()),
        "mixed_language": mixed_language,
        "language_confidence": primary_conf
    }


# Convenience helper aliases
detect_char_script = detect_character_script


def detect_token_script(token: str) -> str:
    """Return the detected script for a single token."""
    return detect_token_script_and_language(token)["script"]


def detect_token_language(token: str) -> str:
    """Return the detected language code for a single token."""
    return detect_token_script_and_language(token)["language"]


def detect_language_and_script(text: str) -> Tuple[str, float, str]:
    """Return tuple of (primary_language_code, confidence, primary_script)."""
    res = detect_document_languages(text)
    return (res["primary_language"], res["language_confidence"], res["primary_script"])


class MultilingualDetector:
    """Class wrapper for multilingual detection operations."""
    @staticmethod
    def detect_char_script(char: str) -> Optional[str]:
        return detect_character_script(char)

    @staticmethod
    def detect_token(token: str) -> Dict[str, Any]:
        return detect_token_script_and_language(token)

    @staticmethod
    def detect_document(text: str) -> Dict[str, Any]:
        return detect_document_languages(text)

