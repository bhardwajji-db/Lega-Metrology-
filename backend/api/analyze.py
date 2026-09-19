from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Request, status
from pydantic import BaseModel
from typing import List, Optional
import json
from models.schemas import AnalysisResponse
from services.analysis_service import analyze_products, analyze_text
from utils.validators import validate_image_file
from auth.security import public_user
from auth.ratelimit import get_client_ip, check_analysis_rate_limit

router = APIRouter()

@router.post("/analyze", response_model=AnalysisResponse)
@router.post("/analyze/batch", response_model=AnalysisResponse)
async def analyze_endpoint(
    request: Request,
    files: Optional[List[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None),
    labels: Optional[str] = Form(None),
    user: Optional[dict] = Depends(public_user)
):
    client_ip = get_client_ip(request)
    allowed, rate_msg = check_analysis_rate_limit(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=rate_msg,
        )

    upload_list: List[UploadFile] = []
    if files:
        upload_list.extend(files)
    if file and file not in upload_list:
        upload_list.append(file)
        
    if not upload_list:
        raise HTTPException(status_code=400, detail="At least one image file is required for analysis.")
        
    for f in upload_list:
        validate_image_file(f)
        
    parsed_labels: Optional[List[str]] = None
    if labels:
        try:
            parsed = json.loads(labels)
            if isinstance(parsed, list):
                parsed_labels = [str(l).strip() for l in parsed]
        except Exception:
            parsed_labels = [l.strip() for l in labels.split(',') if l.strip()]
            
    owner_user_id = user.get("username", "") if user else ""
    organization_id = user.get("organization_id", "") if user else ""
    try:
        result = await analyze_products(upload_list, parsed_labels, owner_user_id=owner_user_id, organization_id=organization_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal analysis error: {str(e)}")


class TextAnalyzeRequest(BaseModel):
    text: str


@router.post("/analyze/text", response_model=AnalysisResponse)
async def analyze_text_endpoint(
    req: TextAnalyzeRequest,
    request: Request,
    user: Optional[dict] = Depends(public_user)
):
    client_ip = get_client_ip(request)
    allowed, rate_msg = check_analysis_rate_limit(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=rate_msg,
        )

    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Text is required for analysis.")
    owner_user_id = user.get("username", "") if user else ""
    organization_id = user.get("organization_id", "") if user else ""
    try:
        result = await analyze_text(req.text.strip(), owner_user_id=owner_user_id, organization_id=organization_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal analysis error: {str(e)}")

