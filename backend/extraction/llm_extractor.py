from typing import Optional, List
from models.schemas import ProductInfo, ProductImageEvidence
from extraction.extractor import extractor

class LLMExtractor:
    def extract(self, text: str, images: Optional[List[ProductImageEvidence]] = None) -> ProductInfo:
        # Stub for LLM extraction
        # Since this is a local/PaddleOCR single engine, we use local extractor
        info = extractor.extract(text, images=images)
        info.extraction_mode = 'llm'
        return info

llm_extractor = LLMExtractor()
