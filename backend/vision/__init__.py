"""
MetrCheck AI — Advanced Computer Vision Intelligence Layer
"""

from vision.schemas import (
    VisionAnalysisResult,
    ImageQualityResult,
    ImageQualityMetrics,
    PackageBoundaryResult,
    PerspectiveCorrectionResult,
    PanelCandidate,
    PanelClassificationResult,
    SemanticRegionResult,
    SymbolDetectionResult,
    LogoDetectionResult,
    BarcodeDetectionResult,
    QRDetectionResult,
    TextRegionInfo,
    VisionTimingMetrics
)
from vision.pipeline import vision_pipeline, VisionPipeline
from vision.quality import quality_gate
from vision.geometry import geometric_analyzer
from vision.package_detector import package_boundary_detector
from vision.panel_detector import panel_detector
from vision.classifiers import panel_classifier
from vision.region_detector import semantic_region_detector
from vision.symbol_detector import symbol_detector
from vision.logo_detector import logo_detector
from vision.barcode_detector import barcode_detector
from vision.qr_detector import qr_detector
from vision.evidence import vision_evidence_adapter
from vision.config import vision_config

__all__ = [
    "vision_pipeline",
    "VisionPipeline",
    "VisionAnalysisResult",
    "ImageQualityResult",
    "ImageQualityMetrics",
    "PackageBoundaryResult",
    "PerspectiveCorrectionResult",
    "PanelCandidate",
    "PanelClassificationResult",
    "SemanticRegionResult",
    "SymbolDetectionResult",
    "LogoDetectionResult",
    "BarcodeDetectionResult",
    "QRDetectionResult",
    "TextRegionInfo",
    "VisionTimingMetrics",
    "quality_gate",
    "geometric_analyzer",
    "package_boundary_detector",
    "panel_detector",
    "panel_classifier",
    "semantic_region_detector",
    "symbol_detector",
    "logo_detector",
    "barcode_detector",
    "qr_detector",
    "vision_evidence_adapter",
    "vision_config"
]
