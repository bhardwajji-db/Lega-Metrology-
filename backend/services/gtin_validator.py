"""
MetrCheck AI — GTIN Normalization & GS1 Modulo-10 Validation Service
Implements statutory GS1 General Specifications for:
- GTIN-8, GTIN-12, GTIN-13, and GTIN-14 normalization
- GS1 Modulo-10 check digit calculation and verification
- Issuing GS1 Member Organization prefix resolution (with manufacturing jurisdiction caveat)
"""

import re
from typing import Optional, Tuple, Dict, Any

# GS1 Country / Member Organization Prefixes Table
# Ref: GS1 General Specifications Section 1.4
GS1_COUNTRY_PREFIXES: list[Tuple[int, int, str, str]] = [
    (0, 19, "United States / Canada", "🇺🇸"),
    (30, 39, "United States (Drugs)", "🇺🇸"),
    (40, 49, "Restricted Distribution", "🌐"),
    (50, 59, "Coupons", "🎟️"),
    (60, 139, "United States / Canada", "🇺🇸"),
    (200, 299, "Restricted Distribution", "🌐"),
    (300, 379, "France", "🇫🇷"),
    (380, 380, "Bulgaria", "🇧🇬"),
    (383, 383, "Slovenia", "🇸🇮"),
    (385, 385, "Croatia", "🇭🇷"),
    (387, 387, "Bosnia and Herzegovina", "🇧🇦"),
    (400, 440, "Germany", "🇩🇪"),
    (450, 459, "Japan", "🇯🇵"),
    (460, 469, "Russia", "🇷🇺"),
    (470, 470, "Kyrgyzstan", "🇰🇬"),
    (471, 471, "Taiwan", "🇹🇼"),
    (474, 474, "Estonia", "🇪🇪"),
    (475, 475, "Latvia", "🇱🇻"),
    (476, 476, "Azerbaijan", "🇦🇿"),
    (477, 477, "Lithuania", "🇱🇹"),
    (478, 478, "Uzbekistan", "🇺🇿"),
    (479, 479, "Sri Lanka", "🇱🇰"),
    (480, 480, "Philippines", "🇵🇭"),
    (481, 481, "Belarus", "🇧🇾"),
    (482, 482, "Ukraine", "🇺🇦"),
    (484, 484, "Moldova", "🇲🇩"),
    (485, 485, "Armenia", "🇦🇲"),
    (486, 486, "Georgia", "🇬🇪"),
    (487, 487, "Kazakhstan", "🇰🇿"),
    (488, 488, "Tajikistan", "🇹🇯"),
    (489, 489, "Hong Kong", "🇭🇰"),
    (490, 499, "Japan", "🇯🇵"),
    (500, 509, "United Kingdom", "🇬🇧"),
    (520, 521, "Greece", "🇬🇷"),
    (528, 528, "Lebanon", "🇱🇧"),
    (529, 529, "Cyprus", "🇨🇾"),
    (530, 530, "Albania", "🇦🇱"),
    (531, 531, "North Macedonia", "🇲🇰"),
    (535, 535, "Malta", "🇲🇹"),
    (539, 539, "Ireland", "🇮🇪"),
    (540, 549, "Belgium & Luxembourg", "🇧🇪"),
    (560, 560, "Portugal", "🇵🇹"),
    (569, 569, "Iceland", "🇮🇸"),
    (570, 579, "Denmark", "🇩🇰"),
    (590, 590, "Poland", "🇵🇱"),
    (594, 594, "Romania", "🇷🇴"),
    (599, 599, "Hungary", "🇭🇺"),
    (600, 601, "South Africa", "🇿🇦"),
    (603, 603, "Ghana", "🇬🇭"),
    (604, 604, "Senegal", "🇸🇳"),
    (608, 608, "Bahrain", "🇧🇭"),
    (609, 609, "Mauritius", "🇲🇺"),
    (611, 611, "Morocco", "🇲🇦"),
    (613, 613, "Algeria", "🇩🇿"),
    (615, 615, "Nigeria", "🇳🇬"),
    (616, 616, "Kenya", "🇰🇪"),
    (618, 618, "Ivory Coast", "🇨🇮"),
    (619, 619, "Tunisia", "🇹🇳"),
    (620, 620, "Tanzania", "🇹🇿"),
    (621, 621, "Syria", "🇸🇾"),
    (622, 622, "Egypt", "🇪🇬"),
    (624, 624, "Libya", "🇱🇾"),
    (625, 625, "Jordan", "🇯🇴"),
    (626, 626, "Iran", "🇮🇷"),
    (627, 627, "Kuwait", "🇰🇼"),
    (628, 628, "Saudi Arabia", "🇸🇦"),
    (629, 629, "United Arab Emirates", "🇦🇪"),
    (640, 649, "Finland", "🇫🇮"),
    (690, 699, "China", "🇨🇳"),
    (700, 709, "Norway", "🇳🇴"),
    (729, 729, "Israel", "🇮🇱"),
    (730, 739, "Sweden", "🇸🇪"),
    (740, 740, "Guatemala", "🇬🇹"),
    (741, 741, "El Salvador", "🇸🇻"),
    (742, 742, "Honduras", "🇭🇳"),
    (743, 743, "Nicaragua", "🇳🇮"),
    (744, 744, "Costa Rica", "🇨🇷"),
    (745, 745, "Panama", "🇵🇦"),
    (746, 746, "Dominican Republic", "🇩🇴"),
    (750, 750, "Mexico", "🇲🇽"),
    (754, 755, "Canada", "🇨🇦"),
    (759, 759, "Venezuela", "🇻🇪"),
    (760, 769, "Switzerland", "🇨🇭"),
    (770, 771, "Colombia", "🇨🇴"),
    (773, 773, "Uruguay", "🇺🇾"),
    (775, 775, "Peru", "🇵🇪"),
    (777, 777, "Bolivia", "🇧🇴"),
    (778, 779, "Argentina", "🇦🇷"),
    (780, 780, "Chile", "🇨🇱"),
    (784, 784, "Paraguay", "🇵🇾"),
    (786, 786, "Ecuador", "🇪🇨"),
    (789, 790, "Brazil", "🇧🇷"),
    (800, 839, "Italy", "🇮🇹"),
    (840, 849, "Spain", "🇪🇸"),
    (850, 850, "Cuba", "🇨🇺"),
    (858, 858, "Slovakia", "🇸🇰"),
    (859, 859, "Czech Republic", "🇨🇿"),
    (860, 860, "Serbia", "🇷🇸"),
    (865, 865, "Mongolia", "🇲🇳"),
    (867, 867, "North Korea", "🇰🇵"),
    (868, 869, "Turkey", "🇹🇷"),
    (870, 879, "Netherlands", "🇳🇱"),
    (880, 880, "South Korea", "🇰🇷"),
    (884, 884, "Cambodia", "🇰🇭"),
    (885, 885, "Thailand", "🇹🇭"),
    (888, 888, "Singapore", "🇸🇬"),
    (890, 890, "India", "🇮🇳"),
    (893, 893, "Vietnam", "🇻🇳"),
    (896, 896, "Pakistan", "🇵🇰"),
    (899, 899, "Indonesia", "🇮🇩"),
    (900, 919, "Austria", "🇦🇹"),
    (930, 939, "Australia", "🇦🇺"),
    (940, 949, "New Zealand", "🇳🇿"),
    (955, 955, "Malaysia", "🇲🇾"),
    (958, 958, "Macau", "🇲🇴"),
]

MANUFACTURING_DISCLAIMER = (
    "GS1 prefix designates the issuing Member Organization (e.g., GS1 India for 890), "
    "not guaranteed country of manufacturing."
)


class GTINValidator:
    """Standard GS1 GTIN normalization, validation, and metadata derivation."""

    @staticmethod
    def calculate_check_digit(digits_str: str) -> int:
        """
        Calculate GS1 standard Modulo-10 check digit for a prefix string.
        Rule: Starting immediately to the left of check digit position (weight 3),
        alternate weights 3, 1, 3, 1 moving right-to-left.
        Check digit is the number that brings total to next multiple of 10.
        """
        clean = re.sub(r'\D', '', str(digits_str))
        if not clean:
            return 0
        rev = clean[::-1]
        total = sum(int(c) * (3 if idx % 2 == 0 else 1) for idx, c in enumerate(rev))
        rem = total % 10
        return 0 if rem == 0 else (10 - rem)

    @classmethod
    def validate_modulo10(cls, code: str) -> bool:
        """
        Validate whether the given string is a valid GTIN (8, 12, 13, 14 digits)
        with a correct GS1 Modulo-10 check digit.
        """
        clean = re.sub(r'\D', '', str(code))
        if len(clean) not in (8, 12, 13, 14):
            return False
        prefix = clean[:-1]
        expected = cls.calculate_check_digit(prefix)
        return int(clean[-1]) == expected

    @staticmethod
    def normalize_gtin(code: str) -> Optional[str]:
        """
        Cleans non-digits and returns valid raw GTIN string (8, 12, 13, or 14 digits),
        or None if not a standard GTIN length.
        """
        clean = re.sub(r'\D', '', str(code))
        if len(clean) in (8, 12, 13, 14):
            return clean
        return None

    @classmethod
    def to_gtin14(cls, code: str) -> Optional[str]:
        """
        Converts any valid GTIN (8, 12, 13, 14 digits) to its 14-digit zero-padded canonical form.
        Returns None if invalid GTIN.
        """
        clean = cls.normalize_gtin(code)
        if not clean:
            return None
        return clean.zfill(14)

    @staticmethod
    def identify_format(code: str) -> str:
        """Identify GTIN symbology format: GTIN-8, GTIN-12 (UPC-A), GTIN-13 (EAN-13), GTIN-14."""
        clean = re.sub(r'\D', '', str(code))
        l = len(clean)
        if l == 8:
            return "GTIN-8"
        if l == 12:
            return "GTIN-12 (UPC-A)"
        if l == 13:
            return "GTIN-13 (EAN-13)"
        if l == 14:
            return "GTIN-14"
        return "UNKNOWN_FORMAT"

    @staticmethod
    def resolve_prefix_jurisdiction(code: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Resolves issuing GS1 Member Organization / country and emoji flag from prefix.
        Returns: (Organization/Country Name, Flag Emoji, Prefix string)
        """
        clean = re.sub(r'\D', '', str(code))
        # If 14-digit, strip packaging indicator digit (first digit) to inspect GS1 prefix
        if len(clean) == 14:
            clean = clean[1:]
        # If 12-digit (UPC), UPC 0-19 falls in USA/Canada
        if len(clean) == 12:
            clean = "0" + clean

        if len(clean) < 3:
            return None, None, None

        # Check 3-digit prefix
        try:
            pref_3 = int(clean[:3])
            for p_min, p_max, country, flag in GS1_COUNTRY_PREFIXES:
                if p_min <= pref_3 <= p_max:
                    return country, flag, str(pref_3)
        except ValueError:
            pass

        # Check 2-digit prefix
        try:
            pref_2 = int(clean[:2])
            for p_min, p_max, country, flag in GS1_COUNTRY_PREFIXES:
                if p_min <= pref_2 <= p_max:
                    return country, flag, str(pref_2)
        except ValueError:
            pass

        return "Unknown Jurisdiction", "🌐", clean[:3]

    @classmethod
    def get_gtin_metadata(cls, code: str) -> Dict[str, Any]:
        """
        Returns full diagnostic and normalization dictionary for a GTIN.
        """
        clean = re.sub(r'\D', '', str(code))
        is_length_ok = len(clean) in (8, 12, 13, 14)
        is_checksum_valid = cls.validate_modulo10(clean) if is_length_ok else False
        country, flag, prefix = cls.resolve_prefix_jurisdiction(clean)
        format_name = cls.identify_format(clean)
        gtin14 = cls.to_gtin14(clean) if (is_length_ok and is_checksum_valid) else None

        return {
            "barcode_raw": str(code),
            "barcode_normalized": clean,
            "gtin": clean if is_length_ok else None,
            "gtin14": gtin14,
            "format": format_name,
            "checksum_valid": is_checksum_valid,
            "prefix": prefix,
            "country_name": country,
            "country_flag": flag,
            "country_note": MANUFACTURING_DISCLAIMER
        }


gtin_validator = GTINValidator()
