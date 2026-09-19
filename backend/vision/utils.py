import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from PIL import Image

def normalize_bbox(bbox: List[int], width: int, height: int) -> List[float]:
    """Convert [x1, y1, x2, y2] in pixels to normalized [0.0..1.0] coordinates."""
    if not bbox or len(bbox) != 4 or width <= 0 or height <= 0:
        return [0.0, 0.0, 0.0, 0.0]
    x1, y1, x2, y2 = bbox
    return [
        round(max(0.0, min(1.0, x1 / float(width))), 4),
        round(max(0.0, min(1.0, y1 / float(height))), 4),
        round(max(0.0, min(1.0, x2 / float(width))), 4),
        round(max(0.0, min(1.0, y2 / float(height))), 4),
    ]

def denormalize_bbox(norm_bbox: List[float], width: int, height: int) -> List[int]:
    """Convert normalized [0.0..1.0] coordinates to pixel integers."""
    if not norm_bbox or len(norm_bbox) != 4:
        return [0, 0, 0, 0]
    nx1, ny1, nx2, ny2 = norm_bbox
    return [
        int(round(nx1 * width)),
        int(round(ny1 * height)),
        int(round(nx2 * width)),
        int(round(ny2 * height)),
    ]

def compute_iou(boxA: List[int], boxB: List[int]) -> float:
    """Calculate Intersection over Union (IoU) between two bounding boxes."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = max(0, (boxA[2] - boxA[0])) * max(0, (boxA[3] - boxA[1]))
    boxBArea = max(0, (boxB[2] - boxB[0])) * max(0, (boxB[3] - boxB[1]))

    denom = float(boxAArea + boxBArea - interArea)
    if denom <= 0:
        return 0.0
    return interArea / denom

def box_union(boxes: List[List[int]], width: int, height: int) -> Optional[List[int]]:
    """Compute the enclosing bounding box for a list of boxes."""
    if not boxes:
        return None
    min_x = max(0, min(b[0] for b in boxes))
    min_y = max(0, min(b[1] for b in boxes))
    max_x = min(width, max(b[2] for b in boxes))
    max_y = min(height, max(b[3] for b in boxes))
    return [min_x, min_y, max_x, max_y]

def pad_bbox(bbox: List[int], pad_x: int, pad_y: int, max_w: int, max_h: int) -> List[int]:
    """Add safe padding around a bounding box without overflowing image boundaries."""
    return [
        max(0, bbox[0] - pad_x),
        max(0, bbox[1] - pad_y),
        min(max_w, bbox[2] + pad_x),
        min(max_h, bbox[3] + pad_y)
    ]

def pil_to_cv2(pil_image: Image.Image) -> np.ndarray:
    """Safely convert PIL Image to BGR OpenCV ndarray."""
    rgb = pil_image.convert('RGB')
    return cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)

def cv2_to_pil(cv_image: np.ndarray) -> Image.Image:
    """Safely convert BGR OpenCV ndarray to PIL RGB Image."""
    rgb = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)
