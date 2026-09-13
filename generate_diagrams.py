import os
from PIL import Image, ImageDraw, ImageFont

def create_pipeline_diagram(output_path: str):
    # Width x Height
    w, h = 1800, 750
    img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Try to load a nice font or default
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 34)
        font_subtitle = ImageFont.truetype("arial.ttf", 22)
        font_box_title = ImageFont.truetype("arialbd.ttf", 26)
        font_box_text = ImageFont.truetype("arial.ttf", 20)
        font_badge = ImageFont.truetype("arialbd.ttf", 18)
    except Exception:
        font_title = ImageFont.load_default()
        font_subtitle = font_title
        font_box_title = font_title
        font_box_text = font_title
        font_badge = font_title

    # Background subtle grid / gradient header
    draw.rectangle([(0, 0), (w, 100)], fill=(30, 41, 59))
    draw.text((40, 25), "METRCHECK AI — END-TO-END DATA PROCESSING & COMPLIANCE PIPELINE", fill=(255, 255, 255), font=font_title)
    draw.text((40, 65), "From Multi-Panel Packaging Image Ingestion to Audit-Grade Legal Dossier", fill=(148, 163, 184), font=font_subtitle)

    # Step boxes
    steps = [
        ("01", "INGESTION", "Multi-Panel Upload\nFront, Back, Sides\nFormat validation (10MB)", (238, 242, 255), (79, 70, 229), (67, 56, 202)),
        ("02", "PREPROCESS", "EXIF Orient, Quad Rect\nLanczos Upscaling\n5 Contrast Variants", (240, 253, 244), (22, 163, 74), (21, 128, 61)),
        ("03", "OCR & DETECT", "PaddleOCR PP-OCRv4\nDBNet + SVTR / Tess\n2D Spatial BBoxes", (254, 243, 199), (217, 119, 6), (180, 83, 9)),
        ("04", "EXTRACTION", "Anchored Regex\nFSSAI/Date Repair\nConfidence Scoring", (236, 253, 245), (13, 148, 136), (15, 118, 110)),
        ("05", "COMPLIANCE", "Legal Metrology Rules\nFSSAI Regs (LM/FS)\nRule 12 Font Height", (254, 242, 242), (225, 29, 72), (190, 18, 60)),
        ("06", "SCORING", "Weighted Points\nPass, Warn, Review, Fail\n0-100 Score & Verdict", (245, 243, 255), (147, 51, 234), (126, 34, 206)),
        ("07", "ENFORCE & REP", "Penalty Estimator\nShow-Cause Notice\nPDF, XLSX, CSV, JSON", (241, 245, 249), (71, 85, 105), (51, 65, 85)),
    ]

    card_w = 215
    card_h = 320
    spacing = 30
    start_x = 45
    start_y = 150

    for i, (num, title, desc, bg_col, border_col, text_col) in enumerate(steps):
        x = start_x + i * (card_w + spacing)
        y = start_y

        # Shadow
        draw.rounded_rectangle([(x+4, y+4), (x + card_w + 4, y + card_h + 4)], radius=16, fill=(226, 232, 240))
        # Card Background
        draw.rounded_rectangle([(x, y), (x + card_w, y + card_h)], radius=16, fill=bg_col, outline=border_col, width=3)
        
        # Step Badge
        draw.rounded_rectangle([(x + 15, y + 15), (x + 65, y + 50)], radius=8, fill=border_col)
        draw.text((x + 23, y + 20), num, fill=(255, 255, 255), font=font_badge)

        # Title
        draw.text((x + 15, y + 65), title, fill=text_col, font=font_box_title)
        draw.line([(x + 15, y + 105), (x + card_w - 15, y + 105)], fill=border_col, width=2)

        # Description
        draw.text((x + 15, y + 120), desc, fill=(51, 65, 85), font=font_box_text, spacing=8)

        # Draw arrow to next step
        if i < len(steps) - 1:
            arrow_x = x + card_w + 5
            arrow_y = y + card_h // 2
            draw.polygon([
                (arrow_x, arrow_y - 12),
                (arrow_x + 18, arrow_y),
                (arrow_x, arrow_y + 12)
            ], fill=(148, 163, 184))

    # Bottom summary bar / annotations
    draw.rounded_rectangle([(start_x, 505), (w - start_x, 705)], radius=14, fill=(248, 250, 252), outline=(203, 213, 225), width=2)
    
    col_w = (w - start_x*2 - 80) // 3
    
    # Feature 1
    f1_x = start_x + 25
    draw.text((f1_x, 525), "Deterministic AI & Legal Grounding", fill=(30, 41, 59), font=font_box_title)
    draw.text((f1_x, 565), "- Zero hallucination rule evaluators\n- 13 Codified Legal Rules (LM & FSSAI)\n- Direct legal statutory citations in audit log", fill=(71, 85, 105), font=font_box_text, spacing=6)
    
    # Feature 2
    f2_x = f1_x + col_w + 35
    draw.text((f2_x, 525), "Spatial 2D Bounding Box Evidence", fill=(30, 41, 59), font=font_box_title)
    draw.text((f2_x, 565), "- Coordinate tracking on original image\n- Real-time overlay in EvidenceViewer\n- Confidence score per extracted field", fill=(71, 85, 105), font=font_box_text, spacing=6)

    # Feature 3
    f3_x = f2_x + col_w + 35
    draw.text((f3_x, 525), "Regulatory Compliance Output", fill=(30, 41, 59), font=font_box_title)
    draw.text((f3_x, 565), "- Official ReportLab PDF inspection dossier\n- Multi-sheet Excel workbook (.xlsx)\n- Statutory Show-Cause notice generator", fill=(71, 85, 105), font=font_box_text, spacing=6)

    img.save(output_path, "PNG")
    print(f"Saved pipeline diagram: {output_path}")

def create_architecture_diagram(output_path: str):
    w, h = 1800, 850
    img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("arialbd.ttf", 34)
        font_subtitle = ImageFont.truetype("arial.ttf", 22)
        font_layer = ImageFont.truetype("arialbd.ttf", 26)
        font_header = ImageFont.truetype("arialbd.ttf", 22)
        font_text = ImageFont.truetype("arial.ttf", 19)
    except Exception:
        font_title = ImageFont.load_default()
        font_subtitle = font_title
        font_layer = font_title
        font_header = font_title
        font_text = font_title

    # Header
    draw.rectangle([(0, 0), (w, 100)], fill=(15, 23, 42))
    draw.text((40, 25), "METRCHECK AI — SYSTEM ARCHITECTURE & COMPONENT TOPOLOGY", fill=(255, 255, 255), font=font_title)
    draw.text((40, 65), "Modular Layer Separation: UI, API Gateway, Computer Vision, Rule Engine, and Storage", fill=(148, 163, 184), font=font_subtitle)

    # Layer 1: Presentation (Frontend)
    # Layer 2: API Gateway & Security
    # Layer 3: Core AI & Processing Services
    # Layer 4: Compliance & Legal Engine
    # Layer 5: Persistence & Export Layer

    layers = [
        ("LAYER 1: PRESENTATION LAYER (React 19 + TypeScript + Vite + Tailwind CSS v4)",
         [
             ("Pages & Dashboards", "Dashboard.tsx, Analyze.tsx (Multi-panel),\nAnalyzeListing.tsx, Results.tsx,\nHistory.tsx, DemoCases.tsx, AdminUsers.tsx"),
             ("Visual Components", "EvidenceViewer.tsx (2D BBoxes),\nScoreCircle, StatusBadge, SeverityBadge,\nLoadingSkeleton, Card, ThemeToggle"),
             ("State & Context", "AuthContext (JWT & Bearer Tokens),\nRoleContext (Admin/Officer/Merchant),\nThemeContext (Dark/Light mode)")
         ],
         (240, 249, 255), (2, 132, 199), (3, 105, 161)),

        ("LAYER 2: REST API GATEWAY & AUTHENTICATION (FastAPI Async Framework)",
         [
             ("API Routers (/api/*)", "analyze.py, ocr.py, extract.py,\ncompliance_routes.py, history.py,\ndemo.py, health.py, report.py, enforcement.py"),
             ("Auth & Security (auth/)", "PBKDF2-HMAC-SHA256 (200k iter),\nSigned HMAC-SHA256 Bearer tokens,\nRole-based guards (require_roles)"),
             ("Middleware & Config", "CORS Middleware, StaticFiles (/uploads),\nLifespan DB setup, Pydantic-Settings\nConfig with Test Isolation guards")
         ],
         (245, 243, 255), (147, 51, 234), (126, 34, 206)),

        ("LAYER 3: COMPUTER VISION, OCR & EXTRACTION ENGINE",
         [
             ("OCR Subsystem (ocr/)", "PaddleOCR PP-OCRv4 (DBNet+SVTR),\nDeep Learning Recognition & Angle Cls,\nMulti-pass Preprocessing & Orientation"),
             ("Region & Quality (ocr/)", "RegionDetector (Header/Mid/Stamp/Table),\nQualityAssessor (Blur, Brightness, Contrast),\nText Cleaner & FSSAI/Unit Repair"),
             ("Extraction (extraction/)", "LocalExtractor (High-recall regex),\nContextual validator, Confidence scoring,\nFSSAI 14-digit state/type decoder")
         ],
         (254, 243, 199), (217, 119, 6), (180, 83, 9)),

        ("LAYER 4: STATUTORY COMPLIANCE & LEGAL ENFORCEMENT ENGINE",
         [
             ("Rule Registry (compliance/)", "LM-001 to LM-009 (Packaged Commodities),\nFS-001 to FS-005 (FSSAI Regulations),\nRule 12 Font Height Calculator"),
             ("Scorer & Recommendations", "Weighted Compliance Formula,\nVerdict Categorization (Pass/Warn/Fail),\nDeterministic Corrective Action Engine"),
             ("Enforcement (enforcement/)", "LM Act 2009 Sec 36/38 Penalty Estimator,\nStatutory Show-Cause Notice Builder,\nAdvisory sanction guidelines")
         ],
         (254, 242, 242), (225, 29, 72), (190, 18, 60)),

        ("LAYER 5: DATA PERSISTENCE & MULTI-FORMAT EXPORT ENGINE",
         [
             ("SQLite Storage (database/)", "aiosqlite async database (metrc_check.db),\n'analyses' table (JSON-serialized payloads),\n'users' table (salted hashes & RBAC)"),
             ("Audit Dossiers (services/)", "ReportLab PDF Generator (multi-page),\nopenpyxl XLSX (3-sheet formatted Excel),\nStandard CSV & JSON ingestion endpoints"),
             ("Orchestration (services/)", "analysis_service.py (pipeline coordination),\nimage_service.py (disk persistence),\nrunner.py (multi-port supervisor)")
         ],
         (240, 253, 244), (22, 163, 74), (21, 128, 61)),
    ]

    y_pos = 125
    layer_h = 132
    layer_gap = 12
    margin_x = 40

    for title, boxes, bg_c, border_c, text_c in layers:
        # Layer container
        draw.rounded_rectangle([(margin_x, y_pos), (w - margin_x, y_pos + layer_h)], radius=12, fill=bg_c, outline=border_c, width=2)
        
        # Layer Header Banner
        draw.rounded_rectangle([(margin_x, y_pos), (w - margin_x, y_pos + 36)], radius=12, fill=border_c)
        draw.text((margin_x + 18, y_pos + 6), title, fill=(255, 255, 255), font=font_header)

        # 3 Sub-boxes
        sub_w = (w - margin_x * 2 - 40) // 3
        sub_y = y_pos + 46
        sub_h = layer_h - 54

        for j, (box_title, box_desc) in enumerate(boxes):
            bx = margin_x + 12 + j * (sub_w + 8)
            draw.rounded_rectangle([(bx, sub_y), (bx + sub_w, sub_y + sub_h)], radius=8, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
            draw.text((bx + 10, sub_y + 6), box_title, fill=text_c, font=font_header)
            draw.text((bx + 10, sub_y + 32), box_desc, fill=(71, 85, 105), font=font_text, spacing=4)

        y_pos += layer_h + layer_gap

    img.save(output_path, "PNG")
    print(f"Saved architecture diagram: {output_path}")

if __name__ == "__main__":
    os.makedirs("doc_assets", exist_ok=True)
    create_pipeline_diagram("doc_assets/pipeline_diagram.png")
    create_architecture_diagram("doc_assets/architecture_diagram.png")
