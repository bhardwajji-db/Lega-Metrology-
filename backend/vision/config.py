from typing import Dict, Any

class VisionConfig:
    # ── Image Quality Thresholds ──
    MIN_RESOLUTION_WIDTH: int = 350
    MIN_RESOLUTION_HEIGHT: int = 350
    OPTIMAL_RESOLUTION_MAX: int = 2600

    BLUR_LAPLACIAN_SEVERELY_DEGRADED: float = 35.0
    BLUR_LAPLACIAN_DEGRADED: float = 70.0
    BLUR_LAPLACIAN_ACCEPTABLE: float = 120.0

    MOTION_BLUR_GRADIENT_RATIO_THRESHOLD: float = 2.4
    
    LUMINANCE_UNDEREXPOSURE_THRESHOLD: float = 40.0
    LUMINANCE_LOW_LIGHT_THRESHOLD: float = 65.0
    LUMINANCE_OVEREXPOSURE_THRESHOLD: float = 225.0
    LUMINANCE_SEVERE_OVEREXPOSURE: float = 245.0

    GLARE_PIXEL_INTENSITY_MIN: int = 245
    GLARE_CONCENTRATION_AREA_MIN: int = 150
    GLARE_SEVERITY_RATIO_THRESHOLD: float = 0.035

    SKEW_ANGLE_TOLERANCE_DEG: float = 3.5
    SKEW_MAX_CORRECTION_DEG: float = 45.0

    SMALL_TEXT_HEIGHT_PX_THRESHOLD: float = 12.0

    # ── Confidence Tiers ──
    CONFIDENCE_TIER_HIGH: float = 0.90
    CONFIDENCE_TIER_MEDIUM: float = 0.75
    CONFIDENCE_TIER_LOW: float = 0.50

    @classmethod
    def get_confidence_tier(cls, score: float) -> str:
        if score >= cls.CONFIDENCE_TIER_HIGH:
            return "HIGH"
        elif score >= cls.CONFIDENCE_TIER_MEDIUM:
            return "MEDIUM"
        elif score >= cls.CONFIDENCE_TIER_LOW:
            return "LOW"
        else:
            return "VERY_LOW"

vision_config = VisionConfig()
