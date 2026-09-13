import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from typing import Dict, Tuple, Optional

class ImagePreprocessor:
    """
    Advanced PIL and OpenCV preprocessing pipeline for packaged-product labels.
    Provides:
    - EXIF orientation correction
    - Non-destructive perspective/quad detection and correction
    - Dynamic Lanczos upscaling for tiny fonts
    - 5 controlled variants for multi-pass OCR
    Never alters original files on disk.
    """

    @staticmethod
    def correct_orientation(image: Image.Image) -> Image.Image:
        """Correct EXIF orientation if present."""
        return ImageOps.exif_transpose(image)

    @staticmethod
    def detect_and_correct_perspective(image: Image.Image) -> Tuple[Image.Image, bool]:
        """
        Detect if photographed package exhibits significant perspective distortion/keystoning.
        If a prominent trapezoidal package boundary is detected (>25% image area, edge ratio > 5%),
        straightens the working copy for OCR. Otherwise preserves the original image.
        Never alters stored original on disk.
        """
        try:
            # Convert PIL to BGR numpy
            img_np = np.array(image.convert('RGB'))[:, :, ::-1]
            h, w = img_np.shape[:2]
            gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edged = cv2.Canny(blurred, 40, 160)

            contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

            img_area = w * h
            for c in contours:
                peri = cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, 0.025 * peri, True)

                if len(approx) == 4 and cv2.contourArea(approx) > 0.25 * img_area:
                    pts = approx.reshape(4, 2).astype('float32')

                    # Order points: top-left, top-right, bottom-right, bottom-left
                    s = pts.sum(axis=1)
                    rect = np.zeros((4, 2), dtype='float32')
                    rect[0] = pts[np.argmin(s)]
                    rect[2] = pts[np.argmax(s)]
                    diff = np.diff(pts, axis=1)
                    rect[1] = pts[np.argmin(diff)]
                    rect[3] = pts[np.argmax(diff)]

                    (tl, tr, br, bl) = rect
                    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
                    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
                    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
                    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))

                    w_ratio = abs(widthA - widthB) / max(widthA, widthB)
                    h_ratio = abs(heightA - heightB) / max(heightA, heightB)

                    # Only warp if genuinely trapezoidal/skewed to avoid unnecessary blur
                    if w_ratio > 0.06 or h_ratio > 0.06:
                        maxWidth = max(int(widthA), int(widthB))
                        maxHeight = max(int(heightA), int(heightB))
                        # Prevent degenerate transformations
                        if maxWidth > 300 and maxHeight > 300:
                            dst = np.array([
                                [0, 0],
                                [maxWidth - 1, 0],
                                [maxWidth - 1, maxHeight - 1],
                                [0, maxHeight - 1]
                            ], dtype='float32')
                            M = cv2.getPerspectiveTransform(rect, dst)
                            warped = cv2.warpPerspective(img_np, M, (maxWidth, maxHeight))
                            # Convert back to PIL RGB
                            warped_rgb = cv2.cvtColor(warped, cv2.COLOR_BGR2RGB)
                            return Image.fromarray(warped_rgb), True
        except Exception:
            pass

        return image, False

    @staticmethod
    def scale_image(image: Image.Image) -> Tuple[Image.Image, float]:
        """
        Dynamically upscale image so small 6pt-8pt fonts achieve sufficient resolution for OCR.
        Limits maximum dimension to 2600px for optimal speed and recognition accuracy.
        """
        w, h = image.size
        max_dim = max(w, h)

        if max_dim < 1200:
            scale = 2.2
        elif max_dim < 1800:
            scale = 1.7
        elif max_dim < 2600:
            scale = 1.3
        else:
            scale = 1.0

        if scale != 1.0:
            new_w = int(w * scale)
            new_h = int(h * scale)
            if max(new_w, new_h) > 2600:
                scale = 2600.0 / max_dim
                new_w = int(w * scale)
                new_h = int(h * scale)
            return image.resize((new_w, new_h), Image.Resampling.LANCZOS), scale

        return image, 1.0

    @classmethod
    def create_variants(cls, image_path: str) -> Tuple[Dict[str, Image.Image], bool]:
        """
        Produce a controlled set of 5 targeted preprocessing variants:
        A. original_rgb: Scaled color
        B. sharp_grayscale: Grayscale + autocontrast + unsharp mask (primary for text blocks)
        C. high_contrast: Grayscale + high contrast + median noise filter
        D. adaptive_thresh: Gaussian adaptive binarization for low contrast text
        E. color_enhanced: Contrast & sharpness enhanced RGB
        Returns dict of variants and boolean indicating if perspective was corrected.
        """
        with Image.open(image_path) as orig:
            oriented = cls.correct_orientation(orig)
            straightened, was_perspective_corrected = cls.detect_and_correct_perspective(oriented)

            if straightened.mode not in ('RGB', 'L'):
                straightened = straightened.convert('RGB')
            scaled, _ = cls.scale_image(straightened)

            # Variant A: Scaled original
            rgb_scaled = scaled.convert('RGB') if scaled.mode != 'RGB' else scaled

            # Variant B: Primary Grayscale + Autocontrast + Unsharp Mask
            gray = scaled.convert('L')
            auto_contrast = ImageOps.autocontrast(gray, cutoff=1)
            sharp_gray = auto_contrast.filter(
                ImageFilter.UnsharpMask(radius=1.5, percent=150, threshold=3)
            )

            # Variant C: High Contrast Denoised
            enhancer = ImageEnhance.Contrast(gray)
            high_contrast = enhancer.enhance(1.8).filter(ImageFilter.MedianFilter(size=3))

            # Variant D: Adaptive Thresholding via OpenCV
            try:
                gray_np = np.array(gray)
                adapt_np = cv2.adaptiveThreshold(
                    gray_np, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10
                )
                adaptive_thresh = Image.fromarray(adapt_np)
            except Exception:
                adaptive_thresh = sharp_gray

            # Variant E: Color Enhanced RGB
            color_sharp = ImageEnhance.Sharpness(rgb_scaled).enhance(1.4)
            color_enhanced = ImageEnhance.Contrast(color_sharp).enhance(1.2)

            variants = {
                'sharp_grayscale': sharp_gray,
                'high_contrast': high_contrast,
                'adaptive_thresh': adaptive_thresh,
                'color_enhanced': color_enhanced,
                'original_rgb': rgb_scaled
            }

            return variants, was_perspective_corrected

    @classmethod
    def create_stamp_variants(cls, stamp_crop: Image.Image) -> Dict[str, Image.Image]:
        """
        Step 2 & 3: Specialized preprocessing & targeted upscaling for stamp crops only.
        Generates 6 targeted variants for faint/dot-matrix text:
        A. grayscale + contrast
        B. CLAHE
        C. adaptive threshold
        D. Otsu threshold
        E. sharpened grayscale
        F. inverted threshold
        Applies intelligent 3x-5x Lanczos upscaling strictly to this small crop.
        """
        w, h = stamp_crop.size
        # Intelligent upscale: small crops get 3.5x - 4.5x, larger get 2.5x - 3.0x
        if max(w, h) < 400:
            scale_factor = 4.5
        elif max(w, h) < 800:
            scale_factor = 3.5
        elif max(w, h) < 1400:
            scale_factor = 2.5
        else:
            scale_factor = 1.8

        new_w = int(w * scale_factor)
        new_h = int(h * scale_factor)
        upscaled = stamp_crop.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Convert to Grayscale
        gray = upscaled.convert('L') if upscaled.mode != 'L' else upscaled
        gray_np = np.array(gray)

        # A. grayscale + contrast
        enhancer = ImageEnhance.Contrast(gray)
        var_contrast = enhancer.enhance(2.2)

        # B. CLAHE (Local adaptive histogram equalization)
        try:
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            var_clahe = Image.fromarray(clahe.apply(gray_np))
        except Exception:
            var_clahe = var_contrast

        # C. Adaptive threshold (Gaussian)
        try:
            adapt_arr = cv2.adaptiveThreshold(
                gray_np, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 5
            )
            var_adaptive = Image.fromarray(adapt_arr)
        except Exception:
            var_adaptive = gray

        # D. Otsu threshold
        try:
            _, otsu_arr = cv2.threshold(gray_np, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            var_otsu = Image.fromarray(otsu_arr)
        except Exception:
            var_otsu = gray

        # E. Sharpened grayscale
        var_sharp = gray.filter(ImageFilter.UnsharpMask(radius=2, percent=220, threshold=3))

        # F. Inverted threshold (light text on dark background / dot matrix)
        try:
            var_inv = ImageOps.invert(var_otsu)
        except Exception:
            var_inv = var_sharp

        return {
            'stamp_contrast': var_contrast,
            'stamp_clahe': var_clahe,
            'stamp_adaptive': var_adaptive,
            'stamp_otsu': var_otsu,
            'stamp_sharp': var_sharp,
            'stamp_inverted': var_inv
        }

