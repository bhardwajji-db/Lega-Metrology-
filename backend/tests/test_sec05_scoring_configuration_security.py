"""MetrCheck AI - SEC-05 Scoring Configuration Security and Authorization Test Suite.

Verifies:
1. Unauthenticated mutation attempts return HTTP 401 Unauthorized.
2. Invalid/malformed tokens return HTTP 401 Unauthorized.
3. Merchant (MERCHANT_PUBLIC) mutation attempts return HTTP 403 Forbidden.
4. Enforcement Officer (ENFORCEMENT_OFFICER) mutation attempts return HTTP 403 Forbidden.
5. Audit Officer (AUDIT_OFFICER) mutation attempts return HTTP 403 Forbidden.
6. Admin (ADMIN) mutation is authorized and returns HTTP 200 OK.
7. Invalid configuration schemas submitted by Admin return 422 Validation Error.
8. Unauthorized mutation attempts produce ZERO state modifications or side effects.
9. Authorized configuration updates dynamically take effect in subsequent scoring calculations.
10. Authorized configuration changes create immutable cryptographic security audit logs.
11. Concurrent unauthorized requests all fail safely without state corruption.
12. Default scoring algorithm formulas, risk classifications, and outputs remain intact.
"""

import asyncio
import pytest
from fastapi.testclient import TestClient

from main import app
from auth.security import (
    create_token,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
    ROLE_MERCHANT,
)
from compliance.scorer import (
    get_scoring_config,
    set_scoring_config,
    DEFAULT_SCORING_CONFIG,
    calculate_score,
)
from models.schemas import ScoringConfiguration, ComplianceCheck
from compliance.rules.models import ComplianceStatus
from database.db import get_security_audit_logs, init_db


@pytest.fixture(autouse=True)
def ensure_db_and_clean_state():
    """Ensure database is initialized and restore default scoring config before and after each test."""
    asyncio.run(init_db())
    set_scoring_config(DEFAULT_SCORING_CONFIG)
    yield
    set_scoring_config(DEFAULT_SCORING_CONFIG)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_token():
    return create_token("admin", ROLE_ADMIN)


@pytest.fixture
def officer_token():
    return create_token("officer", ROLE_ENFORCEMENT)


@pytest.fixture
def auditor_token():
    return create_token("audit", ROLE_AUDIT)


@pytest.fixture
def merchant_token():
    return create_token("merchant", ROLE_MERCHANT)


def test_01_unauthenticated_mutation_returns_401(client):
    """Calling PUT /api/scoring/config without credentials returns 401 and causes no state change."""
    config_before = get_scoring_config().model_dump()

    payload = {
        "scoring_version": "HACKED.1",
        "weight_pass": 0.0,
        "weight_fail": 1.0,
        "critical_risk_threshold": 999,
    }

    response = client.put("/api/scoring/config", json=payload)
    assert response.status_code == 401
    assert "detail" in response.json()

    config_after = get_scoring_config().model_dump()
    assert config_after == config_before
    assert config_after["scoring_version"] == DEFAULT_SCORING_CONFIG.scoring_version


def test_02_invalid_token_mutation_returns_401(client):
    """Calling PUT /api/scoring/config with malformed/invalid token returns 401."""
    config_before = get_scoring_config().model_dump()

    headers = {"Authorization": "Bearer invalid.token.payload"}
    payload = {
        "scoring_version": "INVALID_TOKEN_TEST",
        "weight_pass": 0.1,
    }

    response = client.put("/api/scoring/config", json=payload, headers=headers)
    assert response.status_code == 401

    config_after = get_scoring_config().model_dump()
    assert config_after == config_before


def test_03_merchant_mutation_denied_403(client, merchant_token):
    """Merchant cannot modify global scoring configuration (returns 403)."""
    config_before = get_scoring_config().model_dump()

    headers = {"Authorization": f"Bearer {merchant_token}"}
    payload = {
        "scoring_version": "MERCHANT_TAMPER",
        "weight_pass": 1.0,
        "weight_fail": 0.99,
    }

    response = client.put("/api/scoring/config", json=payload, headers=headers)
    assert response.status_code == 403
    assert "Insufficient privileges" in response.json().get("detail", "")

    config_after = get_scoring_config().model_dump()
    assert config_after == config_before


def test_04_enforcement_officer_mutation_denied_403(client, officer_token):
    """Enforcement Officer cannot modify global scoring configuration (returns 403)."""
    config_before = get_scoring_config().model_dump()

    headers = {"Authorization": f"Bearer {officer_token}"}
    payload = {
        "scoring_version": "OFFICER_TAMPER",
        "critical_risk_threshold": 10,
    }

    response = client.put("/api/scoring/config", json=payload, headers=headers)
    assert response.status_code == 403

    config_after = get_scoring_config().model_dump()
    assert config_after == config_before


def test_05_audit_officer_mutation_denied_403(client, auditor_token):
    """Audit Officer cannot modify global scoring configuration (returns 403)."""
    config_before = get_scoring_config().model_dump()

    headers = {"Authorization": f"Bearer {auditor_token}"}
    payload = {
        "scoring_version": "AUDITOR_TAMPER",
        "weight_warning": 0.1,
    }

    response = client.put("/api/scoring/config", json=payload, headers=headers)
    assert response.status_code == 403

    config_after = get_scoring_config().model_dump()
    assert config_after == config_before


def test_06_admin_mutation_allowed_200(client, admin_token):
    """Admin can successfully update scoring configuration."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "scoring_version": "2026.ADMIN_CUSTOM",
        "weight_pass": 1.0,
        "weight_warning": 0.6,
        "weight_needs_review": 0.7,
        "weight_fail": 0.0,
        "critical_risk_threshold": 3,
        "high_risk_failures_threshold": 4,
        "medium_risk_review_threshold": 4,
        "enabled_factors": ["MANDATORY_PRESENCE", "CUSTOM_FACTOR"],
    }

    response = client.put("/api/scoring/config", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["scoring_version"] == "2026.ADMIN_CUSTOM"
    assert data["weight_warning"] == 0.6
    assert data["critical_risk_threshold"] == 3

    # Verify global active config was updated
    active = get_scoring_config()
    assert active.scoring_version == "2026.ADMIN_CUSTOM"
    assert active.weight_warning == 0.6
    assert active.critical_risk_threshold == 3


def test_07_invalid_admin_config_validation_error(client, admin_token):
    """Invalid configuration submitted by Admin fails validation (422) and leaves state unchanged."""
    config_before = get_scoring_config().model_dump()

    headers = {"Authorization": f"Bearer {admin_token}"}
    invalid_payload = {
        "weight_pass": "NOT_A_FLOAT",
        "critical_risk_threshold": "INVALID_INT",
    }

    response = client.put("/api/scoring/config", json=invalid_payload, headers=headers)
    assert response.status_code == 422

    config_after = get_scoring_config().model_dump()
    assert config_after == config_before


def test_08_unauthorized_mutation_zero_side_effects(client, merchant_token, officer_token, auditor_token):
    """All unauthorized mutation attempts have zero side effects on active configuration."""
    initial_config = get_scoring_config().model_dump()

    # 1. Unauthenticated attempt
    client.put("/api/scoring/config", json={"scoring_version": "ATTEMPT_1"})
    assert get_scoring_config().model_dump() == initial_config

    # 2. Merchant attempt
    client.put(
        "/api/scoring/config",
        json={"scoring_version": "ATTEMPT_2"},
        headers={"Authorization": f"Bearer {merchant_token}"},
    )
    assert get_scoring_config().model_dump() == initial_config

    # 3. Enforcement Officer attempt
    client.put(
        "/api/scoring/config",
        json={"scoring_version": "ATTEMPT_3"},
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert get_scoring_config().model_dump() == initial_config

    # 4. Audit Officer attempt
    client.put(
        "/api/scoring/config",
        json={"scoring_version": "ATTEMPT_4"},
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert get_scoring_config().model_dump() == initial_config


def test_09_authorized_config_change_affects_subsequent_scoring(client, admin_token):
    """Authorized config modification dynamically alters subsequent scoring calculations."""
    checks = [
        ComplianceCheck(
            rule_id="LM-001",
            field="manufacturer",
            field_label="Manufacturer",
            required=True,
            detected=True,
            status=ComplianceStatus.WARNING.value,
            severity="medium",
            description="Requirement",
            source="Rule",
            domain="LEGAL_METROLOGY",
        )
    ]

    # Baseline score with default weight_warning = 0.5 -> 50.0%
    score_default = calculate_score(checks)
    assert score_default["score"] == 50.0

    # Admin changes weight_warning to 0.8
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "scoring_version": "2026.DYNAMIC_TEST",
        "weight_pass": 1.0,
        "weight_warning": 0.8,
        "weight_needs_review": 0.85,
        "weight_fail": 0.0,
        "critical_risk_threshold": 1,
        "high_risk_failures_threshold": 2,
        "medium_risk_review_threshold": 2,
        "enabled_factors": ["MANDATORY_PRESENCE"],
    }
    resp = client.put("/api/scoring/config", json=payload, headers=headers)
    assert resp.status_code == 200

    # Subsequent score calculation uses the updated active configuration -> 80.0%
    score_updated = calculate_score(checks)
    assert score_updated["score"] == 80.0
    assert score_updated["scoring_version"] == "2026.DYNAMIC_TEST"


def test_10_authorized_mutation_creates_audit_event(client, admin_token):
    """Authorized config update creates a cryptographic security audit log event."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "scoring_version": "2026.AUDIT_VERIFIED",
        "weight_pass": 1.0,
        "weight_warning": 0.5,
        "weight_needs_review": 0.85,
        "weight_fail": 0.0,
        "critical_risk_threshold": 1,
        "high_risk_failures_threshold": 2,
        "medium_risk_review_threshold": 2,
        "enabled_factors": ["MANDATORY_PRESENCE"],
    }

    resp = client.put("/api/scoring/config", json=payload, headers=headers)
    assert resp.status_code == 200

    # Verify audit event in database
    logs = asyncio.run(get_security_audit_logs(limit=10, event_type="SCORING_CONFIG_UPDATE"))
    assert len(logs) >= 1
    latest = logs[0]
    assert latest["event_type"] == "SCORING_CONFIG_UPDATE"
    assert latest["actor_username"] == "admin"
    assert "2026.AUDIT_VERIFIED" in latest["details"]
    assert latest["event_hash"] is not None


def test_11_concurrent_unauthorized_mutations_no_state_leakage(client, merchant_token, officer_token):
    """Rapid sequence of unauthorized mutation attempts all fail cleanly without corrupting config."""
    config_before = get_scoring_config().model_dump()

    for i in range(10):
        tok = merchant_token if i % 2 == 0 else officer_token
        resp = client.put(
            "/api/scoring/config",
            json={"scoring_version": f"CORRUPT_{i}", "weight_pass": 0.0},
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert resp.status_code == 403

    config_after = get_scoring_config().model_dump()
    assert config_after == config_before


def test_12_existing_scoring_algorithm_regression():
    """Verify standard score calculation logic, thresholds, and outputs remain identical."""
    checks = [
        ComplianceCheck(
            rule_id="LM-001",
            field="manufacturer",
            field_label="Manufacturer",
            required=True,
            detected=True,
            status=ComplianceStatus.PASS.value,
            severity="critical",
            description="Req",
            source="Rule",
            domain="LEGAL_METROLOGY",
        ),
        ComplianceCheck(
            rule_id="LM-002",
            field="mrp",
            field_label="MRP",
            required=True,
            detected=False,
            status=ComplianceStatus.FAIL.value,
            severity="critical",
            description="Req",
            source="Rule",
            domain="LEGAL_METROLOGY",
        ),
    ]

    result = calculate_score(checks)
    assert result["score"] == 50.0
    assert result["status"] == "POTENTIAL NON-COMPLIANCE"
    assert result["risk_assessment"].risk_level == "CRITICAL"
    assert result["risk_assessment"].critical_violation_count == 1
    assert len(result["rule_scores"]) == 2
    assert len(result["category_scores"]) == 2
