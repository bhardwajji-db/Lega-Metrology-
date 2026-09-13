import re
from typing import Dict, Any, Optional
from models.schemas import ProductInfo

class PackageContext:
    """
    Infers package domain attributes from extracted text and declarations:
    - Is food commodity?
    - Is imported?
    - Is retail package?
    - Is single-ingredient?
    - Is multi-image or single-image evidence?
    """

    @staticmethod
    def infer_context(product_info: ProductInfo, ocr_text: str = "") -> Dict[str, Any]:
        info_dict = product_info.model_dump()
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
        
        # 2. Import Status Detection
        # Check country of origin, importer keywords
        coo = (info_dict.get('country_of_origin') or "").lower()
        importer_match = bool(re.search(r'\b(?:imported\s*by|importer|imported\s*from)\b', text_lower))
        is_imported = False
        if importer_match:
            is_imported = True
        elif coo and coo not in ('india', 'bharat', 'ind') and not any(k in text_lower for k in ['made in india', 'product of india', 'mfd. in india']):
            is_imported = True
            
        # 3. Single-Ingredient Food Detection (e.g. 100% Rice, Single Grain, Pure Salt)
        is_single_ingredient = False
        if any(k in prod_name for k in ['basmati rice', 'raw rice', 'pure salt', 'whole wheat', 'crystal salt']):
            is_single_ingredient = True
        elif re.search(r'100%\s*(?:pure|basmati|whole|single)', text_lower):
            is_single_ingredient = True

        # 4. Retail Package Status (Commodity intended for retail sale to ultimate consumer)
        # Default True for prototype consumer packs under Legal Metrology Rule 2(k)
        is_retail = True
        if any(k in text_lower for k in ['wholesale only', 'industrial use', 'institutional pack']):
            is_retail = False

        return {
            'is_food': is_food,
            'is_imported': is_imported,
            'is_single_ingredient': is_single_ingredient,
            'is_retail': is_retail
        }
