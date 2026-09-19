import pytest
from multilingual.registry import (
    SUPPORTED_LANGUAGES,
    SCRIPT_UNICODE_RANGES,
    SCRIPT_TO_LANGUAGES,
    SCRIPT_NUMERALS,
    is_supported_language,
    get_language_name,
    get_native_name,
    get_paddle_lang_code,
    get_numeral_map,
)

def test_supported_languages_contains_10_target_languages():
    expected_codes = {'en', 'hi', 'mr', 'bn', 'gu', 'pa', 'ta', 'te', 'kn', 'ml'}
    assert set(SUPPORTED_LANGUAGES.keys()) == expected_codes
    assert len(SUPPORTED_LANGUAGES) == 10

def test_language_metadata_completeness():
    for code, meta in SUPPORTED_LANGUAGES.items():
        assert meta["code"] == code
        assert meta["name"] != ''
        assert meta["native_name"] != ''
        assert meta["script"] != ''
        assert meta["paddle_lang"] != ''

def test_is_supported_language_helper():
    assert is_supported_language('en') is True
    assert is_supported_language('HI') is True
    assert is_supported_language('mr') is True
    assert is_supported_language('ta') is True
    assert is_supported_language('fr') is False
    assert is_supported_language('de') is False

def test_get_language_name_and_native_name():
    assert get_language_name('hi') == 'Hindi'
    assert get_native_name('hi') == 'हिन्दी'
    assert get_language_name('ta') == 'Tamil'
    assert get_native_name('ta') == 'தமிழ்'
    assert get_language_name('bn') == 'Bengali'
    assert get_native_name('bn') == 'বাংলা'
    assert get_language_name('mr') == 'Marathi'
    assert get_native_name('mr') == 'मराठी'

def test_paddle_language_code_mapping():
    assert get_paddle_lang_code('hi') == 'devanagari'
    assert get_paddle_lang_code('mr') == 'devanagari'
    assert get_paddle_lang_code('ta') == 'ta'
    assert get_paddle_lang_code('te') == 'te'
    assert get_paddle_lang_code('kn') == 'ka'
    assert get_paddle_lang_code('en') == 'en'

def test_script_numerals_coverage():
    assert 'Devanagari' in SCRIPT_NUMERALS
    assert 'Bengali' in SCRIPT_NUMERALS
    assert 'Gujarati' in SCRIPT_NUMERALS
    assert 'Gurmukhi' in SCRIPT_NUMERALS
    assert 'Tamil' in SCRIPT_NUMERALS
    assert 'Telugu' in SCRIPT_NUMERALS
    assert 'Kannada' in SCRIPT_NUMERALS
    assert 'Malayalam' in SCRIPT_NUMERALS
    assert get_numeral_map('Devanagari')['२'] == '2'
