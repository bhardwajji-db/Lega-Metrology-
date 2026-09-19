import pytest
from multilingual.extractor import MultilingualExtractor
from extraction.extractor import LocalExtractor
from models.schemas import OCRResult, OCRWord

def test_extract_mrp_multilingual_indic():
    extractor = MultilingualExtractor()
    
    # Hindi MRP
    hindi_text = 'अधिकतम खुदरा मूल्य: ₹२५०.०० (सभी करों सहित)'
    res_hi = extractor.extract_from_text(hindi_text)
    assert res_hi.get('mrp') == '₹250.00'
    assert 'mrp' in res_hi.get('_provenance', {})
    assert res_hi['_provenance']['mrp'].language in ['hi', 'en']
    assert res_hi['_provenance']['mrp'].script == 'Devanagari'

    # Tamil MRP
    tamil_text = 'அதிகபட்ச சில்லறை விலை: ரூ. 199.00 (அனைத்து வரிகளும் உட்பட)'
    res_ta = extractor.extract_from_text(tamil_text)
    assert res_ta.get('mrp') == '₹199.00'
    assert res_ta['_provenance']['mrp'].script == 'Tamil'

    # Bengali MRP
    bengali_text = 'সর্বোচ্চ খুচরা মূল্য: টাকা ৫০০.০০'
    res_bn = extractor.extract_from_text(bengali_text)
    assert res_bn.get('mrp') == '₹500.00'
    assert res_bn['_provenance']['mrp'].script == 'Bengali'

def test_extract_net_quantity_multilingual():
    extractor = MultilingualExtractor()

    # Marathi
    mr_text = 'निव्वळ वजन: २५० ग्रॅम'
    res_mr = extractor.extract_from_text(mr_text)
    assert res_mr.get('net_quantity') == '250 g'
    assert res_mr['_provenance']['net_quantity'].script == 'Devanagari'

    # Gujarati
    gu_text = 'ચોખ્ખું વજન: ૧ કિગ્રા'
    res_gu = extractor.extract_from_text(gu_text)
    assert res_gu.get('net_quantity') == '1 kg'
    assert res_gu['_provenance']['net_quantity'].script == 'Gujarati'

    # Telugu
    te_text = 'నికర పరిమాణం: 500 గ్రా'
    res_te = extractor.extract_from_text(te_text)
    assert res_te.get('net_quantity') == '500 g'
    assert res_te['_provenance']['net_quantity'].script == 'Telugu'

    # Kannada
    kn_text = 'ನಿವ್ವಳ ತೂಕ: ೫೦೦ ಗ್ರಾಂ'
    res_kn = extractor.extract_from_text(kn_text)
    assert res_kn.get('net_quantity') == '500 g'
    assert res_kn['_provenance']['net_quantity'].script == 'Kannada'

    # Malayalam
    ml_text = 'അറ്റ അളവ്: 500 ഗ്രാം'
    res_ml = extractor.extract_from_text(ml_text)
    assert res_ml.get('net_quantity') == '500 g'
    assert res_ml['_provenance']['net_quantity'].script == 'Malayalam'

    # Punjabi
    pa_text = 'ਨੈੱਟ ਵਜ਼ਨ: 500 ਗ੍ਰਾਮ'
    res_pa = extractor.extract_from_text(pa_text)
    assert res_pa.get('net_quantity') == '500 g'
    assert res_pa['_provenance']['net_quantity'].script == 'Gurmukhi'

def test_extract_dates_fssai_consumer_care_indic():
    extractor = MultilingualExtractor()
    full_pkg = (
        'निर्माता: सनराइज फूड्स प्रा. लि., मुंबई, महाराष्ट्र\n'
        'निर्माण तिथि: १५ जनवरी २०२४\n'
        'उपयोग की अंतिम तिथि: १४ जनवरी २०२५\n'
        'एफएसएसएआई लाइसेंस: 10012011000123\n'
        'उपभोक्ता सेवा: care@sunrisefoods.in | १८००-१२३-४५६७\n'
        'सामग्री: गेहूं का आटा, चीनी, खाद्य वनस्पति तेल\n'
        'पोषण संबंधी जानकारी: ऊर्जा 450 किलोकैलोरी, प्रोटीन 7 ग्राम\n'
        'एलर्जी चेतावनी: ग्लूटेन शामिल है\n'
    )
    res = extractor.extract_from_text(full_pkg)
    assert res.get('mfg_date') == '15/01/2024'
    assert res.get('exp_date') == '14/01/2025'
    assert res.get('fssai_license') == '10012011000123'
    assert 'care@sunrisefoods.in' in str(res.get('consumer_care'))
    assert 'गेहूं का आटा' in str(res.get('ingredients'))
    assert 'मुंबई' in str(res.get('manufacturer_address') or res.get('manufacturer_name'))

def test_local_extractor_with_multilingual_tokens():
    ocr_result = OCRResult(
        language='hi',
        processing_time=0.1,
        full_text=(
            'निर्माता: हिमालया हर्बल्स, देहराडून\n'
            'अधिकतम खुदरा मूल्य: ₹९९.०० (सभी करों सहित)\n'
            'शुद्ध मात्रा: 100 g\n'
            'निर्माण तिथि: 01/2024\n'
        ),
        words=[
            OCRWord(text='अधिकतम', confidence=95.0, bbox=[10, 10, 50, 25], script='Devanagari', language='hi'),
            OCRWord(text='खुदरा', confidence=95.0, bbox=[55, 10, 95, 25], script='Devanagari', language='hi'),
            OCRWord(text='मूल्य:', confidence=95.0, bbox=[100, 10, 140, 25], script='Devanagari', language='hi'),
            OCRWord(text='₹९९.००', confidence=96.0, bbox=[145, 10, 195, 25], script='Devanagari', language='hi'),
            OCRWord(text='शुद्ध', confidence=94.0, bbox=[10, 30, 45, 45], script='Devanagari', language='hi'),
            OCRWord(text='मात्रा:', confidence=94.0, bbox=[50, 30, 90, 45], script='Devanagari', language='hi'),
            OCRWord(text='100', confidence=98.0, bbox=[95, 30, 120, 45], script='Latin', language='en'),
            OCRWord(text='g', confidence=98.0, bbox=[125, 30, 135, 45], script='Latin', language='en'),
        ]
    )
    extractor = LocalExtractor()
    info = extractor.extract(ocr_result)
    assert info.mrp is not None
    assert '99' in info.mrp
    assert info.field_provenance.get('mrp') is not None
    assert info.field_provenance['mrp'].script == 'Devanagari'
