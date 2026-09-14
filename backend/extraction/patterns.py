import re

PATTERNS = {
    'mrp': re.compile(
        r'(?:M\.?R\.?P\.?|Maximum\s*Retail\s*Price|Retail\s*Price|MRP\s*₹|MRP\s*Rs\.?|MRPR|एम\.?आर\.?पी\.?|अधिकतम\s*खुदरा\s*मूल्य|खुदरा\s*मूल्य|मूल्य)[\s.:₹RsINR\/\-*~#\'\"\=]*([0-9]{1,5}(?:\.[0-9]{1,2})?)',
        re.IGNORECASE
    ),
    'net_quantity': re.compile(
        r'(?:Net\s*(?:Wt\.?|Weight|Qty\.?|Quantity|Content|Vol\.?|Volume)|NETOTV|NET\s*QTV|शुद्ध\s*(?:मात्रा|वजन|भार)|मात्रा|भार|वजन)[\s.:\-A-Za-z\=]*([\d]+(?:\.\d+)?\s*(?:g|gm|gms|kg|ml|l|ltr|litre|liter|piece|pcs|N|9|ग्राम|कि\.?\s*ग्रा\.?|किग्रा|मि\.?\s*ली\.?|मिली|लीटर|ली\.?|इकाई|संख्या)s?)\b',
        re.IGNORECASE
    ),
    'manufacturing_date': re.compile(
        r'(?:Mfg\.?\s*(?:Date)?|Date\s*of\s*(?:Mfg|Packing)|Mfd\.?\s*(?:Date)?|Pkd\.?\s*(?:Date)?|Packed\s*on|Manufactured\s*(?:on|Date)?|MFD|MFG|PKD|निर्माण\s*(?:की\s*)?तिथि|पैकिंग\s*तिथि)[\s.:\-]*([A-Za-z0-9/.\-\u0900-\u097F]+(?:\s*[A-Za-z0-9\u0900-\u097F]+)?)',
        re.IGNORECASE
    ),
    'expiry_date': re.compile(
        r'(?:Exp(?:iry)?\.?\s*(?:Date)?|Best\s*Before|Use\s*By|EXP\s*DATE|EXPIRY|USE\s*BY|उपयोग\s*की\s*अंतिम\s*तिथि|समाप्ति\s*तिथि)[\s.:\-]*([A-Za-z0-9/.\-\s\u0900-\u097F]+?(?=\n|Batch|MRP|Mfg|Pkd|Unit|\.|$))',
        re.IGNORECASE
    ),
    'fssai_license': re.compile(
        r'(?:FSSAI|FSBAI|FOSSA|Lic\.?\s*(?:No\.?|Number)?|Licence\s*No\.?|एफएसएसएआई|लाइसेंस\s*संख्या)[\s.:\-=]*([0-9OlISBGzZ\s\-]{13,20})',
        re.IGNORECASE
    ),
    'consumer_care': re.compile(
        r'(?:Customer|Consumer|Feedback|Complaints?|Queries|उपभोक्ता|ग्राहक)\s*(?:Care|Support|Service|Helpline|सेवा|सहायता|&|and)?[\s.:\-]*([a-zA-Z0-9@.\-\+\s,\u0900-\u097F]+?(?=\n[A-Z\s]{4,}:|\n\n|$))',
        re.IGNORECASE
    ),
    'country_of_origin': re.compile(
        r'(?:Country\s*of\s*Origin|Made\s*in|Produce\s*of|Product\s*of|उत्पत्ति\s*का\s*देश|निर्मित\s*देश)[\s.:\-]*\b(India|Bharat|भारत|USA|United\s*States|UK|United\s*Kingdom|Australia|China|Thailand|Vietnam|Italy|Germany|France|Japan|Indonesia|Malaysia|Sri\s*Lanka|Bangladesh|Nepal|Canada|New\s*Zealand|UAE|Switzerland|[A-Za-z\u0900-\u097F]+(?=\s*(?:,|\.|\n|$)))',
        re.IGNORECASE
    ),
    'manufacturer': re.compile(
        r'(?:Mfd|Manufactured|Packed|Mktd|Marketed|निर्माता|पैकर|द्वारा\s*निर्मित|उत्पादक)[\w\s.:\&\-\u0900-\u097F]*?(?:by)?[:\s\-]+([A-Za-z0-9\s,\.\-\&\u0900-\u097F]{3,50}?(?:Ltd|Pvt|Limited|LLP|Company|Enterprises|Foods|Snacks|Bakers|लिमिटेड|प्राइवेट\s*लिमिटेड|उद्योग))\b',
        re.IGNORECASE
    ),
    'marketed_by': re.compile(
        r'(?:Marketed\s*by|Mktd\.?\s*by|Merkotod\s*Dy|विपणक|द्वारा\s*विपणन)[:\s\-]+([A-Za-z0-9\s,\.\-\&\u0900-\u097F]{3,50}?(?:Ltd|Pvt|Limited|LLP|Company|Enterprises|Foods|Snacks|Bakers|लिमिटेड|उद्योग))\b',
        re.IGNORECASE
    ),
    'best_before': re.compile(
        r'(?:Best\s*Before|BEST\s*BEFORE|सर्वश्रेष्ठ\s*पहले)[\s.:\-]*([A-Za-z0-9/.\-\s\u0900-\u097F]+?(?=\n|Batch|MRP|Mfg|Pkd|Unit|\.|$))',
        re.IGNORECASE
    ),
    'batch_number': re.compile(
        r'(?:Batch\s*(?:No\.?|Number)?|Lot\s*(?:No\.?|Number)?|B\.?\s*No\.?|BATCH|LOT|BATCH\s*NO\.?|बैच\s*(?:संख्या|नं\.?|क्र\.?)|लॉट\s*नं\.?)[\s.:\-]*([A-Za-z0-9\-_\/]+)',
        re.IGNORECASE
    ),
}

FALLBACK_PATTERNS = {
    'mrp': re.compile(r'(?:\bRs\.?|₹)\s*([\d,]+(?:\.\d{2})?)', re.IGNORECASE),
    'fssai_license': re.compile(r'\b(1\d{13}|2\d{13})\b'),
    'email': re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
    'phone': re.compile(r'(?:\+91[\s\-]?)?[6-9]\d{4}[\s\-]?\d{5}|1800[\s\-]?(?:\d{3}[\s\-]?\d{3,4}|\d{2}[\s\-]?\d{2}[\s\-]?\d{3,4}|\d{6,8})|0\d{2,4}[-\s]?\d{6,8}'),
    'company': re.compile(r'\b([A-Za-z\s]{3,35}\s*(?:Health\s*Foods|Foods|Snacks|Enterprises|Industries|Bakers|Pvt\s*Ltd|Pvt\.?\s*Ltd|Py?t\s*Lt\.?|Private\s*Limited|Ltd\.?|LLP))\b', re.IGNORECASE),
}
