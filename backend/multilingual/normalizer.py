"""
MetrCheck AI — Multilingual Text, Indic Numeral, Currency, Unit & Date Normalizer

Features:
- Unicode NFKC normalization
- Transliteration of Indic script numerals (Devanagari, Bengali, Gujarati, Gurmukhi, Tamil, Telugu, Kannada, Malayalam) to ASCII Arabic digits
- Currency symbol standardization (₹, Rs, INR, Indic currency words)
- Unit normalization (grams, kilograms, milliliters, liters, counts)
- Multilingual date month parsing and normalization
- Safe preservation of both original_text and normalized_text
"""

import re
import unicodedata
from typing import Dict, Any, Optional, Tuple
from multilingual.registry import SCRIPT_NUMERALS

# Complete transliteration map for all 8 Indic script numerals to ASCII digits
ALL_INDIC_DIGIT_MAP = {}
for script, mapping in SCRIPT_NUMERALS.items():
    ALL_INDIC_DIGIT_MAP.update(mapping)

INDIC_DIGIT_TRANSLATOR = str.maketrans(ALL_INDIC_DIGIT_MAP)

# Multilingual Currency Words / Symbols to ₹
CURRENCY_PATTERNS = [
    (re.compile(r'(?:INR|Rs\.?|Rupees?|Rupaye|रु\.?|रू\.?|টাকা|ਰੁ\.?|ரூ\.?|ரூபாய்|రూ\.?|రూపాయలు|ರೂ\.?|ರೂಪಾಯಿ|രൂപ)\s*', re.IGNORECASE), '₹'),
    (re.compile(r'₹+', re.UNICODE), '₹'),
]


def normalize_indic_digits(text: str) -> str:
    """Convert all Indic script digits (Devanagari, Bengali, Gujarati, etc.) to ASCII Arabic digits 0-9."""
    if not text:
        return ""
    return str(text).translate(INDIC_DIGIT_TRANSLATOR)


def normalize_currency(text: str) -> str:
    """Normalize currency expressions and words into standardized ₹ prefix."""
    if not text:
        return ""
    t = normalize_indic_digits(text)
    t = re.sub(r'(?:INR|Rupees?|Rupaye|ரூபாய்|రూపాయలు|ರೂಪಾಯಿ|രൂപ|Rs\.?|रु\.?|रू\.?|টাকা|ਰੁ\.?|ரூ\.?|రూ\.?|ರೂ\.?)\s*', '₹', t, flags=re.IGNORECASE)
    t = re.sub(r'₹+', '₹', t)
    return t


def normalize_units(text: str) -> str:
    """Normalize regional unit words (grams, kg, ml, liters, pieces) to canonical abbreviations."""
    if not text:
        return ""
    t = normalize_indic_digits(text)
    # Kilograms first
    t = re.sub(r'(\d+(?:\.\d+)?)\s*(?:किलोग्राम|kilograms?|kilogram|kilo|किग्रा|कि\.?\s*ग्रा\.?|ਕਿਲੋ|கிலோகிராம்|கிலோ|కిలోగ్రాములు|కిలో|ಕಿಲೋಗ್ರಾಂ|কেজি|કિલોગ્રામ|કિગ્રા|કિ\.?\s*ગ્રા\.?|કિલો|kg|kgs)(?!\w)', r'\1 kg', t, flags=re.IGNORECASE)
    # Milligrams
    t = re.sub(r'(\d+(?:\.\d+)?)\s*(?:milligrams?|milligram|mg|mgs|मि\.?\s*ग्रा\.?|மி\.?\s*கி|ಮಿ\.?\s*ಗ್ರಾಂ)(?!\w)', r'\1 mg', t, flags=re.IGNORECASE)
    # Grams
    t = re.sub(r'(\d+(?:\.\d+)?)\s*(?:grams?|gram|gm|gms|ग्राम|ग्रॅम|ग्रॅ|ഗ്രാം|கிராம்|ಗ್ರಾಂ|గ్రాములు|గ్రా|গ্রাম|ਗ੍ਰਾਮ|ગ્રા|g)(?!\w)', r'\1 g', t, flags=re.IGNORECASE)
    # Milliliters
    t = re.sub(r'(\d+(?:\.\d+)?)\s*(?:millilitres?|milliliters?|millilitre|milliliter|milli|मिलीलीटर|मिली|मि\.?\s*ली\.?|மி\.?\s*லி|மில்லி|మిల్లీ|మి\.?\s*లీ|ಮಿಲಿ|মিলি|ਮਿਲੀ|મિલી|ml|mls)(?!\w)', r'\1 ml', t, flags=re.IGNORECASE)
    # Liters
    t = re.sub(r'(\d+(?:\.\d+)?)\s*(?:litres?|liters?|litre|liter|लीटर|ली\.?|லிட்டர்|லீಟರ್|లీటరు|లీ|লিটার|ਲੀਟਰ|લિટર|ltrs|ltr|l)(?!\w)', r'\1 l', t, flags=re.IGNORECASE)
    # Counts
    t = re.sub(r'(\d+(?:\.\d+)?)\s*(?:pieces?|units?|संख्या|इकाई|নগ|எண்ணிக்கை|సంఖ్య|ಘಟಕ|ನੰਬਰ|સંખ્યા|pcs|pc|u|n)(?!\w)', r'\1 u', t, flags=re.IGNORECASE)
    return t


# Multilingual Month Names to 2-Digit String (01-12)
MONTH_MAPPINGS = {
    # English
    'jan': '01', 'january': '01', 'feb': '02', 'february': '02', 'mar': '03', 'march': '03',
    'apr': '04', 'april': '04', 'may': '05', 'jun': '06', 'june': '06', 'jul': '07', 'july': '07',
    'aug': '08', 'august': '08', 'sep': '09', 'sept': '09', 'september': '09', 'oct': '10', 'october': '10',
    'nov': '11', 'november': '11', 'dec': '12', 'december': '12',
    # Hindi / Marathi (Devanagari)
    'जनवरी': '01', 'जानेवारी': '01', 'फरवरी': '02', 'फेब्रुवारी': '02', 'मार्च': '03',
    'अप्रैल': '04', 'एप्रिल': '04', 'मई': '05', 'मे': '05', 'जून': '06', 'जुलाई': '07', 'जुलै': '07',
    'अगस्त': '08', 'ऑगस्ट': '08', 'सितंबर': '09', 'सप्टेंबर': '09', 'अक्टूबर': '10', 'ऑक्टोबर': '10',
    'नवंबर': '11', 'नोव्हेंबर': '11', 'दिसंबर': '12', 'डिसेंबर': '12',
    # Bengali
    'জানুয়ারি': '01', 'ফেব্রুয়ারি': '02', 'মার্চ': '03', 'এপ্রিল': '04', 'মে': '05', 'জুন': '06',
    'জুলাই': '07', 'আগস্ট': '08', 'সেপ্টেম্বর': '09', 'অক্টোবর': '10', 'নভেম্বর': '11', 'ডিসেম্বর': '12',
    # Gujarati
    'જાન્યુઆરી': '01', 'ફેબ્રુઆરી': '02', 'માર્ચ': '03', 'એપ્રિલ': '04', 'મે': '05', 'જૂન': '06',
    'જુલાઈ': '07', 'ઓગસ્ટ': '08', 'સપ્ટેમ્બર': '09', 'ઓક્ટોબર': '10', 'નવેમ્બર': '11', 'ડિસેમ્બર': '12',
    # Punjabi
    'ਜਨਵਰੀ': '01', 'ਫ਼ਰਵਰੀ': '02', 'ਮਾਰਚ': '03', 'ਅਪ੍ਰੈਲ': '04', 'ਮਈ': '05', 'ਜੂਨ': '06',
    'ਜੁਲਾਈ': '07', 'ਅਗਸਤ': '08', 'ਸਤੰਬਰ': '09', 'ਅਕਤੂਬਰ': '10', 'ਨਵੰਬਰ': '11', 'ਦਸੰਬਰ': '12',
    # Tamil
    'ஜனவரி': '01', 'பிப்ரவரி': '02', 'மார்ச்': '03', 'ஏப்ரல்': '04', 'மே': '05', 'ஜூன்': '06',
    'ஜூலை': '07', 'ஆகஸ்ட்': '08', 'செப்டம்பர்': '09', 'அக்டோபர்': '10', 'நவம்பர்': '11', 'டிசம்பர்': '12',
    # Telugu
    'జనవరి': '01', 'ఫిబ్రవరి': '02', 'మార్చి': '03', 'ఏప్రిల్': '04', 'మే': '05', 'జూన్': '06',
    'జూలై': '07', 'ఆగస్టు': '08', 'సెప్టెంబరు': '09', 'అక్టోబరు': '10', 'నవంబరు': '11', 'డిసెంబరు': '12',
    # Kannada
    'ಜನವರಿ': '01', 'ಫೆಬ್ರವರಿ': '02', 'ಮಾರ್ಚ್': '03', 'ಏಪ್ರಿಲ್': '04', 'ಮೇ': '05', 'ಜೂನ್': '06',
    'ಜುಲೈ': '07', 'ಆಗಸ್ಟ್': '08', 'ಸೆಪ್ಟೆಂಬರ್': '09', 'ಅಕ್ಟೋಬರ್': '10', 'ನವೆಂಬರ್': '11', 'ಡಿಸೆಂಬರ್': '12',
    # Malayalam
    'ജനുവരി': '01', 'ഫെബ്രുവരി': '02', 'മാർച്ച്': '03', 'ഏപ്രിൽ': '04', 'മേയ്': '05', 'ജൂൺ': '06',
    'ജൂലൈ': '07', 'ഓഗസ്റ്റ്': '08', 'സെപ്റ്റംബർ': '09', 'ഒക്ടോബർ': '10', 'നവംബർ': '11', 'ഡിസംബർ': '12'
}


def normalize_multilingual_date(date_str: str) -> Optional[str]:
    """
    Convert localized date strings into standard MM/YYYY, DD/MM/YYYY, or MM/YY format.
    Supports Indic month names and Indic numerals.
    """
    if not date_str:
        return None

    # First normalize Indic numerals to ASCII digits
    d = normalize_indic_digits(date_str).strip()
    d_lower = d.lower()

    # Check for text month names in date (e.g. "15 जनवरी 2024" or "মার্চ 2025" or "JAN 2026")
    for month_word, month_num in MONTH_MAPPINGS.items():
        if month_word in d_lower:
            # Look for 4-digit year first (e.g. 2024, 2025, 2026, 1999)
            year_match = re.search(r'\b(20\d\d|19\d\d)\b', d)
            if not year_match:
                m_pos = d_lower.find(month_word)
                after_month = d[m_pos + len(month_word):]
                year_match = re.search(r'\b(\d{2})\b', after_month)
                if not year_match:
                    year_match = re.search(r'\b(\d{2})\b', d)
            if year_match:
                year = year_match.group(1)
                if len(year) == 2:
                    year = f"20{year}"
                
                # Check for day before month
                m_pos = d_lower.find(month_word)
                before_month = d[:m_pos]
                day_match = re.search(r'\b([0-2]?\d|3[01])\b', before_month)
                if day_match and int(day_match.group(1)) <= 31 and int(day_match.group(1)) > 0:
                    day = f"{int(day_match.group(1)):02d}"
                    return f"{day}/{month_num}/{year}"
                return f"{month_num}/{year}"

    # Handle standard numeric formats (e.g. 05/2024, 12-08-2025)
    num_match = re.search(r'\b(\d{1,2})[\/\.\-](\d{1,2})[\/\.\-](\d{2,4})\b', d)
    if num_match:
        p1, p2, p3 = num_match.group(1), num_match.group(2), num_match.group(3)
        if len(p3) == 2:
            p3 = f"20{p3}"
        return f"{int(p1):02d}/{int(p2):02d}/{p3}"

    month_year_match = re.search(r'\b(\d{1,2})[\/\.\-](\d{2,4})\b', d)
    if month_year_match:
        m, y = month_year_match.group(1), month_year_match.group(2)
        if 1 <= int(m) <= 12:
            if len(y) == 2:
                y = f"20{y}"
            return f"{int(m):02d}/{y}"

    return d


def normalize_text_comprehensive(text: str) -> Dict[str, str]:
    """
    Perform complete multilingual normalization on text.
    Returns:
        {
            "original_text": str,
            "normalized_text": str
        }
    """
    orig = str(text or "")
    # 1. Unicode NFKC normalization
    nfkc = unicodedata.normalize('NFKC', orig)
    
    # 2. Indic digits transliteration
    with_ascii_digits = normalize_indic_digits(nfkc)
    
    # 3. Currency symbol standardization
    with_curr = normalize_currency(with_ascii_digits)
    
    # 4. Unit standardization
    with_units = normalize_units(with_curr)
    
    # 5. Clean extra whitespace
    cleaned = re.sub(r'[ \t]+', ' ', with_units).strip()

    return {
        "original_text": orig,
        "normalized_text": cleaned
    }


# Convenience helper aliases
parse_multilingual_date = normalize_multilingual_date


def normalize_multilingual_text(text: str) -> str:
    """Return normalized text string directly."""
    return normalize_text_comprehensive(text)["normalized_text"]


class MultilingualNormalizer:
    """Class wrapper for multilingual text normalization operations."""
    @staticmethod
    def normalize_digits(text: str) -> str:
        return normalize_indic_digits(text)

    @staticmethod
    def normalize_currency_symbols(text: str) -> str:
        return normalize_currency(text)

    @staticmethod
    def normalize_metric_units(text: str) -> str:
        return normalize_units(text)

    @staticmethod
    def normalize_date(text: str) -> Optional[str]:
        return normalize_multilingual_date(text)

    @staticmethod
    def normalize_all(text: str) -> Dict[str, str]:
        return normalize_text_comprehensive(text)

