from fastapi import APIRouter
from pydantic import BaseModel
from models.schemas import ProductInfo
from extraction.llm_extractor import llm_extractor

router = APIRouter()

class ExtractRequest(BaseModel):
    text: str

@router.post("/extract", response_model=ProductInfo)
async def extract_endpoint(req: ExtractRequest):
    return llm_extractor.extract(req.text)
