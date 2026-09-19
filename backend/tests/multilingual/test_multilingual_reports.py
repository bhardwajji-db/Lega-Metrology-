import pytest
from services.report_service import generate_pdf_report
from models.schemas import (
    AnalysisResponse, ComplianceResult, ComplianceCheck,
    ProductInfo, MultilingualMetadata, MultilingualLanguageInfo,
    OCRResult, OCRWord
)

def create_sample_analysis():
    return AnalysisResponse(
        id='test-multilingual-report-01',
        product_name='हिमालय आयुर्वेदिक च्यवनप्राश (Himalaya Chyawanprash)',
        image_url='/test.png',
        created_at='2026-09-16T12:00:00',
        ocr_result=OCRResult(
            full_text='हिमालय आयुर्वेदिक च्यवनप्राश ₹350.00 500 g',
            words=[],
            language='hi',
            processing_time=0.1
        ),
        product_info=ProductInfo(
            product_name='हिमालय आयुर्वेदिक च्यवनप्राश',
            brand='Himalaya Herbals',
            mrp='₹350.00',
            net_quantity='500 g',
            manufacturer_name='The Himalaya Drug Company, Makali, Bengaluru - 562162',
            mfg_date='2024-01-15',
            exp_date='2026-01-14',
            consumer_care='care@himalayawellness.com | 1800-208-1930',
            fssai_license='10012043000045',
        ),
        compliance_result=ComplianceResult(
            score=95.0,
            status='COMPLIANT',
            passed_rules=12,
            failed_rules=0,
            needs_review_rules=1,
            not_applicable_rules=0,
            total_rules=13,
            checks=[
                ComplianceCheck(
                    rule_id='LM-001',
                    field='mrp',
                    field_label='Maximum Retail Price (MRP)',
                    status='PASS',
                    detected_value='₹350.00',
                    explanation='Statutory MRP declaration is clearly present on Principal Display Panel.',
                ),
                ComplianceCheck(
                    rule_id='LM-002',
                    field='net_quantity',
                    field_label='Net Quantity',
                    status='PASS',
                    detected_value='500 g',
                    explanation='Net quantity compliant with Legal Metrology standard units.',
                ),
            ],
            issues=[],
        ),
        multilingual=MultilingualMetadata(
            primary_language='hi',
            detected_languages=[
                MultilingualLanguageInfo(code='hi', name='Hindi', native_name='हिन्दी', script='Devanagari', token_count=45, confidence=0.95),
                MultilingualLanguageInfo(code='en', name='English', native_name='English', script='Latin', token_count=30, confidence=0.98),
            ],
            detected_scripts=['Devanagari', 'Latin'],
            is_multilingual=True,
            total_tokens=75,
        ),
    )

def test_generate_pdf_report_all_10_languages():
    analysis = create_sample_analysis()
    languages = ['en', 'hi', 'mr', 'bn', 'gu', 'pa', 'ta', 'te', 'kn', 'ml']
    
    for lang in languages:
        pdf_bytes = generate_pdf_report(analysis, language=lang)
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 1000
        assert pdf_bytes.startswith(b'%PDF')
