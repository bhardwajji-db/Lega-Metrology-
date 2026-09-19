import pytest
from models.schemas import AnalysisResponse, OCRWord, OCRResult, FieldProvenance, EvidenceItem, ProductInfo

def test_schemas_backward_compatibility():
    # Verify existing OCRWord instantiation without multilingual kwargs works
    word = OCRWord(text='100g', confidence=98.0, bbox=[0, 0, 10, 10])
    assert word.script is None
    assert word.language is None

    # Verify FieldProvenance backward compatibility
    prov = FieldProvenance(
        field_name='mrp',
        raw_value='₹100',
        confidence=95.0,
        source_bbox=[0, 0, 10, 10],
        match_method='DIRECT_OCR',
    )
    assert prov.language is None
    assert prov.script is None

    # Verify ProductInfo backward compatibility
    info = ProductInfo(mrp='₹100', net_quantity='100 g')
    assert info.mrp == '₹100'

    # Verify EvidenceItem backward compatibility
    ev = EvidenceItem(
        rule_id='LM-001',
        field_type='mrp',
        matched_text='₹100',
        confidence=95.0,
        bbox=[0, 0, 10, 10],
    )
    assert ev.language is None
    assert ev.script is None
