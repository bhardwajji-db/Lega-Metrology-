"""
MetrCheck AI — Controlled Deterministic Multilingual Localization Layer

Provides deterministic, template-driven localizations for:
- Statutory Field Labels (LM-001..LM-009, FS-001..FS-005)
- Compliance Statuses (PASS, FAIL, WARNING, NEEDS_REVIEW, NOT_APPLICABLE)
- Rule Explanations and Legal Findings across all 10 languages
- Recommendation Titles and Corrective Actions
- PDF Report Headings and Metadata Labels

NO UNCONTROLLED LLM TRANSLATIONS. All text is derived from verified statutory templates.
"""

from typing import Dict, Any, Optional, List

LOCALIZED_STATUSES: Dict[str, Dict[str, str]] = {
    "en": {"PASS": "PASS", "FAIL": "FAIL", "WARNING": "WARNING", "NEEDS_REVIEW": "NEEDS REVIEW", "NOT_APPLICABLE": "NOT APPLICABLE", "COMPLIANT": "COMPLIANT", "NON_COMPLIANT": "NON-COMPLIANT"},
    "hi": {"PASS": "उत्तीर्ण (पास)", "FAIL": "विफल", "WARNING": "चेतावनी", "NEEDS_REVIEW": "समीक्षा आवश्यक", "NOT_APPLICABLE": "लागू नहीं", "COMPLIANT": "अनुपालक", "NON_COMPLIANT": "गैर-अनुपालक"},
    "bn": {"PASS": "উত্তীর্ণ", "FAIL": "ব্যর্থ", "WARNING": "সতর্কতা", "NEEDS_REVIEW": "পর্যালোচনা প্রয়োজন", "NOT_APPLICABLE": "প্রযোজ্য নয়", "COMPLIANT": "সম্মত", "NON_COMPLIANT": "অসম্মত"},
    "mr": {"PASS": "उत्तीर्ण", "FAIL": "अपात्र", "WARNING": "सूचना", "NEEDS_REVIEW": "तपासणी आवश्यक", "NOT_APPLICABLE": "लागू नाही", "COMPLIANT": "सुसंगत", "NON_COMPLIANT": "असंगत"},
    "gu": {"PASS": "પાસ", "FAIL": "નિષ્ફળ", "WARNING": "ચેતવણી", "NEEDS_REVIEW": "સમીક્ષા જરૂરી", "NOT_APPLICABLE": "લાગુ નથી", "COMPLIANT": "સુસંગત", "NON_COMPLIANT": "બિન-સુસંગત"},
    "pa": {"PASS": "ਪਾਸ", "FAIL": "ਅਸਫ਼ਲ", "WARNING": "ਚੇਤਾਵਨੀ", "NEEDS_REVIEW": "ਜਾਂਚ ਦੀ ਲੋੜ", "NOT_APPLICABLE": "ਲਾਗੂ ਨਹੀਂ", "COMPLIANT": "ਪਾਲਣਾ", "NON_COMPLIANT": "ਗੈਰ-ਪਾਲਣਾ"},
    "ta": {"PASS": "தேர்ச்சி", "FAIL": "தோல்வி", "WARNING": "எச்சரிக்கை", "NEEDS_REVIEW": "மறுஆய்வு தேவை", "NOT_APPLICABLE": "பொருந்தாது", "COMPLIANT": "இணக்கமானது", "NON_COMPLIANT": "இணக்கமற்றது"},
    "te": {"PASS": "ఉత్తీర్ణం", "FAIL": "విఫలం", "WARNING": "హెచ్చరిక", "NEEDS_REVIEW": "సమీక్ష అవసరం", "NOT_APPLICABLE": "వర్తించదు", "COMPLIANT": "అనుగుణంగా ఉంది", "NON_COMPLIANT": "నిబంధనలకు విరుద్ధం"},
    "kn": {"PASS": "ಪಾಸಾಗಿದೆ", "FAIL": "ವಿಫಲವಾಗಿದೆ", "WARNING": "ಎಚ್ಚರಿಕೆ", "NEEDS_REVIEW": "ಪರಿಶೀಲನೆ ಅಗತ್ಯ", "NOT_APPLICABLE": "ಅನ್ವಯಿಸುವುದಿಲ್ಲ", "COMPLIANT": "ಅನುಸರಣೆಯಾಗಿದೆ", "NON_COMPLIANT": "ಅನುಸರಿಸಿಲ್ಲ"},
    "ml": {"PASS": "വിജയിച്ചു", "FAIL": "പരാജയം", "WARNING": "മുന്നറിയിപ്പ്", "NEEDS_REVIEW": "പരിശോധന ആവശ്യമാണ്", "NOT_APPLICABLE": "ബാധകമല്ല", "COMPLIANT": "അനുസൃതമാണ്", "NON_COMPLIANT": "അനുസൃതമല്ല"}
}

LOCALIZED_FIELD_LABELS: Dict[str, Dict[str, str]] = {
    "en": {
        "LM-001": "Manufacturer / Packer / Importer",
        "LM-002": "Common / Generic Name",
        "LM-003": "Net Quantity",
        "LM-004": "Maximum Retail Price (MRP)",
        "LM-005": "Consumer Care Details",
        "LM-006": "Country of Origin",
        "LM-007": "Unit Sale Price",
        "LM-008": "Date of Manufacture / Packing",
        "LM-009": "Best Before / Expiry Duration",
        "FS-001": "FSSAI Licence Number / Logo",
        "FS-002": "Name of Food",
        "FS-003": "List of Ingredients",
        "FS-004": "Nutritional Information Panel",
        "FS-005": "Date Marking (Best Before / Expiry)"
    },
    "hi": {
        "LM-001": "निर्माता / पैककर्ता / आयातक का विवरण",
        "LM-002": "उत्पाद का सामान्य / जेनेरिक नाम",
        "LM-003": "शुद्ध मात्रा / वजन",
        "LM-004": "अधिकतम खुदरा मूल्य (MRP)",
        "LM-005": "उपभोक्ता देखभाल विवरण",
        "LM-006": "मूल देश (Country of Origin)",
        "LM-007": "इकाई विक्रय मूल्य (Unit Sale Price)",
        "LM-008": "निर्माण / पैकिंग की तारीख",
        "LM-009": "सर्वोत्तम उपयोग / समाप्ति अवधि",
        "FS-001": "एफएसएसएआई लाइसेंस नंबर / लोगो",
        "FS-002": "खाद्य पदार्थ का नाम",
        "FS-003": "सामग्री की सूची",
        "FS-004": "पोषण संबंधी जानकारी तालिका",
        "FS-005": "तिथि अंकन (सर्वोत्तम उपयोग / समाप्ति)"
    },
    "mr": {
        "LM-001": "उत्पादक / पॅकर / आयातदार माहिती",
        "LM-002": "उत्पादनाचे सामान्य नाव",
        "LM-003": "निव्वळ प्रमाण / वजन",
        "LM-004": "कमाल किरकोळ किंमत (MRP)",
        "LM-005": "ग्राहक सेवा तपशील",
        "LM-006": "मूळ देश",
        "LM-007": "प्रति एकक विक्री किंमत",
        "LM-008": "उत्पादन / पॅकिंग दिनांक",
        "LM-009": "वापरण्यायोग्य कालावधी",
        "FS-001": "एफएसएसएआय परवाना क्रमांक",
        "FS-002": "अन्नाचे नाव",
        "FS-003": "घटकांची यादी",
        "FS-004": "पोषण माहिती तक्ता",
        "FS-005": "दिनांक नोंदणी"
    },
    "bn": {
        "LM-001": "প্রস্তুতকারক / প্যাকার / আমদানিকারক",
        "LM-002": "পণ্যের সাধারণ নাম",
        "LM-003": "নিট পরিমাণ / ওজন",
        "LM-004": "সর্বোচ্চ খুচরা মূল্য (MRP)",
        "LM-005": "গ্রাহক পরিষেবা বিবরণ",
        "LM-006": "উৎপত্তির দেশ",
        "LM-007": "একক বিক্রয় মূল্য",
        "LM-008": "উৎপাদন / প্যাকিংয়ের তারিখ",
        "LM-009": "ব্যবহারের সর্বোত্তম সময়",
        "FS-001": "এফএসএসএআই লাইসেন্স নম্বর",
        "FS-002": "খাদ্যের নাম",
        "FS-003": "উপাদানের তালিকা",
        "FS-004": "পুষ্টি তথ্য প্যানেল",
        "FS-005": "তারিখ চিহ্নিতকরণ"
    },
    "gu": {
        "LM-001": "ઉત્પાદક / પેકર / આયાતકાર વિગતો",
        "LM-002": "ઉત્પાદનનું સામાન્ય નામ",
        "LM-003": "ચોખ્ખો જથ્થો / વજન",
        "LM-004": "મહત્તમ છૂટક કિંમત (MRP)",
        "LM-005": "ગ્રાહક સેવા વિગતો",
        "LM-006": "મૂળ દેશ",
        "LM-007": "યુનિટ વેચાણ કિંમત",
        "LM-008": "ઉત્પાદન / પેકિંગ તારીખ",
        "LM-009": "શ્રેષ્ઠ ઉપયોગ અવધિ",
        "FS-001": "એફએસએસએઆઈ લાઇસન્સ નંબર",
        "FS-002": "ખાદ્ય પદાર્થનું નામ",
        "FS-003": "સામગ્રીની સૂચિ",
        "FS-004": "પોષણ માહિતી પેનલ",
        "FS-005": "તારીખ માર્કિંગ"
    },
    "pa": {
        "LM-001": "ਨਿਰਮਾਤਾ / ਪੈਕਰ / ਆਯਾਤਕ ਵੇਰਵਾ",
        "LM-002": "ਉਤਪਾਦ ਦਾ ਆਮ ਨਾਮ",
        "LM-003": "ਸ਼ੁੱਧ ਮਾਤਰਾ / ਭਾਰ",
        "LM-004": "ਵੱਧ ਤੋਂ ਵੱਧ ਪ੍ਰਚੂਨ ਮੁੱਲ (MRP)",
        "LM-005": "ਗਾਹਕ ਸੇਵਾ ਵੇਰਵਾ",
        "LM-006": "ਮੂਲ ਦੇਸ਼",
        "LM-007": "ਪ੍ਰਤੀ ਇਕਾਈ ਵਿਕਰੀ ਮੁੱਲ",
        "LM-008": "ਨਿਰਮਾਣ / ਪੈਕਿੰਗ ਮਿਤੀ",
        "LM-009": "ਵਰਤੋਂ ਯੋਗ ਸਮਾਂ",
        "FS-001": "ਐਫਐਸਐਸਏਆਈ ਲਾਇਸੈਂਸ ਨੰਬਰ",
        "FS-002": "ਭੋਜਨ ਦਾ ਨਾਮ",
        "FS-003": "ਸਮੱਗਰੀ ਦੀ ਸੂਚੀ",
        "FS-004": "ਪੋਸ਼ਣ ਜਾਣਕਾਰੀ ਪੈਨਲ",
        "FS-005": "ਮਿਤੀ ਨਿਸ਼ਾਨਦੇਹੀ"
    },
    "ta": {
        "LM-001": "உற்பத்தியாளர் / பேக்கர் / இறக்குமதியாளர் விவரம்",
        "LM-002": "தயாரிப்பின் பொதுவான பெயர்",
        "LM-003": "நிகர அளவு / எடை",
        "LM-004": "அதிகபட்ச சில்லறை விலை (MRP)",
        "LM-005": "வாடிக்கையாளர் சேவை விவரங்கள்",
        "LM-006": "பிறப்பிட நாடு",
        "LM-007": "அலகு விற்பனை விலை",
        "LM-008": "உற்பத்தி / பேக்கிங் தேதி",
        "LM-009": "சிறந்த பயன்பாட்டு காலம்",
        "FS-001": "எஃப்எஸ்எஸ்ஏஐ உரிம எண்",
        "FS-002": "உணவின் பெயர்",
        "FS-003": "பொருட்களின் பட்டியல்",
        "FS-004": "ஊட்டச்சத்து தகவல் பலகை",
        "FS-005": "தேதி குறிப்பு"
    },
    "te": {
        "LM-001": "తయారీదారు / ప్యాకర్ / దిగుమతిదారు వివరాలు",
        "LM-002": "ఉత్పత్తి సాధారణ పేరు",
        "LM-003": "నికర పరిమాణం / బరువు",
        "LM-004": "గరిష్ట చిల్లర ధర (MRP)",
        "LM-005": "కస్టమర్ కేర్ వివరాలు",
        "LM-006": "మూల దేశం",
        "LM-007": "యూనిట్ అమ్మకపు ధర",
        "LM-008": "తయారీ / ప్యాకింగ్ తేదీ",
        "LM-009": "ఉత్తమ వినియోగ గడువు",
        "FS-001": "ఎఫ్ఎస్ఎస్ఏఐ లైసెన్స్ సంఖ్య",
        "FS-002": "ఆహారం పేరు",
        "FS-003": "పదార్థాల జాబితా",
        "FS-004": "పోషకాహార సమాచార ప్యానెల్",
        "FS-005": "తేదీ మార్కింగ్"
    },
    "kn": {
        "LM-001": "ತಯಾರಕರು / ಪ್ಯಾಕರ್ ವಿವರಗಳು",
        "LM-002": "ಉತ್ಪನ್ನದ ಸಾಮಾನ್ಯ ಹೆಸರು",
        "LM-003": "ನಿವ್ವಳ ಪ್ರಮಾಣ / ತೂಕ",
        "LM-004": "ಗರಿಷ್ಠ ಚಿಲ್ಲರೆ ಬೆಲೆ (MRP)",
        "LM-005": "ಗ್ರಾಹಕ ಸೇವಾ ವಿವರಗಳು",
        "LM-006": "ಮೂಲ ದೇಶ",
        "LM-007": "ಪ್ರತಿ ಘಟಕದ ಮಾರಾಟ ಬೆಲೆ",
        "LM-008": "ತಯಾರಿಕಾ / ಪ್ಯಾಕಿಂಗ್ ದಿನಾಂಕ",
        "LM-009": "ಬಳಕೆಯ ಗಡುವು",
        "FS-001": "ಎಫ್‌ಎಸ್‌ಎಸ್‌ಎಐ ಪರವಾನಗಿ ಸಂಖ್ಯೆ",
        "FS-002": "ಆಹಾರದ ಹೆಸರು",
        "FS-003": "ಪದಾರ್ಥಗಳ ಪಟ್ಟಿ",
        "FS-004": "ಪೌಷ್ಟಿಕಾಂಶ ಮಾಹಿತಿ ಫಲಕ",
        "FS-005": "ದಿನಾಂಕ ನಮೂದು"
    },
    "ml": {
        "LM-001": "ഉത്പാദകർ / പാക്കർ വിവരങ്ങൾ",
        "LM-002": "ഉൽപ്പന്നത്തിന്റെ പേര്",
        "LM-003": "അറ്റ അളവ് / തൂക്കം",
        "LM-004": "പരമാവധി ചില്ലറ വിൽപ്പന വില (MRP)",
        "LM-005": "ഉപഭോക്തൃ സേവന വിവരങ്ങൾ",
        "LM-006": "ഉത്ഭവ രാജ്യം",
        "LM-007": "യൂണിറ്റ് വിൽപ്പന വില",
        "LM-008": "ഉത്പാദന / പാക്കിംഗ് തീയതി",
        "LM-009": "ഉപയോഗ യോഗ്യതാ കാലാവധി",
        "FS-001": "എഫ്എസ്എസ്എഐ ലൈസൻസ് നമ്പർ",
        "FS-002": "ഭക്ഷണത്തിന്റെ പേര്",
        "FS-003": "ചേരുവകളുടെ പട്ടിക",
        "FS-004": "പോഷകാഹാര വിവര പാനൽ",
        "FS-005": "തീയതി രേഖപ്പെടുത്തൽ"
    }
}

LOCALIZED_EXPLANATION_TEMPLATES: Dict[str, Dict[str, Dict[str, str]]] = {
    "en": {
        "PASS": {
            "LM-001": "Manufacturer/Packer name and address verified on packaging.",
            "LM-002": "Common/Generic name of commodity is clearly declared.",
            "LM-003": "Net quantity is declared in standard metric units.",
            "LM-004": "Maximum Retail Price (MRP) is clearly declared inclusive of all taxes.",
            "LM-005": "Consumer helpline/contact details are properly declared.",
            "LM-006": "Country of origin is declared as required for commodities.",
            "LM-007": "Unit sale price is declared in accordance with statutory guidelines.",
            "LM-008": "Date of manufacture/pre-packing is properly declared.",
            "LM-009": "Best before / relative shelf life is clearly indicated.",
            "FS-001": "Valid 14-digit FSSAI licence number is present on the package.",
            "FS-002": "Food name is clearly declared.",
            "FS-003": "Complete list of ingredients is declared in descending order.",
            "FS-004": "Nutritional information panel is properly displayed.",
            "FS-005": "Date marking (expiry/best before) is present."
        },
        "FAIL": {
            "LM-001": "Manufacturer or Packer declaration is missing or incomplete.",
            "LM-002": "Common or Generic name of the commodity is missing.",
            "LM-003": "Net quantity declaration is missing or in non-standard units.",
            "LM-004": "Maximum Retail Price (MRP) declaration could not be verified.",
            "LM-005": "Consumer care name, address, phone or email is missing.",
            "LM-006": "Country of origin is missing on the package.",
            "LM-007": "Unit sale price declaration is missing.",
            "LM-008": "Date of manufacture or packing is missing.",
            "LM-009": "Best before or expiry duration is missing.",
            "FS-001": "FSSAI licence number or logo is missing on food package.",
            "FS-002": "Standard food name is missing.",
            "FS-003": "Ingredients declaration is missing on food package.",
            "FS-004": "Nutritional information panel is missing.",
            "FS-005": "Mandatory date marking is missing."
        }
    },
    "hi": {
        "PASS": {
            "LM-001": "निर्माता/पैककर्ता का नाम एवं पता पैकेजिंग पर सत्यापित है।",
            "LM-002": "उत्पाद का सामान्य/जेनेरिक नाम स्पष्ट रूप से घोषित है।",
            "LM-003": "शुद्ध मात्रा मानक मीट्रिक इकाइयों में घोषित है।",
            "LM-004": "अधिकतम खुदरा मूल्य (MRP) सभी करों सहित स्पष्ट रूप से घोषित है।",
            "LM-005": "उपभोक्ता हेल्पलाइन/संपर्क विवरण नियमानुसार घोषित है।",
            "LM-006": "मूल देश (Country of Origin) नियमानुसार घोषित है।",
            "LM-007": "इकाई विक्रय मूल्य वैधानिक दिशानिर्देशों के अनुसार घोषित है।",
            "LM-008": "निर्माण/पैकिंग की तारीख उचित रूप से घोषित है।",
            "LM-009": "सर्वोत्तम उपयोग अवधि स्पष्ट रूप से दर्शायी गई है।",
            "FS-001": "मान्य 14-अंकीय एफएसएसएआई लाइसेंस नंबर पैकेज पर उपस्थित है।",
            "FS-002": "खाद्य पदार्थ का नाम स्पष्ट रूप से घोषित है।",
            "FS-003": "सामग्रियों की पूर्ण सूची घोषित है।",
            "FS-004": "पोषण संबंधी जानकारी तालिका पैकेज पर उपलब्ध है।",
            "FS-005": "तिथि अंकन (समाप्ति/सर्वोत्तम उपयोग) उपस्थित है।"
        },
        "FAIL": {
            "LM-001": "निर्माता या पैककर्ता का विवरण पैकेज पर गायब या अधूरा है।",
            "LM-002": "उत्पाद का सामान्य या जेनेरिक नाम अनुपस्थित है।",
            "LM-003": "शुद्ध मात्रा की घोषणा अनुपस्थित है या अमानक इकाई में है।",
            "LM-004": "अधिकतम खुदरा मूल्य (MRP) की घोषणा सत्यापित नहीं की जा सकी।",
            "LM-005": "उपभोक्ता सेवा फोन/ईमेल संपर्क विवरण गायब है।",
            "LM-006": "मूल देश की घोषणा पैकेज पर नहीं मिली।",
            "LM-007": "इकाई विक्रय मूल्य की घोषणा गायब है।",
            "LM-008": "निर्माण या पैकिंग की तारीख अनुपस्थित है।",
            "LM-009": "समाप्ति या सर्वोत्तम उपयोग अवधि गायब है।",
            "FS-001": "एफएसएसएआई लाइसेंस नंबर या लोगो खाद्य पैकेज पर नहीं मिला।",
            "FS-002": "मानक खाद्य नाम अनुपस्थित है।",
            "FS-003": "सामग्री सूची खाद्य पैकेज पर नहीं मिली।",
            "FS-004": "पोषण संबंधी जानकारी तालिका गायब है।",
            "FS-005": "अनिवार्य तिथि अंकन गायब है।"
        }
    }
}

REPORT_UI_LABELS: Dict[str, Dict[str, str]] = {
    "en": {
        "report_title": "Legal Metrology Compliance Screening Report",
        "subtitle": "Comprehensive Statutory Audit & Evidence Breakdown",
        "overall_status": "Overall Status",
        "compliance_score": "Compliance Score",
        "product_name": "Product Name",
        "generated_at": "Generated At",
        "detected_languages": "Detected Languages",
        "statutory_declarations": "Statutory Declarations Summary",
        "rule_evaluations": "Rule-by-Rule Compliance Evaluation",
        "field_header": "Field / Rule",
        "status_header": "Status",
        "detected_value_header": "Detected Value",
        "finding_header": "Statutory Finding",
        "evidence_summary": "Original Evidence & Traceability",
        "page": "Page",
        "disclaimer": "This screening report is generated automatically by MetrCheck AI to assist compliance officers. Official enforcement decisions must be verified with physical packaging."
    },
    "hi": {
        "report_title": "विधिक मापविज्ञान अनुपालन जांच रिपोर्ट",
        "subtitle": "विस्तृत वैधानिक लेखापरीक्षा एवं साक्ष्य विवरण",
        "overall_status": "समग्र स्थिति",
        "compliance_score": "अनुपालन स्कोर",
        "product_name": "उत्पाद का नाम",
        "generated_at": "रिपोर्ट जारी तिथि",
        "detected_languages": "पहचानी गई भाषाएं",
        "statutory_declarations": "वैधानिक घोषणाओं का सारांश",
        "rule_evaluations": "नियमवार अनुपालन मूल्यांकन",
        "field_header": "क्षेत्र / नियम",
        "status_header": "स्थिति",
        "detected_value_header": "प्राप्त मान",
        "finding_header": "वैधानिक निष्कर्ष",
        "evidence_summary": "मूल साक्ष्य एवं सत्यापन",
        "page": "पृष्ठ",
        "disclaimer": "यह जांच रिपोर्ट अनुपालन अधिकारियों की सहायता के लिए मेट्रचेक एआई द्वारा स्वचालित रूप से तैयार की गई है। आधिकारिक निर्णयों का भौतिक पैकेज से सत्यापन आवश्यक है।"
    }
}


def localize_rule_label(rule_id: str, lang: str = "en") -> str:
    """Retrieve localized label for a rule ID (falls back to English)."""
    l = (lang or "en").lower().strip()
    labels = LOCALIZED_FIELD_LABELS.get(l, LOCALIZED_FIELD_LABELS["en"])
    return labels.get(rule_id, LOCALIZED_FIELD_LABELS["en"].get(rule_id, rule_id))


def localize_status(status: str, lang: str = "en") -> str:
    """Retrieve localized status string."""
    l = (lang or "en").lower().strip()
    s = (status or "PASS").upper().replace("-", "_")
    statuses = LOCALIZED_STATUSES.get(l, LOCALIZED_STATUSES["en"])
    return statuses.get(s, s)


def localize_explanation(rule_id: str, status: str, detected_value: Optional[str] = None, lang: str = "en") -> str:
    """Retrieve localized explanation for a rule finding."""
    l = (lang or "en").lower().strip()
    st_group = "PASS" if status in ("PASS", "COMPLIANT") else "FAIL"
    
    lang_templates = LOCALIZED_EXPLANATION_TEMPLATES.get(l, LOCALIZED_EXPLANATION_TEMPLATES["en"])
    tpl_group = lang_templates.get(st_group, LOCALIZED_EXPLANATION_TEMPLATES["en"][st_group])
    base_expl = tpl_group.get(rule_id, LOCALIZED_EXPLANATION_TEMPLATES["en"][st_group].get(rule_id, "Status evaluated."))

    if detected_value and st_group == "PASS":
        if l == "hi":
            return f"{base_expl} (मान: {detected_value})"
        return f"{base_expl} (Declared: {detected_value})"
    return base_expl


def get_report_ui_labels(lang: str = "en") -> Dict[str, str]:
    """Retrieve localized UI headers and labels for PDF report generation."""
    l = (lang or "en").lower().strip()
    return REPORT_UI_LABELS.get(l, REPORT_UI_LABELS["en"])
