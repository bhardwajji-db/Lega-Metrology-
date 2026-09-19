import re
from typing import List, Dict, Any, Tuple
from vision.config import vision_config

class PanelClassifier:
    """
    Confidence-based Front / Back / Side / Top / Bottom Panel Classifier.
    Combines multi-modal visual & textual signals:
    - Text density (words per area)
    - Nutrition table & ingredients presence
    - Manufacturer & customer care presence
    - Prominent brand/title font height
    - Barcode proximity & narrow geometric aspect ratio
    """

    FRONT_KEYWORDS = [
        "classic", "original", "premium", "rich", "flavour", "flavor", "delicious",
        "tasty", "fresh", "special", "instant", "healthy", "natural", "crunchy"
    ]

    BACK_KEYWORDS = [
        "ingredients", "nutrition", "nutritional", "manufactured by", "packed by",
        "marketed by", "consumer care", "customer care", "helpline", "batch no",
        "net quantity", "mfg date", "exp date", "lic no", "fssai", "storage instructions"
    ]

    @classmethod
    def classify(
        cls,
        text: str,
        words: List[Dict[str, Any]],
        img_width: int,
        img_height: int,
        has_nutrition_table: bool = False,
        has_barcode: bool = False
    ) -> Tuple[str, float, List[str]]:
        signals: List[str] = []
        front_score = 0.0
        back_score = 0.0
        side_score = 0.0

        aspect = float(img_width) / max(float(img_height), 1.0)
        word_count = len(words)
        text_lower = text.lower() if text else ""

        # 1. Aspect Ratio Signal
        if aspect < 0.45 or aspect > 2.3:
            side_score += 0.35
            signals.append(f"Narrow geometry (aspect: {aspect:.2f}) indicates side or flap panel")
        else:
            front_score += 0.10
            back_score += 0.10

        # 2. Text Density Signal
        # Back panels usually have high word counts (30+ words), front has fewer prominent words
        if word_count > 35:
            back_score += 0.40
            signals.append(f"High text density ({word_count} tokens) characteristic of Information/Back panel")
        elif word_count < 15 and word_count > 0:
            front_score += 0.35
            signals.append(f"Sparse, high-prominence text ({word_count} tokens) characteristic of Principal Display/Front panel")

        # 3. Keyword Grounding
        back_hits = sum(1 for kw in cls.BACK_KEYWORDS if kw in text_lower)
        front_hits = sum(1 for kw in cls.FRONT_KEYWORDS if kw in text_lower)

        if back_hits >= 3:
            back_score += 0.45
            signals.append(f"Multiple statutory information markers ({back_hits} keywords: ingredients/manufacturer/mrp)")
        elif back_hits >= 1:
            back_score += 0.20

        if front_hits >= 1 and back_hits <= 1:
            front_score += 0.30
            signals.append(f"Branding / marketing claims detected ({front_hits} keywords)")

        # 4. Nutrition Table & Barcode
        if has_nutrition_table:
            back_score += 0.35
            signals.append("Structured Nutrition Information Table detected")

        if has_barcode and (aspect < 0.6 or aspect > 1.8):
            side_score += 0.30
            signals.append("1D Barcode located on narrow facet")

        # 5. Font Height Variance
        if words:
            font_heights = [abs(w.get('bbox', [0,0,0,0])[3] - w.get('bbox', [0,0,0,0])[1]) for w in words]
            max_h = max(font_heights) if font_heights else 0
            avg_h = sum(font_heights) / len(font_heights) if font_heights else 0
            if max_h > avg_h * 2.5 and max_h > img_height * 0.08:
                front_score += 0.25
                signals.append(f"Prominent large brand title text (height: {max_h}px)")

        # Compute winner
        scores = {
            "front_candidate": front_score,
            "back_candidate": back_score,
            "side_candidate": side_score
        }

        winner = max(scores, key=scores.get)
        win_score = scores[winner]

        if win_score < 0.25:
            return "unknown", 0.35, ["Insufficient visual & textual signals to classify panel surface with high confidence"]

        confidence = round(min(0.96, max(0.40, win_score / (sum(scores.values()) + 1e-4) * 0.85 + 0.15)), 2)
        return winner, confidence, signals

panel_classifier = PanelClassifier()
