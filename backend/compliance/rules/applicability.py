import re
from typing import Dict, Any, Optional, Tuple
from models.schemas import ProductInfo
from compliance.rules.models import RuleDefinition

class PackageContext:
    """
    Infers package domain attributes from extracted text and declarations:
    - Primary category (FOOD, NON_FOOD, COSMETICS, MEDICAL_DEVICES, EXPORT)
    - Is food commodity?
    - Is imported?
    - Is export?
    - Is retail package?
    - Is single-ingredient?
    - Is multi-image or single-image evidence?
    """

    @staticmethod
    def infer_context(product_info: ProductInfo, ocr_text: str = "") -> Dict[str, Any]:
        info_dict = product_info.model_dump() if hasattr(product_info, 'model_dump') else (product_info.dict() if hasattr(product_info, 'dict') else {})
        text_lower = (ocr_text or "").lower()
        prod_name = (product_info.product_name or "").lower()
        
        # 1. Food Detection
        # Check FSSAI license, ingredients, nutrition facts, or food keywords
        has_fssai = bool(info_dict.get('fssai_license'))
        has_nut = bool(info_dict.get('nutritional_info') or info_dict.get('nutrition_facts'))
        has_ingr = bool(info_dict.get('ingredients'))
        food_keywords = [
            'oats', 'rice', 'juice', 'noodles', 'snack', 'cereal', 'food', 'edible',
            'flour', 'atta', 'oil', 'masala', 'biscuit', 'tea', 'coffee', 'chocolate',
            'protein', 'sugar', 'salt', 'milk', 'dairy', 'spices', 'pulses', 'dal',
            'wheat', 'grain', 'beverage', 'drink', 'bar', 'candy', 'confectionery', 'soup', 'pasta', 'sauce'
        ]
        is_food = has_fssai or has_nut or has_ingr or any(k in prod_name for k in food_keywords) or any(k in text_lower for k in ['ingredients:', 'nutrition facts', 'fssai'])
        
        # 2. Cosmetics Detection
        cosmetics_keywords = [
            'shampoo', 'conditioner', 'soap', 'lotion', 'face wash', 'cream', 'serum',
            'lipstick', 'perfume', 'deodorant', 'cosmetic', 'moisturizer', 'sunscreen',
            'hair oil', 'body wash', 'toothpaste'
        ]
        is_cosmetics = any(k in prod_name for k in cosmetics_keywords) or any(k in text_lower for k in ['for external use only', 'dermatologically tested', 'cosmetic licence'])

        # 3. Medical Devices Detection
        medical_keywords = [
            'thermometer', 'syringe', 'bandage', 'dressing', 'catheter', 'glucometer',
            'oximeter', 'diagnostic', 'sterile', 'medical device', 'surgical'
        ]
        is_medical_device = any(k in prod_name for k in medical_keywords) or any(k in text_lower for k in ['mfg. lic. no.', 'sterile eo', 'single use only'])

        # 4. Import Status Detection
        coo = (info_dict.get('country_of_origin') or "").lower()
        importer_match = bool(re.search(r'\b(?:imported\s*by|importer|imported\s*from)\b', text_lower))
        is_imported = False
        if importer_match:
            is_imported = True
        elif coo and coo not in ('india', 'bharat', 'ind') and not any(k in text_lower for k in ['made in india', 'product of india', 'mfd. in india']):
            is_imported = True

        # 5. Export Context
        is_export = bool(re.search(r'\b(?:for\s*export\s*only|export\s*pack|duty\s*free)\b', text_lower))

        # 6. Single-Ingredient Food Detection (e.g. 100% Rice, Single Grain, Pure Salt)
        is_single_ingredient = False
        if any(k in prod_name for k in ['basmati rice', 'raw rice', 'pure salt', 'whole wheat', 'crystal salt']):
            is_single_ingredient = True
        elif re.search(r'100%\s*(?:pure|basmati|whole|single)', text_lower):
            is_single_ingredient = True

        # 7. Retail Package Status (Commodity intended for retail sale to ultimate consumer)
        is_retail = True
        if any(k in text_lower for k in ['wholesale only', 'industrial use', 'institutional pack']):
            is_retail = False

        # Determine primary category
        if is_food:
            primary_cat = "FOOD"
        elif is_cosmetics:
            primary_cat = "COSMETICS"
        elif is_medical_device:
            primary_cat = "MEDICAL_DEVICES"
        elif is_export:
            primary_cat = "EXPORT"
        else:
            primary_cat = "NON_FOOD"

        return {
            'category': primary_cat,
            'is_food': is_food,
            'is_cosmetics': is_cosmetics,
            'is_medical_device': is_medical_device,
            'is_imported': is_imported,
            'is_export': is_export,
            'is_single_ingredient': is_single_ingredient,
            'is_retail': is_retail
        }

    @staticmethod
    def is_rule_applicable(rule_def: RuleDefinition, context: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Determines whether a RuleDefinition applies under the identified package context.
        Returns (is_applicable, applicability_reason).
        """
        # 1. Domain Applicability: FSSAI rules apply exclusively to food packages
        if rule_def.domain.value == "FSSAI" and not context.get('is_food', False):
            return False, "FSSAI regulations apply exclusively to food commodities."

        # 2. Category Applicability
        cat = context.get('category', 'ALL')
        cat_app = getattr(rule_def, 'category_applicability', ['ALL'])
        if "ALL" not in cat_app and cat not in cat_app:
            if context.get('is_food') and "FOOD" not in cat_app:
                return False, f"Rule {rule_def.id} is non-food specific; food provisions governed under FSSAI."

        # 3. Export Exemption (Rule 26)
        if context.get('is_export', False) and not getattr(rule_def, 'applies_to_export', False):
            return False, "Export packages are exempt from domestic retail labelling under Rule 26."

        return True, "Rule applicable under current package category and attributes."

