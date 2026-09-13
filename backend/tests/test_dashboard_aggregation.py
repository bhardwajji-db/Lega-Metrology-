import pytest
import json
import uuid
import os
from database.db import classify_analysis_outcome, get_stats, save_analysis, delete_all_user_analyses, create_user, get_user_by_username
from models.schemas import ComplianceCheck, ComplianceResult
from auth.security import create_token, ROLE_MERCHANT, ROLE_ADMIN

def test_1_fail_with_review_and_pass():
    # 8 PASS + 3 REVIEW + 1 FAIL + 2 N/A
    checks = [
        {'status': 'PASS'} for _ in range(8)
    ] + [
        {'status': 'NEEDS_REVIEW'} for _ in range(3)
    ] + [
        {'status': 'FAIL'}
    ] + [
        {'status': 'NOT_APPLICABLE'} for _ in range(2)
    ]
    analysis = {
        'id': 'test-1',
        'score': 87.9,
        'status': 'POTENTIAL NON-COMPLIANCE',
        'compliance_result': {
            'checks': checks,
            'passed_rules': 8,
            'needs_review_rules': 3,
            'failed_rules': 1,
            'not_applicable_rules': 2,
            'status': 'POTENTIAL NON-COMPLIANCE'
        }
    }
    outcome = classify_analysis_outcome(analysis)
    assert outcome == 'FAILURE'

def test_2_review_with_pass_zero_fail():
    # 8 PASS + 3 REVIEW + 0 FAIL + 2 N/A
    checks = [
        {'status': 'PASS'} for _ in range(8)
    ] + [
        {'status': 'NEEDS_REVIEW'} for _ in range(3)
    ] + [
        {'status': 'NOT_APPLICABLE'} for _ in range(2)
    ]
    analysis = {
        'id': 'test-2',
        'score': 95.0,
        'status': 'REVIEW REQUIRED',
        'compliance_result': {
            'checks': checks,
            'passed_rules': 8,
            'needs_review_rules': 3,
            'failed_rules': 0,
            'not_applicable_rules': 2,
            'status': 'REVIEW REQUIRED'
        }
    }
    outcome = classify_analysis_outcome(analysis)
    assert outcome == 'NEEDS_REVIEW'

def test_3_all_pass_zero_fail_zero_review():
    # 10 PASS + 0 REVIEW + 0 FAIL
    checks = [{'status': 'PASS'} for _ in range(10)]
    analysis = {
        'id': 'test-3',
        'score': 100.0,
        'status': 'COMPLIANT',
        'compliance_result': {
            'checks': checks,
            'passed_rules': 10,
            'needs_review_rules': 0,
            'failed_rules': 0,
            'status': 'COMPLIANT'
        }
    }
    outcome = classify_analysis_outcome(analysis)
    assert outcome == 'COMPLIANT'

def test_4_multiple_analyses_aggregate():
    analyses = [
        # Analysis A: PASS only
        {
            'id': 'a',
            'score': 100.0,
            'status': 'COMPLIANT',
            'compliance_result': {
                'checks': [{'status': 'PASS'} for _ in range(5)],
                'failed_rules': 0,
                'needs_review_rules': 0,
                'passed_rules': 5
            }
        },
        # Analysis B: REVIEW only
        {
            'id': 'b',
            'score': 85.0,
            'status': 'REVIEW REQUIRED',
            'compliance_result': {
                'checks': [{'status': 'NEEDS_REVIEW'} for _ in range(2)],
                'failed_rules': 0,
                'needs_review_rules': 2,
                'passed_rules': 0
            }
        },
        # Analysis C: FAIL + REVIEW
        {
            'id': 'c',
            'score': 60.0,
            'status': 'POTENTIAL NON-COMPLIANCE',
            'compliance_result': {
                'checks': [{'status': 'FAIL'}, {'status': 'NEEDS_REVIEW'}],
                'failed_rules': 1,
                'needs_review_rules': 1,
                'passed_rules': 0
            }
        }
    ]
    
    outcomes = [classify_analysis_outcome(a) for a in analyses]
    assert outcomes == ['COMPLIANT', 'NEEDS_REVIEW', 'FAILURE']
    
    compliant_count = sum(1 for o in outcomes if o == 'COMPLIANT')
    needs_review_count = sum(1 for o in outcomes if o == 'NEEDS_REVIEW')
    failures_count = sum(1 for o in outcomes if o == 'FAILURE')
    
    assert len(analyses) == 3
    assert compliant_count == 1
    assert needs_review_count == 1
    assert failures_count == 1

def test_5_high_score_with_confirmed_fail():
    # Score 93.3 with 1 confirmed FAIL must still be classified as FAILURE
    checks = [{'status': 'PASS'} for _ in range(14)] + [{'status': 'FAIL'}]
    analysis = {
        'id': 'test-5',
        'score': 93.3,
        'status': 'POTENTIAL NON-COMPLIANCE',
        'compliance_result': {
            'checks': checks,
            'failed_rules': 1,
            'passed_rules': 14,
            'needs_review_rules': 0
        }
    }
    outcome = classify_analysis_outcome(analysis)
    assert outcome == 'FAILURE'

def test_6_zero_fail_with_review_findings():
    # Even if status string has POTENTIAL NON-COMPLIANCE, if underlying checks say 0 FAIL and 2 REVIEW,
    # the rule results must govern (NEEDS_REVIEW)
    checks = [{'status': 'PASS'} for _ in range(8)] + [{'status': 'NEEDS_REVIEW'} for _ in range(2)]
    analysis = {
        'id': 'test-6',
        'score': 85.0,
        'status': 'POTENTIAL NON-COMPLIANCE',
        'compliance_result': {
            'checks': checks,
            'failed_rules': 0,
            'needs_review_rules': 2,
            'passed_rules': 8
        }
    }
    outcome = classify_analysis_outcome(analysis)
    assert outcome == 'NEEDS_REVIEW'

@pytest.mark.asyncio
async def test_7_get_stats_merchant_filtering_and_counts(client=None):
    from database.db import delete_all_user_analyses, save_analysis
    from main import app
    from fastapi.testclient import TestClient
    
    test_client = TestClient(app)
    
    # Clean up test user analyses
    await delete_all_user_analyses()
    
    # Save 1 fail analysis owned by merchant1
    fail_analysis = {
        'id': str(uuid.uuid4()),
        'product_name': 'High Protein Oats',
        'image_filename': 'oats.png',
        'ocr_text': 'test',
        'extracted_data': {},
        'compliance_result': {
            'checks': [{'status': 'PASS'} for _ in range(8)] + [{'status': 'NEEDS_REVIEW'} for _ in range(3)] + [{'status': 'FAIL'}],
            'passed_rules': 8,
            'needs_review_rules': 3,
            'failed_rules': 1,
            'not_applicable_rules': 2,
            'score': 87.9,
            'status': 'POTENTIAL NON-COMPLIANCE'
        },
        'score': 87.9,
        'status': 'POTENTIAL NON-COMPLIANCE',
        'created_at': '2026-09-13T12:00:00Z',
        'images': [],
        'owner_user_id': 'merchant_test_user'
    }
    await save_analysis(fail_analysis)
    
    # Save 1 compliant analysis owned by merchant2
    other_analysis = {
        'id': str(uuid.uuid4()),
        'product_name': 'Other Product',
        'image_filename': 'other.png',
        'ocr_text': 'test',
        'extracted_data': {},
        'compliance_result': {
            'checks': [{'status': 'PASS'} for _ in range(10)],
            'passed_rules': 10,
            'needs_review_rules': 0,
            'failed_rules': 0,
            'score': 100.0,
            'status': 'COMPLIANT'
        },
        'score': 100.0,
        'status': 'COMPLIANT',
        'created_at': '2026-09-13T12:05:00Z',
        'images': [],
        'owner_user_id': 'other_merchant'
    }
    await save_analysis(other_analysis)
    
    # Merchant 1 requests stats:
    merchant_user = {'username': 'merchant_test_user', 'role': ROLE_MERCHANT, 'id': 99}
    stats = await get_stats(user=merchant_user)
    
    assert stats['total_analyzed'] == 1
    assert stats['packages_screened'] == 1
    assert stats['compliant'] == 0
    assert stats['compliant_packages'] == 0
    assert stats['needs_review'] == 3
    assert stats['review_findings'] == 3
    assert stats['failures'] == 1
    assert stats['failed_findings'] == 1

    # Test GET /api/stats endpoint via FastAPI TestClient
    from auth.security import create_token, hash_password
    from database.db import create_user
    pwh, salt = hash_password("pass123")
    await create_user("merchant_test_user", pwh, salt, ROLE_MERCHANT, "Merchant Tester")
    token = create_token('merchant_test_user', ROLE_MERCHANT)
    resp = test_client.get('/api/stats', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['packages_screened'] == 1
    assert data['compliant_packages'] == 0
    assert data['review_findings'] == 3
    assert data['failed_findings'] == 1
    
    # Clean up test analyses
    await delete_all_user_analyses()


@pytest.mark.asyncio
async def test_8_dashboard_finding_kpis_edge_cases():
    """Verify edge cases: fully compliant, review-only, multiple failures, and multiple packages."""
    from database.db import delete_all_user_analyses, save_analysis
    
    await delete_all_user_analyses()

    # Case A: Fully compliant (10 PASS)
    pkg_comp = {
        'id': 'edge-comp-1',
        'product_name': 'Pure Honey',
        'image_filename': '',
        'ocr_text': '',
        'extracted_data': {},
        'compliance_result': {
            'checks': [{'status': 'PASS'} for _ in range(10)],
            'passed_rules': 10,
            'needs_review_rules': 0,
            'failed_rules': 0,
            'status': 'COMPLIANT'
        },
        'score': 100.0,
        'status': 'COMPLIANT',
        'created_at': '2026-09-13T10:00:00Z',
        'images': [],
        'owner_user_id': 'merchant_edge'
    }
    await save_analysis(pkg_comp)

    stats_a = await get_stats(user={'username': 'merchant_edge', 'role': ROLE_MERCHANT})
    assert stats_a['packages_screened'] == 1
    assert stats_a['compliant_packages'] == 1
    assert stats_a['review_findings'] == 0
    assert stats_a['failed_findings'] == 0

    # Case B: Add a review-only package (8 PASS, 4 REVIEW, 0 FAIL)
    pkg_rev = {
        'id': 'edge-rev-1',
        'product_name': 'Herbal Tea',
        'image_filename': '',
        'ocr_text': '',
        'extracted_data': {},
        'compliance_result': {
            'checks': [{'status': 'PASS'} for _ in range(8)] + [{'status': 'NEEDS_REVIEW'} for _ in range(4)],
            'passed_rules': 8,
            'needs_review_rules': 4,
            'failed_rules': 0,
            'status': 'REVIEW REQUIRED'
        },
        'score': 92.0,
        'status': 'REVIEW REQUIRED',
        'created_at': '2026-09-13T11:00:00Z',
        'images': [],
        'owner_user_id': 'merchant_edge'
    }
    await save_analysis(pkg_rev)

    stats_b = await get_stats(user={'username': 'merchant_edge', 'role': ROLE_MERCHANT})
    assert stats_b['packages_screened'] == 2
    assert stats_b['compliant_packages'] == 1
    assert stats_b['review_findings'] == 4
    assert stats_b['failed_findings'] == 0

    # Case C: Add a multi-failure package (5 PASS, 2 REVIEW, 3 FAIL, 2 NOT_APPLICABLE)
    pkg_fail = {
        'id': 'edge-fail-1',
        'product_name': 'Spicy Chips',
        'image_filename': '',
        'ocr_text': '',
        'extracted_data': {},
        'compliance_result': {
            'checks': (
                [{'status': 'PASS'} for _ in range(5)] +
                [{'status': 'NEEDS_REVIEW'} for _ in range(2)] +
                [{'status': 'FAIL'} for _ in range(3)] +
                [{'status': 'NOT_APPLICABLE'} for _ in range(2)]
            ),
            'passed_rules': 5,
            'needs_review_rules': 2,
            'failed_rules': 3,
            'not_applicable_rules': 2,
            'status': 'POTENTIAL NON-COMPLIANCE'
        },
        'score': 55.0,
        'status': 'POTENTIAL NON-COMPLIANCE',
        'created_at': '2026-09-13T12:00:00Z',
        'images': [],
        'owner_user_id': 'merchant_edge'
    }
    await save_analysis(pkg_fail)

    stats_c = await get_stats(user={'username': 'merchant_edge', 'role': ROLE_MERCHANT})
    assert stats_c['packages_screened'] == 3
    assert stats_c['compliant_packages'] == 1
    assert stats_c['review_findings'] == 6   # 0 + 4 + 2
    assert stats_c['failed_findings'] == 3   # 0 + 0 + 3

    await delete_all_user_analyses()
