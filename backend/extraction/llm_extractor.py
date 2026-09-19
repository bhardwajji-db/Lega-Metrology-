"""
MetrCheck AI — Gemini / Multimodal LLM Extraction Engine
Integrates Google Gemini 3.8 / 2.5 Flash / Pro models for intelligent Legal Metrology
and FSSAI packaged commodity declaration extraction, semantic enrichment,
and compliance auto-correction recommendations.
"""

import json
import logging
import httpx
from typing import Optional, List, Dict, Any

from config import settings
from models.schemas import ProductInfo, ProductImageEvidence
from extraction.extractor import extractor

logger = logging.getLogger(__name__)

GEMINI_API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

EXTRACTION_SYSTEM_PROMPT = """You are an expert Legal Metrology and FSSAI Compliance Inspector specializing in Indian Packaged Commodity Regulations (Legal Metrology Packaged Commodities Rules 2011, and Food Safety and Standards Regulations).

Analyze the provided OCR text extracted from commodity packaging (and image descriptions if provided).
Extract all statutory declarations into a strict JSON object with these EXACT keys:
{
  "product_name": string or null (full commercial name),
  "brand": string or null (brand name),
  "category": string or null (e.g. food, beverage, cosmetics, electronics, etc.),
  "is_food": boolean (true if edible food/beverage product, false otherwise),
  "net_quantity": string or null (standardized with unit, e.g. '500 g', '1 L', '100 ml', '1 N', '2 pcs'),
  "mrp": string or null (inclusive of all taxes, formatted with currency e.g. '₹120.00' or 'Rs 120'),
  "unit_sale_price": string or null (e.g. '₹0.24 / g' or 'Rs 1.20 / ml'),
  "manufacture_date": string or null (date or month/year, e.g. '08/2026' or '2026-08-15'),
  "packaging_date": string or null (date or month/year if specifically marked as packed date),
  "expiry_date": string or null (date or month/year if indicated),
  "best_before": string or null (e.g. '6 months from manufacture' or 'Best Before 12/2026'),
  "batch_number": string or null (lot number or batch code),
  "fssai_license": string or null (14-digit FSSAI licence number only digits),
  "consumer_care": string or null (combined consumer helpline / email / address),
  "consumer_care_phone": string or null (toll free phone or mobile),
  "consumer_care_email": string or null (email address),
  "country_of_origin": string or null (e.g. 'India', 'Made in India', 'Product of Germany'),
  "manufacturer_name": string or null (company or business entity),
  "manufacturer_address": string or null (complete physical manufacturing address),
  "packer_name": string or null (if packed by different entity),
  "packer_address": string or null,
  "importer_name": string or null (if imported),
  "importer_address": string or null,
  "ingredients": string or null (list of ingredients),
  "nutritional_info": string or null (summary of energy, protein, fat, carbs, etc.),
  "veg_nonveg_status": string or null ('GREEN' for vegetarian, 'BROWN' for non-vegetarian, or null)
}

RULES:
1. Return ONLY the JSON object. Do not include markdown formatting or backticks if possible.
2. If a field is not detected or cannot be verified from the text, return null for that key. Do not hallucinate.
3. For net_quantity, ensure SI units are preserved accurately (g, kg, ml, l, N).
4. For fssai_license, strip spaces and prefixes, extract exactly the 14 digits.
"""


class LLMExtractor:
    def __init__(self):
        self.timeout_sec = 8.0

    def get_api_key(self) -> str:
        return settings.active_gemini_api_key

    def get_model(self) -> str:
        model = (settings.GEMINI_MODEL or "gemini-2.5-flash").strip()
        # Map user convenience alias
        if model.lower() in ("gemini-3.8", "gemini-3.8-flash"):
            return "gemini-2.5-flash"
        return model

    async def call_gemini_api(self, prompt: str) -> Optional[Dict[str, Any]]:
        api_key = self.get_api_key()
        if not api_key:
            return None

        model = self.get_model()
        url = GEMINI_API_URL_TEMPLATE.format(model=model, key=api_key)
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts and "text" in parts[0]:
                            raw_text = parts[0]["text"].strip()
                            if raw_text.startswith("```json"):
                                raw_text = raw_text[7:]
                            if raw_text.startswith("```"):
                                raw_text = raw_text[3:]
                            if raw_text.endswith("```"):
                                raw_text = raw_text[:-3]
                            return json.loads(raw_text.strip())
                else:
                    logger.warning(f"[Gemini API] Request returned {resp.status_code}: {resp.text[:200]}")
                    return None
        except Exception as e:
            logger.warning(f"[Gemini API] Exception during extraction: {e}")
            return None

    def extract(self, text: str, images: Optional[List[ProductImageEvidence]] = None) -> ProductInfo:
        """Synchronous extraction method providing backward-compatibility for all existing routes."""
        info = extractor.extract(text, images=images)
        info.extraction_mode = 'local'

        api_key = self.get_api_key()
        if not settings.GEMINI_ENABLED or not api_key or settings.TEST_MODE:
            return info

        try:
            import asyncio
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

            if loop and loop.is_running():
                return info
            else:
                gemini_data = asyncio.run(self.extract_async_gemini(text, images))
                if gemini_data:
                    self._merge_gemini_data(info, gemini_data)
                    info.extraction_mode = f"gemini:{self.get_model()}"
        except Exception as e:
            logger.debug(f"[Gemini Sync Fallback] Error in extraction: {e}")

        return info

    async def extract_async(self, text: str, images: Optional[List[ProductImageEvidence]] = None) -> ProductInfo:
        """Asynchronous extraction with Gemini LLM enhancement."""
        info = extractor.extract(text, images=images)
        info.extraction_mode = 'local'

        api_key = self.get_api_key()
        if not settings.GEMINI_ENABLED or not api_key or settings.TEST_MODE:
            return info

        gemini_data = await self.extract_async_gemini(text, images)
        if gemini_data:
            self._merge_gemini_data(info, gemini_data)
            info.extraction_mode = f"gemini:{self.get_model()}"

        return info

    async def extract_async_gemini(self, text: str, images: Optional[List[ProductImageEvidence]] = None) -> Optional[Dict[str, Any]]:
        prompt = f"{EXTRACTION_SYSTEM_PROMPT}\n\nPACKAGING OCR TEXT:\n{text}"
        if images:
            prompt += f"\n\nPANEL EVIDENCE SUMMARY: {len(images)} panels inspected: " + ", ".join(i.label for i in images)
        return await self.call_gemini_api(prompt)

    def _merge_gemini_data(self, info: ProductInfo, gemini_data: Dict[str, Any], refine_existing: bool = True):
        """Safely enrich baseline ProductInfo with Gemini extractions."""
        for field, val in gemini_data.items():
            if val is not None and hasattr(info, field):
                current_val = getattr(info, field)
                if not current_val or refine_existing:
                    setattr(info, field, val)
                    info.declaration_confidences[field] = 0.95
                elif field == "is_food" and current_val is None:
                    setattr(info, field, bool(val))
                elif field == "veg_nonveg_status" and not current_val:
                    setattr(info, field, str(val).upper())


llm_extractor = LLMExtractor()
