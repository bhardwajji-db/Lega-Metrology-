from PIL import Image
from typing import List, Dict, Any, Tuple
import cv2
import numpy as np

class RegionDetector:
    """
    Intelligent region detection for Indian packaged commodities.
    Segments labels into functional zones:
    - header_brand: Product name & brand highlights
    - nutrition_panel: Nutrition facts table
    - middle_statutory: Manufacturer, Marketer, FSSAI, Consumer care
    - bottom_stamp: Stamp box (MRP, Net Weight, Dates, Batch Number)
    Gracefully falls back to whole-image OCR if region detection fails.
    """

    @staticmethod
    def detect_regions(image: Image.Image) -> List[Dict[str, Any]]:
        regions: List[Dict[str, Any]] = []
        w, h = image.size

        # If image is very small or narrow, do not fragment
        if h < 300 or w < 250:
            return regions

        try:
            # 1. Header / Brand Region (Top 0% to 32%)
            h_header = int(h * 0.32)
            if h_header > 40:
                regions.append({
                    'type': 'header_brand',
                    'bbox': [0, 0, w, h_header],
                    'crop': image.crop((0, 0, w, h_header)),
                    'psm': 6
                })

            # 2. Middle Statutory & Nutrition Region (24% to 68%)
            y_mid_start = int(h * 0.24)
            y_mid_end = int(h * 0.68)
            if y_mid_end > y_mid_start + 40:
                regions.append({
                    'type': 'middle_statutory',
                    'bbox': [0, y_mid_start, w, y_mid_end],
                    'crop': image.crop((0, y_mid_start, w, y_mid_end)),
                    'psm': 6
                })

            # 3. Bottom Stamp & Legal Declarations Area (62% to 100%)
            # Specifically targets MRP, Net Quantity, Batch, Mfg/Exp Dates
            y_bottom_start = int(h * 0.62)
            if h > y_bottom_start + 40:
                regions.append({
                    'type': 'bottom_stamp',
                    'bbox': [0, y_bottom_start, w, h],
                    'crop': image.crop((0, y_bottom_start, w, h)),
                    'psm': 6
                })

            # 4. Stamp Box isolation (Bottom 25%)
            y_stamp_start = int(h * 0.74)
            if h > y_stamp_start + 30:
                regions.append({
                    'type': 'stamp_box_sparse',
                    'bbox': [0, y_stamp_start, w, h],
                    'crop': image.crop((0, y_stamp_start, w, h)),
                    'psm': 11
                })

            # 4b. Targeted Rectangular/Dotted Stamp Area Detector (Contour-based)
            try:
                roi_h_start = int(h * 0.55)
                roi_crop = image.crop((0, roi_h_start, w, h))
                roi_np = np.array(roi_crop.convert('L'))
                roi_edges = cv2.Canny(roi_np, 30, 120)
                stamp_contours, _ = cv2.findContours(roi_edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

                for sc in stamp_contours:
                    sx, sy, sbw, sbh = cv2.boundingRect(sc)
                    # Rectangular box taking 25-95% width and 15-80% height of ROI
                    if sbw > w * 0.25 and sbh > (h - roi_h_start) * 0.15 and sbw < w * 0.98:
                        aspect = sbw / float(sbh)
                        if 1.0 <= aspect <= 4.2:
                            abs_y1 = roi_h_start + sy
                            abs_y2 = min(h, abs_y1 + sbh)
                            abs_x1 = max(0, sx)
                            abs_x2 = min(w, sx + sbw)
                            regions.append({
                                'type': 'stamp_contour_box',
                                'bbox': [abs_x1, abs_y1, abs_x2, abs_y2],
                                'crop': image.crop((abs_x1, abs_y1, abs_x2, abs_y2)),
                                'psm': 6
                            })
                            break
            except Exception:
                pass

            # 5. Table detector for Nutrition Table
            img_np = np.array(image.convert('L'))
            thresh = cv2.adaptiveThreshold(
                img_np, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 4
            )
            h_k = cv2.getStructuringElement(cv2.MORPH_RECT, (max(10, w // 20), 1))
            v_k = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(10, h // 30)))
            h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_k)
            v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_k)
            table_mask = cv2.bitwise_or(h_lines, v_lines)
            contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for c in contours:
                bx, by, bw, bh = cv2.boundingRect(c)
                # Nutrition tables usually take 20-60% width and 15-50% height in the middle/upper section
                if bw > w * 0.25 and bh > h * 0.15 and by < h * 0.75:
                    # Add mild padding
                    pad_x = int(bw * 0.05)
                    pad_y = int(bh * 0.05)
                    x1 = max(0, bx - pad_x)
                    y1 = max(0, by - pad_y)
                    x2 = min(w, bx + bw + pad_x)
                    y2 = min(h, by + bh + pad_y)
                    regions.append({
                        'type': 'nutrition_table',
                        'bbox': [x1, y1, x2, y2],
                        'crop': image.crop((x1, y1, x2, y2)),
                        'psm': 6
                    })
                    break

        except Exception:
            # Safe fallback: return whatever regions succeeded
            pass

        return regions
