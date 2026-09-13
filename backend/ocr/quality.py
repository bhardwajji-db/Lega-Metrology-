import cv2
import numpy as np
from typing import Dict, Any, Optional

def assess_image_quality(image_path: str) -> Dict[str, Any]:
    """
    Calculate basic image quality indicators:
    - resolution
    - blur (Laplacian variance)
    - brightness (mean pixel intensity)
    - contrast (pixel standard deviation)
    Returns dictionary with diagnostics and user-facing warning if poor.
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {
                'is_good': False,
                'resolution': 'Unknown',
                'blur_score': 0.0,
                'brightness': 0.0,
                'contrast': 0.0,
                'issues': ['Image file unreadable'],
                'warning': 'Image could not be opened for quality assessment.'
            }

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 1. Blur score: Laplacian variance
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # 2. Brightness: mean intensity
        brightness = float(np.mean(gray))

        # 3. Contrast: standard deviation
        contrast = float(np.std(gray))

        issues = []
        if min(w, h) < 400:
            issues.append('Low resolution (under 400px); tiny statutory text may not resolve.')
        if blur_score < 70.0:
            issues.append('Camera blur detected; fine print may be degraded.')
        if brightness < 45.0:
            issues.append('Image is very dark / underexposed.')
        elif brightness > 230.0:
            issues.append('Excessive glare / overexposed reflections.')
        if contrast < 28.0:
            issues.append('Low contrast between label text and packaging background.')

        warning = " | ".join(issues) if issues else None

        return {
            'is_good': len(issues) == 0,
            'resolution': f'{w}x{h}',
            'blur_score': round(blur_score, 1),
            'brightness': round(brightness, 1),
            'contrast': round(contrast, 1),
            'issues': issues,
            'warning': warning
        }
    except Exception as e:
        return {
            'is_good': True,
            'resolution': 'Unknown',
            'blur_score': 0.0,
            'brightness': 0.0,
            'contrast': 0.0,
            'issues': [],
            'warning': None
        }
