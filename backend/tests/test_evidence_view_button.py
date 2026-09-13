import pytest
from models.schemas import ProductInfo, ProductImageEvidence, OCRWord
from compliance.engine import engine

def test_evidence_items_multi_image_indexing():
    front_words = [
        OCRWord(text='High', confidence=96.0, bbox=[50, 100, 120, 130]),
        OCRWord(text='Protein', confidence=95.0, bbox=[125, 100, 200, 130]),
        OCRWord(text='Oats', confidence=98.0, bbox=[205, 100, 260, 130]),
    ]
    back_words = [
        OCRWord(text='Manufactured', confidence=92.0, bbox=[50, 200, 150, 220]),
        OCRWord(text='by', confidence=95.0, bbox=[155, 200, 175, 220]),
        OCRWord(text='Alpino', confidence=96.0, bbox=[50, 225, 100, 245]),
        OCRWord(text='Health', confidence=95.0, bbox=[105, 225, 150, 245]),
        OCRWord(text='Foods', confidence=94.0, bbox=[155, 225, 200, 245]),
        OCRWord(text='Net', confidence=95.0, bbox=[50, 300, 80, 320]),
        OCRWord(text='Weight:', confidence=94.0, bbox=[85, 300, 140, 320]),
        OCRWord(text='400', confidence=97.0, bbox=[145, 300, 175, 320]),
        OCRWord(text='g', confidence=96.0, bbox=[180, 300, 195, 320]),
        OCRWord(text='MRP:', confidence=90.0, bbox=[50, 400, 90, 420]),
        OCRWord(text='Rs.', confidence=88.0, bbox=[95, 400, 120, 420]),
        OCRWord(text='299', confidence=92.0, bbox=[125, 400, 160, 420]),
        OCRWord(text='Lic.No.:10716022000249', confidence=95.0, bbox=[50, 500, 250, 520]),
    ]

    images = [
        ProductImageEvidence(filename='front.jpg', image_url='/uploads/front.jpg', label='Front', ocr_text='High Protein Oats', words=front_words),
        ProductImageEvidence(filename='back.jpg', image_url='/uploads/back.jpg', label='Back', ocr_text='Manufactured by Alpino Net Weight: 400 g MRP: Rs. 299', words=back_words),
    ]

    prod_info = ProductInfo(
        product_name='High Protein Oats',
        brand='Alpino',
        manufacturer='Alpino Health Foods',
        net_quantity='400 g',
        mrp='Rs. 299',
        fssai_license='10716022000249',
        country_of_origin='India',
        extraction_mode='real'
    )

    result = engine.check(prod_info, ocr_text='High Protein Oats Manufactured by Alpino', images=images)
    checks = {c.rule_id: c for c in result['checks']}

    # LM-002 / FS-002 should localize to Front (image_index=0)
    assert checks['LM-002'].evidence[0].image_index == 0
    assert checks['LM-002'].evidence[0].image_label == 'Front'
    assert checks['LM-002'].bbox is not None

    # LM-001 / LM-003 / LM-004 / FS-001 should localize to Back (image_index=1)
    assert checks['LM-001'].evidence[0].image_index == 1
    assert checks['LM-001'].evidence[0].image_label == 'Back'
    assert checks['LM-001'].bbox is not None

    assert checks['LM-003'].evidence[0].image_index == 1
    assert checks['LM-003'].evidence[0].image_label == 'Back'
    assert checks['LM-003'].bbox is not None

def test_evidence_non_visual_and_derived_rules():
    prod_info = ProductInfo(
        product_name='High Protein Oats',
        brand='Alpino',
        manufacturer='Alpino Health Foods',
        net_quantity='400 g',
        mrp='Rs. 299',
        extraction_mode='real'
    )

    result = engine.check(prod_info, ocr_text='Alpino Oats', images=[])
    checks = {c.rule_id: c for c in result['checks']}

    # LM-009 is a derived cross-field check
    assert checks['LM-009'].bbox is None
    assert checks['LM-009'].evidence[0].evidence_type == 'DERIVED_FIELD'
    assert checks['LM-009'].evidence[0].geometry_type == 'NONE'

    # LM-008 is delegated under food proviso
    assert checks['LM-008'].status == 'NOT_APPLICABLE'
    assert checks['LM-008'].bbox is None
    assert checks['LM-008'].evidence[0].evidence_type == 'PROVISO_DELEGATION'
