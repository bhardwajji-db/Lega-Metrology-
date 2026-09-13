from models.schemas import ProductInfo
from typing import Dict, List, Any

DEMO_CASES: Dict[str, ProductInfo] = {
    "1": ProductInfo(
        product_name="Royal Gold Premium Basmati Rice",
        brand="Royal Gold",
        manufacturer="Royal Gold Foods Pvt. Ltd., Plot No. 45, Industrial Area, Phase II, Karnal, Haryana - 132001",
        net_quantity="5 kg",
        mrp="₹650",
        manufacturing_date="07/2026",
        expiry_date="07/2027",
        fssai_license="10012345678901",
        consumer_care="1800-123-4567, care@royalgold.example.com",
        country_of_origin="India",
        ingredients="Premium Basmati Rice (100%)",
        batch_number="RG-2026-07-001",
        extraction_mode="demo"
    ),
    "2": ProductInfo(
        product_name="FreshVita Mixed Fruit Juice",
        brand="FreshVita",
        manufacturer="FreshVita Beverages Ltd., 23 MG Road, Pune, Maharashtra - 411001",
        net_quantity="1 L",
        mrp="₹120",
        manufacturing_date="08/2026",
        expiry_date=None,  # Missing
        fssai_license="22345678901234",
        consumer_care=None,  # Missing
        country_of_origin="India",
        ingredients="Water, Apple Juice Concentrate, ...",
        batch_number="FV-2026-08-002",
        extraction_mode="demo"
    ),
    "3": ProductInfo(
        product_name="QuickBite Instant Noodles",
        brand="QuickBite",
        manufacturer=None,  # Missing
        net_quantity=None,  # Missing
        mrp=None,  # Missing
        manufacturing_date=None,  # Missing
        expiry_date=None,  # Missing
        fssai_license=None,  # Missing
        consumer_care=None,  # Missing
        country_of_origin=None,  # Missing
        ingredients=None,  # Missing
        batch_number="QB-2026-09-003",
        extraction_mode="demo"
    )
}

DEMO_CASES_META: Dict[str, Dict[str, Any]] = {
    "1": {
        "id": "1",
        "name": "Royal Gold Premium Basmati Rice",
        "brand": "Royal Gold",
        "category": "Packaged Food / Grains",
        "purpose": "Strong Compliant Package Benchmark",
        "description": "Demonstrates a fully compliant food package with complete statutory declarations including net quantity, MRP, batch number, FSSAI licence, and consumer care details.",
        "panels": ["Front", "Back"],
        "expected_score": 95.5,
        "expected_status": "COMPLIANT",
        "badge_type": "compliant",
        "tags": ["Full Declarations", "FSSAI Valid", "Dual Panel Evidence"]
    },
    "2": {
        "id": "2",
        "name": "FreshVita Mixed Fruit Juice",
        "brand": "FreshVita",
        "category": "Beverages / Packaged Juice",
        "purpose": "Review & Corrective Action Workflow",
        "description": "Demonstrates detection of missing expiry date and consumer care contact declarations under Legal Metrology Rule 6(1) with prioritized corrective actions.",
        "panels": ["Front", "Back"],
        "expected_score": 76.9,
        "expected_status": "POTENTIAL NON-COMPLIANCE",
        "badge_type": "warning",
        "tags": ["Missing Expiry", "Missing Consumer Care", "Corrective Guidance"]
    },
    "3": {
        "id": "3",
        "name": "QuickBite Instant Noodles",
        "brand": "QuickBite",
        "category": "Processed Foods",
        "purpose": "Multiple Non-Compliance Benchmark",
        "description": "Demonstrates automated screening on heavily deficient packaging missing manufacturer address, net quantity, MRP, and date markings.",
        "panels": ["Front"],
        "expected_score": 37.9,
        "expected_status": "POTENTIAL NON-COMPLIANCE",
        "badge_type": "violation",
        "tags": ["Multiple Violations", "High Priority Actions", "Statutory Penalties"]
    }
}


def get_demo_cases_list() -> List[Dict[str, Any]]:
    """Return all demo case metadata items in order."""
    return [DEMO_CASES_META[k] for k in sorted(DEMO_CASES_META.keys())]
