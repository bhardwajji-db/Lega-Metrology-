from typing import List, Dict, Any, Optional
from vision.schemas import TextRegionInfo
from vision.utils import normalize_bbox
from vision.config import vision_config

class TextRegionSegmenter:
    """
    Transforms detected OCR words into structured text regions.
    Performs:
    - Font height estimation per token
    - Small-text / low-resolution risk flagging (height < 12px)
    - Normalized coordinate mapping
    Avoids duplicate OCR detection by reusing PaddleOCR tokens.
    """

    @classmethod
    def segment(
        cls,
        words: List[Dict[str, Any]],
        img_width: int,
        img_height: int
    ) -> List[TextRegionInfo]:
        if not words or img_width <= 0 or img_height <= 0:
            return []

        regions: List[TextRegionInfo] = []
        for idx, w in enumerate(words):
            bbox = w.get('bbox', [0, 0, 0, 0])
            if len(bbox) != 4:
                continue

            x1, y1, x2, y2 = bbox
            font_h = abs(y2 - y1)
            is_small = font_h < vision_config.SMALL_TEXT_HEIGHT_PX_THRESHOLD
            norm_box = normalize_bbox(bbox, img_width, img_height)

            reg = TextRegionInfo(
                id=f"text_reg_{idx+1}",
                bbox=[int(x1), int(y1), int(x2), int(y2)],
                normalized_bbox=norm_box,
                text=str(w.get('text', '')),
                confidence=round(float(w.get('confidence', 0.0)), 2),
                estimated_font_height_px=float(font_h),
                is_small_text=is_small,
                orientation=0.0,
                script=w.get('script'),
                language=w.get('language')
            )
            regions.append(reg)

        return regions

text_region_segmenter = TextRegionSegmenter()
