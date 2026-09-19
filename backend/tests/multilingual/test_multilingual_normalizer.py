import pytest
from multilingual.normalizer import (
    normalize_indic_digits,
    normalize_currency,
    normalize_units,
    parse_multilingual_date,
    normalize_multilingual_text,
    MultilingualNormalizer,
)

def test_indic_digits_normalization_all_scripts():
    # Devanagari ०-९
    assert normalize_indic_digits('₹२५०.५०') == '₹250.50'
    # Bengali ০-৯
    assert normalize_indic_digits('৫০০ গ্রাম') == '500 গ্রাম'
    # Gujarati ૦-૯
    assert normalize_indic_digits('૧૨૫ ગ્રામ') == '125 ગ્રામ'
    # Gurmukhi ੦-੯
    assert normalize_indic_digits('੫੦੦ ਗ੍ਰਾਮ') == '500 ਗ੍ਰਾਮ'
    # Tamil ௦-௯
    assert normalize_indic_digits('௨௫௦ மி.கி') == '250 மி.கி'
    # Telugu ౦-౯
    assert normalize_indic_digits('౫౦౦ గ్రాములు') == '500 గ్రాములు'
    # Kannada ೦-೯
    assert normalize_indic_digits('೫೦೦ ಗ್ರಾಂ') == '500 ಗ್ರಾಂ'
    # Malayalam ൦-൯
    assert normalize_indic_digits('൫൦൦ ഗ്രാം') == '500 ഗ്രാം'

def test_currency_normalization():
    assert normalize_currency('रु. 250') == '₹250'
    assert normalize_currency('रु २५०') == '₹250'
    assert normalize_currency('ரூ. 100') == '₹100'
    assert normalize_currency('ரூபாய் 500') == '₹500'
    assert normalize_currency('రూ. 300') == '₹300'
    assert normalize_currency('টাকা 400') == '₹400'
    assert normalize_currency('INR 150') == '₹150'
    assert normalize_currency('MRP Rs. 99.00') == 'MRP ₹99.00'

def test_unit_normalization():
    assert normalize_units('500 ग्राम') == '500 g'
    assert normalize_units('1 किलोग्राम') == '1 kg'
    assert normalize_units('250 मिली') == '250 ml'
    assert normalize_units('1 लीटर') == '1 l'
    assert normalize_units('500 ഗ്രാം') == '500 g'
    assert normalize_units('250 கிராம்') == '250 g'
    assert normalize_units('100 மி.கி') == '100 mg'
    assert normalize_units('500 గ్రా') == '500 g'
    assert normalize_units('100 ಗ್ರಾಂ') == '100 g'

def test_multilingual_date_parsing():
    # Hindi
    assert parse_multilingual_date('१५ जनवरी २०२४') == '15/01/2024'
    assert parse_multilingual_date('मार्च २०२४') == '03/2024'
    # Tamil
    assert parse_multilingual_date('10 ஜனவரி 2024') == '10/01/2024'
    # Bengali
    assert parse_multilingual_date('১ জানুয়ারি ২০২৪') == '01/01/2024'
    # Marathi
    assert parse_multilingual_date('१५ ऑगस्ट २०२३') == '15/08/2023'
    # Standard format
    assert parse_multilingual_date('01/2024') == '01/2024'

def test_full_text_normalization():
    raw = 'अधिकतम खुदरा मूल्य: रु. २५०.०० (सभी करों सहित), शुद्ध मात्रा: ५०० ग्राम'
    normalized = normalize_multilingual_text(raw)
    assert '250.00' in normalized
    assert '₹' in normalized
    assert '500 g' in normalized
