import json
import re
from pathlib import Path
import pytest

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent.parent / 'frontend'
LOCALES_DIR = FRONTEND_DIR / 'src' / 'i18n' / 'locales'
SRC_DIR = FRONTEND_DIR / 'src'

SUPPORTED_LANGUAGES = ['en', 'hi', 'mr', 'bn', 'gu', 'pa', 'ta', 'te', 'kn', 'ml']

SCRIPT_RANGES = {
    'hi': (0x0900, 0x097F, 'Devanagari'),
    'mr': (0x0900, 0x097F, 'Devanagari'),
    'bn': (0x0980, 0x09FF, 'Bengali'),
    'gu': (0x0A80, 0x0AFF, 'Gujarati'),
    'pa': (0x0A00, 0x0A7F, 'Gurmukhi'),
    'ta': (0x0B80, 0x0BFF, 'Tamil'),
    'te': (0x0C00, 0x0C7F, 'Telugu'),
    'kn': (0x0C80, 0x0CFF, 'Kannada'),
    'ml': (0x0D00, 0x0D7F, 'Malayalam'),
}

def load_locale(lang: str) -> dict:
    file_path = LOCALES_DIR / f'{lang}.json'
    assert file_path.exists(), f'Locale file missing for {lang}: {file_path}'
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def flatten_keys(d: dict, prefix: str = '') -> set:
    keys = set()
    for k, v in d.items():
        curr_key = f'{prefix}.{k}' if prefix else k
        if isinstance(v, dict):
            keys.update(flatten_keys(v, curr_key))
        else:
            keys.add(curr_key)
    return keys

def to_camel_case(s: str) -> str:
    parts = s.split('_')
    return parts[0] + ''.join(word.capitalize() for word in parts[1:])

def to_snake_case(s: str) -> str:
    return re.sub(r'([A-Z])', r'_\1', s).lower()

def resolve_key(data: dict, key_path: str):
    parts = key_path.split('.')
    current = data
    for part in parts:
        if not isinstance(current, dict):
            return None
        if part in current:
            current = current[part]
        elif to_camel_case(part) in current:
            current = current[to_camel_case(part)]
        elif to_snake_case(part) in current:
            current = current[to_snake_case(part)]
        elif part.upper() in current:
            current = current[part.upper()]
        elif part.lower() in current:
            current = current[part.lower()]
        else:
            return None
    return current if isinstance(current, str) else None

def test_all_locales_exist():
    for lang in SUPPORTED_LANGUAGES:
        file_path = LOCALES_DIR / f'{lang}.json'
        assert file_path.exists(), f'Locale file missing: {file_path}'

def test_locales_valid_json_and_non_empty():
    for lang in SUPPORTED_LANGUAGES:
        data = load_locale(lang)
        assert isinstance(data, dict), f'Locale {lang} must be a dictionary'
        assert len(data) > 0, f'Locale {lang} must not be empty'

def test_key_symmetry_with_english():
    en_data = load_locale('en')
    en_keys = flatten_keys(en_data)
    assert len(en_keys) > 0, 'English locale should have keys'

    for lang in SUPPORTED_LANGUAGES:
        if lang == 'en':
            continue
        target_data = load_locale(lang)
        for key in en_keys:
            val = resolve_key(target_data, key)
            assert val is not None and len(val.strip()) > 0, (
                f'Missing or empty translation for key {key} in locale {lang}'
            )

def test_no_question_mark_corruption():
    for lang in SUPPORTED_LANGUAGES:
        file_path = LOCALES_DIR / f'{lang}.json'
        raw_text = file_path.read_text(encoding='utf-8')
        # Check no suspicious repeated question mark patterns
        assert not re.search(r'\?{2,}', raw_text), f'Locale {lang} contains suspicious question mark corruption'
        if lang != 'en':
            assert raw_text.count('?') == 0, f'Non-English locale {lang} should have 0 question marks'

def test_locales_unicode_scripts_present():
    for lang, (start, end, script_name) in SCRIPT_RANGES.items():
        file_path = LOCALES_DIR / f'{lang}.json'
        raw_text = file_path.read_text(encoding='utf-8')
        script_chars = [c for c in raw_text if start <= ord(c) <= end]
        assert len(script_chars) > 1000, (
            f'Locale {lang} should contain authentic {script_name} characters, found {len(script_chars)}'
        )

def test_all_component_keys_resolve_in_all_languages():
    key_pattern = re.compile(r"""\b(?:t|translate)\(\s*['"]([a-zA-Z0-9_.]+)['"]""")
    used_keys = set()

    for file_path in SRC_DIR.rglob('*.[t|j]s*'):
        if 'i18n' in file_path.parts:
            continue
        try:
            content = file_path.read_text(encoding='utf-8')
            for match in key_pattern.finditer(content):
                used_keys.add(match.group(1))
        except Exception:
            pass

    assert len(used_keys) > 0, 'Should detect t() keys in frontend source files'

    for lang in SUPPORTED_LANGUAGES:
        data = load_locale(lang)
        for key in used_keys:
            val = resolve_key(data, key)
            assert val is not None, (
                f'Frontend key {key} failed to resolve in locale {lang}'
            )

def test_all_locales_have_critical_dashboard_and_nav_keys():
    critical_keys = [
        'dashboard.greeting_morning',
        'dashboard.greeting_afternoon',
        'dashboard.greeting_evening',
        'dashboard.overview_subtitle',
        'dashboard.stats.packages_screened',
        'dashboard.stats.compliant_packages',
        'dashboard.stats.review_findings',
        'dashboard.stats.failed_findings',
        'dashboard.stats.finding_info',
        'dashboard.action_required_discrepancies',
        'dashboard.steps.capture',
        'dashboard.steps.extract',
        'dashboard.steps.screen',
        'dashboard.steps.verify',
        'dashboard.steps.report',
        'dashboard.table.product',
        'dashboard.table.score',
        'dashboard.table.status',
        'dashboard.table.date',
        'dashboard.table.action',
        'navigation.system_operational',
        'navigation.dashboard',
        'navigation.analyze_package',
        'navigation.screening_history',
        'navigation.compliance_rules',
    ]
    for lang in SUPPORTED_LANGUAGES:
        data = load_locale(lang)
        for key in critical_keys:
            val = resolve_key(data, key)
            assert val is not None and len(val.strip()) > 0, (
                f'Critical key {key} missing in {lang}'
            )

def test_parameter_interpolation():
    for lang in SUPPORTED_LANGUAGES:
        data = load_locale(lang)
        template = resolve_key(data, 'dashboard.manualVerification')
        assert template is not None
        assert '{count}' in template, f'manualVerification in {lang} should contain {{count}}'
