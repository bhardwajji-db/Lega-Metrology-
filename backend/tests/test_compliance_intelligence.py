import pytest
from datetime import datetime
from models.schemas import ProductInfo, ComplianceCheck, RuleTestRequest
from compliance.rules.registry import registry
from compliance.rules.models import RuleCategory, RuleDomain, ComplianceStatus
from compliance.rules.applicability import PackageContext
from compliance.engine import ComplianceEngine, engine


def test_rule_registry_contains_all_14_rules():
    rules = registry.get_all_rules()
    assert len(rules) == 14
    lm_rules = [r for r in rules if r.id.startswith("LM-")]
    fs_rules = [r for r in rules if r.id.startswith("FS-")]
    assert len(lm_rules) == 9
    assert len(fs_rules) == 5


def test_rule_metadata_versioning_and_effective_dates():
    for r in registry.get_all_rules():
        assert r.rule_version is not None
        assert len(r.rule_version) > 0
        assert r.effective_from is not None
        # Verify date format YYYY-MM-DD
        datetime.strptime(r.effective_from, "%Y-%m-%d")
        assert isinstance(r.category_applicability, list)
        assert len(r.category_applicability) > 0
        assert len(r.conditions) > 0
        assert len(r.evidence_fields) > 0


def test_registry_category_filtering():
    # Food category has 13 rules (8 universal LM rules + 5 FSSAI rules, since LM-008 delegates to FS-005)
    food_rules = registry.get_rules_by_category("FOOD")
    assert len(food_rules) == 13
    
    non_food_rules = registry.get_rules_by_category("NON_FOOD")
    # Non-food category should include ALL 9 LM rules but NOT FS-specific rules
    fs_in_non_food = [r for r in non_food_rules if r.domain == RuleDomain.FSSAI]
    assert len(fs_in_non_food) == 0
    assert len(non_food_rules) == 9

    all_rules = registry.get_rules_by_category("ALL")
    assert len(all_rules) == 14


def test_package_context_inference():
    # Test food context inference
    food_info = ProductInfo(
        product_name="Britannia Good Day Biscuits",
        ingredients="Wheat Flour, Sugar, Butter",
        fssai_license="10014011000123"
    )
    ctx = PackageContext.infer_context(food_info)
    assert ctx["is_food"] is True
    assert ctx["category"] == "FOOD"
    assert ctx["is_imported"] is False

    # Test imported non-food context inference
    imported_info = ProductInfo(
        product_name="Phillips Electric Shaver",
        country_of_origin="Netherlands",
        importer_name="Philips India Ltd"
    )
    ctx_imp = PackageContext.infer_context(imported_info)
    assert ctx_imp["is_food"] is False
    assert ctx_imp["is_imported"] is True
    assert ctx_imp["category"] == "NON_FOOD"


def test_compliance_engine_execution_trace_generation():
    eng = ComplianceEngine()
    info = ProductInfo(
        manufacturer="Tata Consumer Products Ltd, Mumbai, Maharashtra 400001",
        product_name="Tata Tea Gold",
        mrp="Rs. 150.00",
        net_quantity="250 g",
        unit_sale_price="Rs. 0.60 / g",
        manufacturing_date="01/2025",
        country_of_origin="India",
        fssai_license="10014011000456",
        ingredients="Tea Leaves"
    )
    res = eng.check(info)
    assert "checks" in res
    assert len(res["checks"]) == 14
    
    for check in res["checks"]:
        assert check.rule_version is not None
        assert check.execution_trace is not None
        trace = check.execution_trace
        assert trace["rule_id"] == check.rule_id
        assert "execution_ms" in trace
        assert trace["output_status"] == check.status
        assert trace["prerequisites_met"] is True
        assert len(trace["conditions_evaluated"]) > 0


def test_5_state_compliance_results():
    eng = ComplianceEngine()
    
    # Test NOT_APPLICABLE status for FSSAI on non-food item
    non_food_info = ProductInfo(
        product_name="Cello Stainless Steel Bottle",
        manufacturer="Cello World Ltd, Mumbai 400001",
        mrp="Rs. 499.00",
        net_quantity="1 N",
        country_of_origin="India",
        manufacturing_date="02/2025"
    )
    res = eng.check(non_food_info)
    fssai_checks = [c for c in res["checks"] if c.rule_id.startswith("FS-")]
    for fc in fssai_checks:
        assert fc.status == ComplianceStatus.NOT_APPLICABLE.value
        assert fc.required is False
        assert fc.execution_trace["exemption_applied"] is not None

    # Test PASS status
    mfg_check = next(c for c in res["checks"] if c.rule_id == "LM-001")
    assert mfg_check.status == ComplianceStatus.PASS.value
    assert mfg_check.pass_reason is not None

    # Test FAIL status
    mrp_missing_info = ProductInfo(manufacturer="Sample Brand Ltd")
    res_fail = eng.check(mrp_missing_info)
    mrp_check = next(c for c in res_fail["checks"] if c.rule_id == "LM-004")
    assert mrp_check.status == ComplianceStatus.FAIL.value
    assert mrp_check.fail_reason is not None


def test_rule_conflict_detection_chronological():
    eng = ComplianceEngine()
    conflicting_info = ProductInfo(
        product_name="Expired Batch Chips",
        manufacturing_date="10/2025",
        best_before="01/2024",
        mrp="Rs. 20.00",
        net_quantity="50 g"
    )
    res = eng.check(conflicting_info)
    conflicts = res.get("conflicts", [])
    chrono_conflicts = [c for c in conflicts if c.get("conflict_type") == "CHRONOLOGICAL_INCONSISTENCY"]
    assert len(chrono_conflicts) > 0
    assert "LM-008" in chrono_conflicts[0]["rule_ids"]
    assert "FS-005" in chrono_conflicts[0]["rule_ids"]


def test_rule_conflict_detection_unit_sale_price():
    eng = ComplianceEngine()
    # Pack with MRP Rs 500, but USP declared as Rs 600
    invalid_usp_info = ProductInfo(
        product_name="Premium Basmati Rice",
        net_quantity="5 kg",
        mrp="Rs. 500.00",
        unit_sale_price="Rs. 600.00 / kg"
    )
    res = eng.check(invalid_usp_info)
    conflicts = res.get("conflicts", [])
    math_conflicts = [c for c in conflicts if c.get("conflict_type") == "MATHEMATICAL_MISMATCH"]
    assert len(math_conflicts) > 0
    assert "LM-004" in math_conflicts[0]["rule_ids"]
    assert "LM-007" in math_conflicts[0]["rule_ids"]


def test_single_rule_simulation_in_memory():
    eng = ComplianceEngine()
    info = ProductInfo(
        mrp="Rs. 100.00 (inclusive of all taxes)",
        net_quantity="500 g"
    )
    sim_resp = eng.test_single_rule("LM-004", info)
    assert sim_resp.rule_id == "LM-004"
    assert sim_resp.status == "PASS"
    assert sim_resp.is_simulation is True
    assert sim_resp.execution_trace["rule_version"] == "2011.amended"
    assert sim_resp.execution_trace["inputs"]["mrp"] == "Rs. 100.00 (inclusive of all taxes)"


@pytest.mark.asyncio
async def test_compliance_api_routes():
    from httpx import AsyncClient, ASGITransport
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Test GET /api/compliance/rules
        resp = await ac.get("/api/compliance/rules")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 14

        # Test Category filter
        resp_cat = await ac.get("/api/compliance/rules?category=NON_FOOD")
        assert resp_cat.status_code == 200
        assert len(resp_cat.json()) == 9

        # Test GET /api/compliance/rules/{rule_id}
        resp_rule = await ac.get("/api/compliance/rules/LM-004")
        assert resp_rule.status_code == 200
        rule_data = resp_rule.json()
        assert rule_data["id"] == "LM-004"
        assert rule_data["rule_version"] == "2011.amended"

        # Test POST /api/compliance/test-rule simulation
        sim_payload = {
            "rule_id": "LM-003",
            "product_info": {
                "net_quantity": "1 kg"
            }
        }
        resp_sim = await ac.post("/api/compliance/test-rule", json=sim_payload)
        assert resp_sim.status_code == 200
        sim_data = resp_sim.json()
        assert sim_data["rule_id"] == "LM-003"
        assert sim_data["status"] == "PASS"
        assert sim_data["is_simulation"] is True

