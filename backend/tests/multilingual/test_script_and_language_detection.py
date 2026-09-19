import pytest
from multilingual.detector import (
    detect_char_script,
    detect_token_script,
    detect_language_and_script,
    detect_token_language,
    detect_document_languages,
    MultilingualDetector,
)

def test_detect_char_script_coverage():
    assert detect_char_script('A') == 'Latin'
    assert detect_char_script('z') == 'Latin'
    assert detect_char_script('क') == 'Devanagari'
    assert detect_char_script('ক') == 'Bengali'
    assert detect_char_script('ક') == 'Gujarati'
    assert detect_char_script('ਕ') == 'Gurmukhi'
    assert detect_char_script('க') == 'Tamil'
    assert detect_char_script('క') == 'Telugu'
    assert detect_char_script('ಕ') == 'Kannada'
    assert detect_char_script('ക') == 'Malayalam'

def test_detect_token_script():
    assert detect_token_script('Metrology') == 'Latin'
    assert detect_token_script('किराना') == 'Devanagari'
    assert detect_token_script('தமிழ்நாடு') == 'Tamil'
    assert detect_token_script('100g') == 'Latin'

def test_pure_indic_script_detection():
    # Bengali
    lang, conf, script = detect_language_and_script('মোট ওজন ৫০০ গ্রাম')
    assert lang == 'bn'
    assert script == 'Bengali'
    assert conf > 0.8

    # Tamil
    lang, conf, script = detect_language_and_script('நிகர எடை 500 கிராம்')
    assert lang == 'ta'
    assert script == 'Tamil'
    assert conf > 0.8

    # Gujarati
    lang, conf, script = detect_language_and_script('ચોખ્ખું વજન ૧ કિગ્રા')
    assert lang == 'gu'
    assert script == 'Gujarati'
    assert conf > 0.8

    # Telugu
    lang, conf, script = detect_language_and_script('నికర పరిమాణం 500 గ్రాములు')
    assert lang == 'te'
    assert script == 'Telugu'
    assert conf > 0.8

    # Kannada
    lang, conf, script = detect_language_and_script('ನಿವ್ವಳ ತೂಕ ೫೦೦ ಗ್ರಾಂ')
    assert lang == 'kn'
    assert script == 'Kannada'
    assert conf > 0.8

    # Malayalam
    lang, conf, script = detect_language_and_script('അറ്റ അളവ് 500 ഗ്രാം')
    assert lang == 'ml'
    assert script == 'Malayalam'
    assert conf > 0.8

    # Punjabi
    lang, conf, script = detect_language_and_script('ਨੈੱਟ ਵਜ਼ਨ 500 ਗ੍ਰਾਮ')
    assert lang == 'pa'
    assert script == 'Gurmukhi'
    assert conf > 0.8

def test_hindi_marathi_disambiguation():
    # Marathi distinctive markers (आहे, चे, च्या, वजन, दिनांक, ग्राहक)
    mr_text = 'हे उत्पादन महाराष्ट्रात तयार केले आहे. निव्वळ वजन २५० ग्रॅम.'
    lang_mr, conf_mr, script_mr = detect_language_and_script(mr_text)
    assert lang_mr == 'mr'
    assert script_mr == 'Devanagari'

    # Hindi distinctive markers (है, का, की, के, मूल्य, संपर्क)
    hi_text = 'यह उत्पाद भारत में निर्मित है। अधिकतम खुदरा मूल्य ₹२५०.०० है।'
    lang_hi, conf_hi, script_hi = detect_language_and_script(hi_text)
    assert lang_hi == 'hi'
    assert script_hi == 'Devanagari'

def test_detect_document_languages_mixed():
    mixed_text = (
        'Net Quantity 500g MRP Rs 100 '
        'अधिकतम खुदरा मूल्य ₹१०० नेट मात्रा ५०० ग्राम'
    )
    meta = detect_document_languages(mixed_text)
    assert meta["mixed_language"] is True
    detected_codes = [l["code"] for l in meta["detected_languages"]]
    assert 'en' in detected_codes
    assert 'hi' in detected_codes
    assert 'Devanagari' in meta["detected_scripts"]
    assert 'Latin' in meta["detected_scripts"]
