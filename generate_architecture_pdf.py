import os
import sys
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm, cm, inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage, PageBreak, HRFlowable, KeepTogether
)
from reportlab.pdfgen import canvas

# ── Color Palette ────────────────────────────────────────────────────────
COLOR_PRIMARY = colors.HexColor('#1e1b4b')     # Deep indigo / slate 950
COLOR_ACCENT = colors.HexColor('#4f46e5')      # Indigo 600
COLOR_ACCENT_LIGHT = colors.HexColor('#e0e7ff')# Indigo 100
COLOR_SECONDARY = colors.HexColor('#059669')   # Emerald 600
COLOR_SECONDARY_LIGHT = colors.HexColor('#d1fae5')
COLOR_WARNING = colors.HexColor('#d97706')     # Amber 600
COLOR_WARNING_LIGHT = colors.HexColor('#fef3c7')
COLOR_DANGER = colors.HexColor('#dc2626')      # Red 600
COLOR_DANGER_LIGHT = colors.HexColor('#fee2e2')
COLOR_TEXT_MAIN = colors.HexColor('#0f172a')   # Slate 900
COLOR_TEXT_MUTED = colors.HexColor('#475569')  # Slate 600
COLOR_BG_LIGHT = colors.HexColor('#f8fafc')    # Slate 50
COLOR_BG_CARD = colors.HexColor('#f1f5f9')     # Slate 100
COLOR_BORDER = colors.HexColor('#cbd5e1')      # Slate 300
COLOR_BORDER_LIGHT = colors.HexColor('#e2e8f0')# Slate 200

# ── Numbered Canvas with Running Headers & Footers ───────────────────────
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        page_w, page_h = A4

        # Skip headers/footers on page 1 (Cover Page)
        if self._pageNumber > 1:
            # Header
            self.setFont("Helvetica", 8)
            self.setFillColor(COLOR_TEXT_MUTED)
            self.drawString(36, page_h - 28, "METRCHECK AI — Complete Architecture & Code Flow Guide")
            self.drawRightString(page_w - 36, page_h - 28, "Smart India Hackathon SIH26034")

            self.setStrokeColor(COLOR_BORDER_LIGHT)
            self.setLineWidth(0.75)
            self.line(36, page_h - 34, page_w - 36, page_h - 34)

            # Footer
            self.line(36, 36, page_w - 36, 36)
            self.drawString(36, 24, "Legal Metrology & FSSAI Automated Compliance Engine | Technical Deep Dive")
            page_text = f"Page {self._pageNumber} of {page_count}"
            self.drawRightString(page_w - 36, 24, page_text)

        self.restoreState()


def build_pdf(filename: str):
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=44,
        bottomMargin=44
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=26,
        leading=32,
        textColor=COLOR_PRIMARY,
        alignment=TA_LEFT,
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=13,
        leading=17,
        textColor=COLOR_ACCENT,
        alignment=TA_LEFT,
        spaceAfter=14
    )

    h1_style = ParagraphStyle(
        'DocH1',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=COLOR_PRIMARY,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'DocH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=COLOR_ACCENT,
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True
    )

    h3_style = ParagraphStyle(
        'DocH3',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=COLOR_TEXT_MAIN,
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12.5,
        textColor=COLOR_TEXT_MAIN,
        spaceAfter=6
    )

    body_bold = ParagraphStyle(
        'DocBodyBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    body_muted = ParagraphStyle(
        'DocBodyMuted',
        parent=body_style,
        textColor=COLOR_TEXT_MUTED,
        fontSize=8.5,
        leading=11.5
    )

    callout_style = ParagraphStyle(
        'DocCallout',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=12,
        textColor=COLOR_TEXT_MAIN
    )

    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
        alignment=TA_LEFT
    )

    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10.5,
        textColor=COLOR_TEXT_MAIN
    )

    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=table_cell,
        fontName='Helvetica-Bold'
    )

    table_cell_code = ParagraphStyle(
        'TableCellCode',
        parent=table_cell,
        fontName='Courier',
        fontSize=7.5,
        leading=9.5,
        textColor=COLOR_ACCENT
    )
    table_cell_muted = ParagraphStyle(
        'TableCellMuted',
        parent=table_cell,
        textColor=COLOR_TEXT_MUTED
    )

    story = []

    # ═══════════════════════════════════════════════════════════════════════
    # COVER / TITLE HEADER BLOCK
    # ═══════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 10))

    # Badge Row
    badge_table_data = [[
        Paragraph("<font color='#4f46e5'><b>SMART INDIA HACKATHON 2026</b></font> | Problem Statement: <b>SIH26034</b>", body_style),
        Paragraph(f"Generated: <b>{datetime.now().strftime('%d %B %Y')}</b> | System Version: <b>1.0.0</b>", ParagraphStyle('RightDate', parent=body_style, alignment=TA_RIGHT))
    ]]
    badge_table = Table(badge_table_data, colWidths=[300, 223])
    badge_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_ACCENT_LIGHT),
        ('BOX', (0, 0), (-1, -1), 1, COLOR_ACCENT),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(badge_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("MetrCheck AI", title_style))
    story.append(Paragraph("Complete System Architecture, Code Flow &amp; Technical Reference Manual", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=COLOR_ACCENT, spaceBefore=0, spaceAfter=12))

    # Executive Overview Callout Box
    overview_html = """<b>EXECUTIVE SUMMARY:</b><br/>
    <b>MetrCheck AI</b> is an enterprise-grade, automated statutory compliance auditing and decision-support platform engineered specifically for pre-packaged commodities sold across retail and e-commerce platforms in India.
    Operating under the strict statutory mandates of the <b>Legal Metrology (Packaged Commodities) Rules, 2011</b> and the <b>Food Safety and Standards (Packaging and Labelling) Regulations, 2020</b>, the system bridges the gap between raw packaging artwork/images and verifiable legal compliance through deterministic multi-stage AI reasoning.
    <br/><br/>
    The system ingests multi-panel product photographs (Front, Back, Sides) or e-commerce listing descriptions, executes high-resolution computer vision preprocessing (EXIF, perspective rectification, Lanczos upscaling), performs multi-pass OCR via PaddleOCR PP-OCRv4 (DBNet + SVTR), extracts statutory packaging declarations via contextual pattern matching with automatic character repair, validates them against 14 codified statutory rules, computes explainable 0–100 compliance scores, produces prioritized manufacturer corrective guidance, estimates statutory legal penalties under Legal Metrology Act Sections 36 &amp; 38, generates court-ready show-cause notices, and exports multi-format inspection dossiers (ReportLab PDF, openpyxl XLSX, CSV, JSON).
    """
    callout_data = [[Paragraph(overview_html, callout_style)]]
    callout_table = Table(callout_data, colWidths=[523])
    callout_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_BG_LIGHT),
        ('BOX', (0, 0), (-1, -1), 1, COLOR_BORDER),
        ('LINELEFT', (0, 0), (0, -1), 4, COLOR_ACCENT),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(callout_table)
    story.append(Spacer(1, 14))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 1: HIGH-LEVEL ARCHITECTURE & TOPOLOGY
    # ═══════════════════════════════════════════════════════════════════════
    story.append(Paragraph("1. System Architecture &amp; Component Topology", h1_style))
    story.append(Paragraph(
        "MetrCheck AI is engineered with a strict 5-layer decoupled architecture ensuring complete separation of concerns, high throughput asynchronous processing, zero external runtime internet dependencies, and verifiable test isolation.",
        body_style
    ))

    if os.path.exists("doc_assets/architecture_diagram.png"):
        story.append(RLImage("doc_assets/architecture_diagram.png", width=523, height=247))
        story.append(Spacer(1, 10))

    # Layer Breakdown Table
    arch_table_data = [
        [Paragraph("Layer", table_header), Paragraph("Key Modules &amp; Technologies", table_header), Paragraph("Primary Architectural Responsibility", table_header)],
        [
            Paragraph("<b>Layer 1: Presentation</b>", table_cell),
            Paragraph("React 19, TypeScript, Vite, Tailwind CSS v4, Lucide React, Recharts", table_cell),
            Paragraph("Multi-panel drag-and-drop upload, 2D EvidenceViewer with bounding box overlays, compliance gauges, listing text paste screening, admin console.", table_cell)
        ],
        [
            Paragraph("<b>Layer 2: REST Gateway</b>", table_cell),
            Paragraph("FastAPI, Pydantic v2, Uvicorn, PBKDF2-HMAC-SHA256 Auth, HMAC-SHA256 Bearer", table_cell),
            Paragraph("Asynchronous REST API routing, Bearer token authentication, Role-Based Access Control (RBAC), CORS middleware, input payload validation.", table_cell)
        ],
        [
            Paragraph("<b>Layer 3: Vision &amp; OCR</b>", table_cell),
            Paragraph("PaddleOCR (PP-OCRv4 DBNet+SVTR), OpenCV, Pillow, NumPy", table_cell),
            Paragraph("EXIF orientation, quad perspective rectification, dynamic Lanczos scaling, 5 binary filter passes, 2D spatial coordinate tracking, OCR text cleaner &amp; repair.", table_cell)
        ],
        [
            Paragraph("<b>Layer 4: Compliance &amp; Legal</b>", table_cell),
            Paragraph("RuleRegistry, LM-001..LM-009, FS-001..FS-005, Scorer, Penalty Estimator", table_cell),
            Paragraph("Deterministic statutory evaluation, Rule 12 font height calculation, weighted point scoring, prioritized corrective actions, Sec 36/38 penalty brackets.", table_cell)
        ],
        [
            Paragraph("<b>Layer 5: Storage &amp; Export</b>", table_cell),
            Paragraph("aiosqlite (SQLite), ReportLab PDF, openpyxl XLSX, CSV, JSON", table_cell),
            Paragraph("Persistent screening audit logs, role-gated user database, multi-sheet formatted Excel generation, official multi-page PDF inspection reports.", table_cell)
        ]
    ]

    arch_table = Table(arch_table_data, colWidths=[90, 165, 268])
    arch_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT])
    ]))
    story.append(arch_table)
    story.append(Spacer(1, 14))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 2: END-TO-END DATA PROCESSING PIPELINE & CODE FLOW
    # ═══════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("2. End-to-End Data Processing Pipeline &amp; Code Execution Flow", h1_style))
    story.append(Paragraph(
        "Every packaging analysis undergoes a deterministic, high-throughput 7-stage execution pipeline coordinated by <font name='Courier' color='#4f46e5'>backend/services/analysis_service.py</font>.",
        body_style
    ))

    if os.path.exists("doc_assets/pipeline_diagram.png"):
        story.append(RLImage("doc_assets/pipeline_diagram.png", width=523, height=218))
        story.append(Spacer(1, 10))

    pipeline_steps = [
        ("Stage 1: Multi-Panel Ingestion &amp; Image Validation",
         "API endpoint <code>POST /api/analyze</code> receives 1 to 4 upload files labeled as 'Front', 'Back', 'Side 1', 'Side 2'. "
         "<code>utils/validators.py:validate_image_file()</code> enforces MIME type whitelist (PNG, JPEG, JPG, WebP) and 10MB maximum file size. "
         "<code>services/image_service.py:process_and_save_image()</code> writes sanitized files to <code>backend/uploads/</code> with unique UUIDs."),

        ("Stage 2: Advanced Computer Vision Preprocessing",
         "<code>ocr/preprocessing.py:ImagePreprocessor</code> executes non-destructive image enhancements: "
         "(1) <i>EXIF Transposition</i> to normalize rotated phone snapshots; "
         "(2) <i>Perspective Rectification</i> using OpenCV Canny edges, contour polygon approximation, and 4-point homography warp; "
         "(3) <i>Dynamic Lanczos Upscaling</i> (scale factor up to 2.8x for labels under 1200px); "
         "(4) Generation of 5 targeted multi-pass variants (Grayscale, Otsu Adaptive, CLAHE High-Contrast, Morphological Opening, and Deskewed)."),

        ("Stage 3: Multi-Pass OCR &amp; Spatial Bounding Box Extraction",
         "<code>ocr/factory.py:get_ocr_engine()</code> initializes PaddleOCR (PP-OCRv4 deep learning with DBNet detection &amp; SVTR recognition). "
         "Extracts recognized text lines, confidence scores, and 2D bounding boxes <code>[ymin, xmin, ymax, xmax]</code> for every word. "
         "<code>ocr/quality.py</code> computes blur (Laplacian variance), brightness, and contrast diagnostics to warn users of degraded photography."),

        ("Stage 4: OCR Normalization &amp; Character Repair",
         "<code>ocr/cleaner.py:clean_ocr_text()</code> eliminates unicode replacement artifacts while strictly preserving currency symbols (₹, Rs.), decimals, units, and dates. "
         "<code>ocr/repair.py</code> applies contextual heuristics: auto-corrects FSSAI transposed letters (<code>O/I/l/S/B/G/Z</code> $\to$ <code>0/1/1/5/8/6/2</code>), fixes Net Qty '9' $\to$ 'g', and cleans MRP/date delimiters."),

        ("Stage 5: Structured Information Extraction",
         "<code>extraction/extractor.py:LocalExtractor</code> runs anchored statutory regex patterns (<code>patterns.py</code>) to extract: "
         "Product Name, Brand, Manufacturer/Packer with PIN code, Net Quantity, MRP, Mfg/Exp/Use-By Dates, Batch Number, FSSAI Licence, Consumer Care Phone/Email, Country of Origin, Ingredients, Nutrition table, and Barcodes. "
         "Computes dynamic confidence scores per declaration and decodes FSSAI state codes."),

        ("Stage 6: Codified Statutory Compliance Evaluation",
         "<code>compliance/engine.py:ComplianceEngine</code> checks all 14 statutory rules (LM-001..009 and FS-001..005). "
         "<code>compliance/rules/legal_metrology.py:compute_font_size_and_readability()</code> measures pixel-to-millimeter font height against Rule 12 statutory minimums based on package net quantity. "
         "<code>compliance/scorer.py:calculate_score()</code> evaluates weighted points (PASS=1.0, WARN=0.5, REVIEW=0.85, FAIL=0.0) to generate the final 0–100 score and categorical status."),

        ("Stage 7: Report &amp; Enforcement Artefact Generation",
         "<code>compliance/recommendations.py</code> builds prioritized manufacturer corrective actions with statutory citations. "
         "<code>enforcement/penalties.py</code> calculates Legal Metrology Act Sec 36/38 penalty brackets and generates court-ready show-cause notices. "
         "<code>services/report_service.py</code> and <code>backend/api/report.py</code> generate downloadable PDF, XLSX, CSV, and JSON audit dossiers. Record is saved to SQLite <code>analyses</code> table.")
    ]

    for title, desc in pipeline_steps:
        story.append(Paragraph(title, h3_style))
        story.append(Paragraph(desc, body_style))

    story.append(Spacer(1, 10))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 3: STATUTORY RULES MATRIX & SCORING MATHEMATICS
    # ═══════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("3. Statutory Compliance Rules Matrix &amp; Scoring Mathematics", h1_style))
    story.append(Paragraph(
        "MetrCheck AI codifies 14 statutory compliance rules split across two regulatory domains: <b>Legal Metrology</b> (Department of Consumer Affairs) and <b>FSSAI</b> (Food Safety and Standards Authority of India).",
        body_style
    ))

    if os.path.exists("doc_assets/compliance_tree_diagram.png"):
        story.append(RLImage("doc_assets/compliance_tree_diagram.png", width=523, height=226))
        story.append(Spacer(1, 10))

    # Scoring Formula Box
    formula_html = """<b>STATUTORY COMPLIANCE SCORING FORMULA:</b><br/>
    $$\\text{Compliance Score} = \\left( \\frac{1.0 \\times N_{\\text{PASS}} + 0.5 \\times N_{\\text{WARNING}} + 0.85 \\times N_{\\text{NEEDS\\_REVIEW}} + 0.0 \\times N_{\\text{FAIL}}}{N_{\\text{Applicable Rules}}} \\right) \\times 100$$
    <br/>
    <b>Classification Verdict Logic:</b><br/>
    &bull; <b>POTENTIAL NON-COMPLIANCE:</b> Assigned if $N_{\\text{FAIL}} \\ge 1$ (any confirmed mandatory declaration missing/illegal).<br/>
    &bull; <b>REVIEW REQUIRED:</b> Assigned if $N_{\\text{FAIL}} = 0$ but $N_{\\text{NEEDS\\_REVIEW}} \\ge 1$ or overall score &lt; 80.0%.<br/>
    &bull; <b>COMPLIANT:</b> Assigned if $N_{\\text{FAIL}} = 0$, $N_{\\text{NEEDS\\_REVIEW}} = 0$, and overall score $\\ge 80.0\\%$.<br/>
    &bull; <i>Note:</i> Rules evaluated as <font color='#64748b'><b>NOT_APPLICABLE</b></font> (e.g. FSSAI rules on non-food goods) are completely excluded from the denominator.
    """
    f_table = Table([[Paragraph(formula_html, callout_style)]], colWidths=[523])
    f_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_BG_LIGHT),
        ('BOX', (0, 0), (-1, -1), 1, COLOR_BORDER),
        ('LINELEFT', (0, 0), (0, -1), 4, COLOR_SECONDARY),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(f_table)
    story.append(Spacer(1, 10))

    # Rules Detail Table
    rules_data = [
        [Paragraph("Rule ID", table_header), Paragraph("Domain", table_header), Paragraph("Statutory Source &amp; Clause", table_header), Paragraph("Requirement &amp; Verification Criteria", table_header), Paragraph("Severity", table_header)],
        [
            Paragraph("<b>LM-001</b>", table_cell_bold),
            Paragraph("Legal Metrology", table_cell),
            Paragraph("Rule 6(1)(a), LM (PC) Rules 2011", table_cell),
            Paragraph("Name &amp; complete physical address of Manufacturer, Packer, or Importer with valid PIN code.", table_cell),
            Paragraph("<font color='#dc2626'><b>HIGH</b></font>", table_cell)
        ],
        [
            Paragraph("<b>LM-002</b>", table_cell_bold),
            Paragraph("Legal Metrology", table_cell),
            Paragraph("Rule 6(1)(b), LM (PC) Rules 2011", table_cell),
            Paragraph("Generic / common commodity name conspicuously declared on principal display panel.", table_cell),
            Paragraph("<font color='#d97706'><b>MEDIUM</b></font>", table_cell)
        ],
        [
            Paragraph("<b>LM-003</b>", table_cell_bold),
            Paragraph("Legal Metrology", table_cell),
            Paragraph("Rule 6(1)(c) &amp; Rule 12, LM Rules", table_cell),
            Paragraph("Net quantity in standard metric units (g, kg, ml, l, pcs, N). Flags non-standard units (gms, kgs, ltr).", table_cell),
            Paragraph("<font color='#dc2626'><b>HIGH</b></font>", table_cell)
        ],
        [
            Paragraph("<b>LM-004</b>", table_cell_bold),
            Paragraph("Legal Metrology", table_cell),
            Paragraph("Rule 6(1)(e), LM (PC) Rules 2011", table_cell),
            Paragraph("Maximum Retail Price (MRP) in INR with explicit 'Inclusive of all taxes' declaration.", table_cell),
            Paragraph("<font color='#dc2626'><b>HIGH</b></font>", table_cell)
        ],
        [
            Paragraph("<b>LM-005</b>", table_cell_bold),
            Paragraph("Legal Metrology", table_cell),
            Paragraph("Rule 6(1)(f), LM (PC) Rules 2011", table_cell),
            Paragraph("Consumer Care Helpline details: Contact name, physical address, toll-free telephone, and email.", table_cell),
            Paragraph("<font color='#dc2626'><b>HIGH</b></font>", table_cell)
        ],
        [
            Paragraph("<b>LM-006</b>", table_cell_bold),
            Paragraph("Legal Metrology", table_cell),
            Paragraph("Rule 6(1)(d), LM (PC) Rules 2011", table_cell),
            Paragraph("Country of Origin clearly declared on packages (e.g. 'Made in India', 'Country of Origin: USA').", table_cell),
            Paragraph("<font color='#d97706'><b>MEDIUM</b></font>", table_cell)
        ],
        [
            Paragraph("<b>LM-007</b>", table_cell_bold),
            Paragraph("Legal Metrology", table_cell),
            Paragraph("Rule 6(11), LM (PC) Rules 2011", table_cell),
            Paragraph("Unit Sale Price (USP) per g/kg/ml for packages containing more than 1 unit/kg.", table_cell),
            Paragraph("<font color='#475569'><b>LOW</b></font>", table_cell)
        ],
        [
            Paragraph("<b>LM-008</b>", table_cell_bold),
            Paragraph("Legal Metrology", table_cell),
            Paragraph("Rule 6(1)(d), LM (PC) Rules 2011", table_cell),
            Paragraph("Month and Year of Manufacture, Pre-packing, or Import in valid MM/YYYY or MM/YY format.", table_cell),
            Paragraph("<font color='#dc2626'><b>HIGH</b></font>", table_cell)
        ],
        [
            Paragraph("<b>LM-009</b>", table_cell_bold),
            Paragraph("Legal Metrology", table_cell),
            Paragraph("Rule 6(1)(e) &amp; Rule 12 Font Height", table_cell),
            Paragraph("Misleading statement detection and Net Quantity font height verification against statutory thresholds.", table_cell),
            Paragraph("<font color='#d97706'><b>MEDIUM</b></font>", table_cell)
        ],
        [
            Paragraph("<b>FS-001</b>", table_cell_bold),
            Paragraph("FSSAI", table_cell),
            Paragraph("FSS (Packaging &amp; Labelling) 2020", table_cell),
            Paragraph("14-digit FSSAI licence number starting with 1 or 2 alongside the official FSSAI logo.", table_cell),
            Paragraph("<font color='#dc2626'><b>HIGH</b></font>", table_cell)
        ],
        [
            Paragraph("<b>FS-002</b>", table_cell_bold),
            Paragraph("FSSAI", table_cell),
            Paragraph("FSS (Packaging &amp; Labelling) 2020", table_cell),
            Paragraph("Standardized food product denomination indicating true nature and physical state of food.", table_cell),
            Paragraph("<font color='#d97706'><b>MEDIUM</b></font>", table_cell)
        ],
        [
            Paragraph("<b>FS-003</b>", table_cell_bold),
            Paragraph("FSSAI", table_cell),
            Paragraph("FSS (Packaging &amp; Labelling) 2020", table_cell),
            Paragraph("Ingredients listed under heading 'Ingredients:' in descending order of in-going weight or volume.", table_cell),
            Paragraph("<font color='#d97706'><b>MEDIUM</b></font>", table_cell)
        ],
        [
            Paragraph("<b>FS-004</b>", table_cell_bold),
            Paragraph("FSSAI", table_cell),
            Paragraph("FSS (Packaging &amp; Labelling) 2020", table_cell),
            Paragraph("Nutrition Information Panel per 100g/serving: Energy (kcal), Protein, Carbohydrate, Total Sugars, Fats.", table_cell),
            Paragraph("<font color='#dc2626'><b>HIGH</b></font>", table_cell)
        ],
        [
            Paragraph("<b>FS-005</b>", table_cell_bold),
            Paragraph("FSSAI", table_cell),
            Paragraph("FSS (Packaging &amp; Labelling) 2020", table_cell),
            Paragraph("Date marking: 'Best Before' or 'Expiry Date' with day/month/year or relative shelf life declaration.", table_cell),
            Paragraph("<font color='#dc2626'><b>HIGH</b></font>", table_cell)
        ],
    ]

    rules_tbl = Table(rules_data, colWidths=[55, 75, 120, 225, 48])
    rules_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT])
    ]))
    story.append(rules_tbl)
    story.append(Spacer(1, 14))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 4: SECURITY ARCHITECTURE & ROLE-BASED ACCESS CONTROL (RBAC)
    # ═══════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("4. Security Architecture &amp; Role-Based Access Control (RBAC)", h1_style))
    story.append(Paragraph(
        "MetrCheck AI implements an enterprise-grade security sub-system built entirely on Python standard library cryptography (zero third-party dependencies like PyJWT or passlib).",
        body_style
    ))

    if os.path.exists("doc_assets/rbac_security_diagram.png"):
        story.append(RLImage("doc_assets/rbac_security_diagram.png", width=523, height=209))
        story.append(Spacer(1, 10))

    sec_desc = """
    <b>Cryptographic Primitives (backend/auth/security.py):</b><br/>
    &bull; <b>Password Storage:</b> Passwords are never stored in plaintext. They are salted with <code>os.urandom(16)</code> and hashed via <b>PBKDF2-HMAC-SHA256</b> with <b>200,000 iterations</b>. Verification uses <code>hmac.compare_digest</code> to prevent timing attacks.<br/>
    &bull; <b>Token Generation &amp; Signing:</b> State-less bearer tokens are signed with <b>HMAC-SHA256</b> using the server's <code>SECRET_KEY</code>. Tokens encode username, role, issue time, and expiration timestamp (default 480 minutes / 8 hours).<br/>
    &bull; <b>Role Hierarchy &amp; Route Guards:</b> <code>require_roles(*roles)</code> dependency injects role enforcement at the FastAPI router level.
    """
    s_table = Table([[Paragraph(sec_desc, callout_style)]], colWidths=[523])
    s_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_BG_LIGHT),
        ('BOX', (0, 0), (-1, -1), 1, COLOR_BORDER),
        ('LINELEFT', (0, 0), (0, -1), 4, COLOR_SECONDARY),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(s_table)
    story.append(Spacer(1, 10))

    # RBAC Matrix Table
    rbac_data = [
        [Paragraph("Feature / Endpoint Capability", table_header), Paragraph("ADMIN", table_header), Paragraph("ENFORCEMENT_OFFICER", table_header), Paragraph("MERCHANT_PUBLIC", table_header)],
        [Paragraph("Multi-Panel Packaging Image Upload &amp; OCR Analysis", table_cell), Paragraph("Yes", table_cell_bold), Paragraph("Yes", table_cell_bold), Paragraph("Yes", table_cell_bold)],
        [Paragraph("E-Commerce Listing Text Screening (/api/extract, /api/compliance/check)", table_cell), Paragraph("Yes", table_cell_bold), Paragraph("Yes", table_cell_bold), Paragraph("Yes", table_cell_bold)],
        [Paragraph("Rule Registry Inspection (/api/compliance/rules)", table_cell), Paragraph("Yes", table_cell_bold), Paragraph("Yes", table_cell_bold), Paragraph("Yes", table_cell_bold)],
        [Paragraph("Download PDF / XLSX / CSV / JSON Compliance Reports", table_cell), Paragraph("Yes", table_cell_bold), Paragraph("Yes", table_cell_bold), Paragraph("Yes", table_cell_bold)],
        [Paragraph("View Inspection Audit History &amp; Trends (/api/history, /api/stats)", table_cell), Paragraph("Yes", table_cell_bold), Paragraph("Yes", table_cell_bold), Paragraph("No", table_cell_muted)],
        [Paragraph("LM Act 2009 Sec 36/38 Statutory Penalty Estimator (/api/enforcement/penalty)", table_cell), Paragraph("Yes", table_cell_bold), Paragraph("Yes", table_cell_bold), Paragraph("No", table_cell_muted)],
        [Paragraph("Court-Ready Show-Cause Notice Generator (/api/enforcement/notice)", table_cell), Paragraph("Yes", table_cell_bold), Paragraph("Yes", table_cell_bold), Paragraph("No", table_cell_muted)],
        [Paragraph("Delete Individual Analysis Record (DELETE /api/history/{id})", table_cell), Paragraph("Yes", table_cell_bold), Paragraph("Yes", table_cell_bold), Paragraph("No", table_cell_muted)],
        [Paragraph("Purge All Audit History Records (DELETE /api/history)", table_cell), Paragraph("Yes", table_cell_bold), Paragraph("No", table_cell_muted), Paragraph("No", table_cell_muted)],
        [Paragraph("User Management Console (Create/Edit/Delete Accounts, Reset Passwords)", table_cell), Paragraph("Yes", table_cell_bold), Paragraph("No", table_cell_muted), Paragraph("No", table_cell_muted)],
    ]

    rbac_tbl = Table(rbac_data, colWidths=[205, 106, 106, 106])
    rbac_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT])
    ]))
    story.append(rbac_tbl)
    story.append(Spacer(1, 14))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 5: COMPLETE CODEBASE INVENTORY & FILE MAP
    # ═══════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("5. Complete Codebase Directory &amp; File Inventory", h1_style))
    story.append(Paragraph(
        "Complete technical mapping of all source files in the repository across backend micro-services, OCR modules, compliance rules, database layers, and the React frontend.",
        body_style
    ))

    file_map_data = [
        [Paragraph("Path / Module", table_header), Paragraph("Type", table_header), Paragraph("Functional Description &amp; Exported Symbols", table_header)],
        # Backend Core
        [Paragraph("backend/main.py", table_cell_code), Paragraph("Backend", table_cell), Paragraph("FastAPI app entrypoint, lifespan startup (init_db), CORS middleware, static mounts (/uploads), router inclusions.", table_cell)],
        [Paragraph("backend/config.py", table_cell_code), Paragraph("Backend", table_cell), Paragraph("Pydantic-Settings Settings class. Controls OCR_ENGINE, DATABASE_PATH, UPLOAD_DIR, TEST_MODE, and test isolation checks.", table_cell)],
        [Paragraph("backend/database/db.py", table_cell_code), Paragraph("Database", table_cell), Paragraph("aiosqlite async operations: init_db(), save_analysis(), get_analyses(), delete_analysis(), create_user(), update_user(), delete_user(), search_analyses(), seed_default_users().", table_cell)],
        [Paragraph("backend/models/schemas.py", table_cell_code), Paragraph("Schemas", table_cell), Paragraph("Pydantic models: OCRWord, OCRResult, ProductInfo, ComplianceCheck, ComplianceResult, Recommendation, ProductImageEvidence, FontSizeAnalysis, AnalysisResponse, HistoryItem.", table_cell)],
        
        # OCR
        [Paragraph("backend/ocr/factory.py", table_cell_code), Paragraph("OCR", table_cell), Paragraph("get_ocr_engine() singleton factory. Initializes and returns PaddleOCREngine.", table_cell)],
        [Paragraph("backend/ocr/paddle_engine.py", table_cell_code), Paragraph("OCR", table_cell), Paragraph("PaddleOCR PP-OCRv4 implementation with OneDNN Windows flags workaround, bounding box extraction, and confidence aggregation.", table_cell)],
        [Paragraph("backend/ocr/preprocessing.py", table_cell_code), Paragraph("CV Pipeline", table_cell), Paragraph("EXIF transpose, perspective/quad detection and homography rectification, dynamic Lanczos upscaling (1.6x-2.8x), and 5 filter variants.", table_cell)],
        [Paragraph("backend/ocr/cleaner.py", table_cell_code), Paragraph("CV Pipeline", table_cell), Paragraph("clean_ocr_text(): Strips stray punctuation while preserving currency (₹), numbers, dates, units, and FSSAI keywords.", table_cell)],
        [Paragraph("backend/ocr/repair.py", table_cell_code), Paragraph("CV Pipeline", table_cell), Paragraph("Specialized repair heuristics: repair_fssai_license() (swapped glyphs), repair_net_quantity(), repair_mrp(), repair_date(), repair_batch_number().", table_cell)],
        [Paragraph("backend/ocr/quality.py", table_cell_code), Paragraph("CV Pipeline", table_cell), Paragraph("assess_image_quality(): Computes blur score (Laplacian variance), brightness, contrast, and resolution diagnostics.", table_cell)],
        [Paragraph("backend/ocr/regions.py", table_cell_code), Paragraph("CV Pipeline", table_cell), Paragraph("RegionDetector: Contour &amp; morph-based segmentation for Brand Header, Middle Statutory, Bottom Stamp, and Nutrition tables.", table_cell)],

        # Extraction & Compliance
        [Paragraph("backend/extraction/extractor.py", table_cell_code), Paragraph("Extraction", table_cell), Paragraph("LocalExtractor: High-recall contextual regex parser for all statutory declarations with dynamic confidence scoring.", table_cell)],
        [Paragraph("backend/extraction/patterns.py", table_cell_code), Paragraph("Extraction", table_cell), Paragraph("Compiled regex dictionaries PATTERNS and FALLBACK_PATTERNS for MRP, Net Qty, Dates, FSSAI, Consumer Care, Origin, Mfr.", table_cell)],
        [Paragraph("backend/compliance/engine.py", table_cell_code), Paragraph("Compliance", table_cell), Paragraph("ComplianceEngine: Dispatches product declarations to codified rule evaluators, aggregates checks, and triggers recommendations.", table_cell)],
        [Paragraph("backend/compliance/rules/legal_metrology.py", table_cell_code), Paragraph("Compliance", table_cell), Paragraph("Rule evaluators evaluate_lm_001..009 + compute_font_size_and_readability() for Rule 12 font heights.", table_cell)],
        [Paragraph("backend/compliance/rules/fssai.py", table_cell_code), Paragraph("Compliance", table_cell), Paragraph("Rule evaluators evaluate_fs_001..005 for food commodities.", table_cell)],
        [Paragraph("backend/compliance/scorer.py", table_cell_code), Paragraph("Compliance", table_cell), Paragraph("calculate_score(): Implements weighted compliance points formula and status classification.", table_cell)],
        [Paragraph("backend/compliance/recommendations.py", table_cell_code), Paragraph("Compliance", table_cell), Paragraph("Deterministic corrective guidance engine mapping all 14 statutory rules to actionable legal advice.", table_cell)],
        [Paragraph("backend/enforcement/penalties.py", table_cell_code), Paragraph("Enforcement", table_cell), Paragraph("estimate_penalty() (LM Act Sec 36/38 fines) and generate_show_cause() (statutory legal notice formatting).", table_cell)],

        # API & Services
        [Paragraph("backend/api/analyze.py", table_cell_code), Paragraph("API", table_cell), Paragraph("POST /api/analyze (multi-panel upload) &amp; POST /api/analyze/text (raw text analysis).", table_cell)],
        [Paragraph("backend/api/report.py", table_cell_code), Paragraph("API", table_cell), Paragraph("GET /api/report/{id} (PDF), /csv (CSV), /xlsx (openpyxl Excel), /json (JSON).", table_cell)],
        [Paragraph("backend/services/report_service.py", table_cell_code), Paragraph("Service", table_cell), Paragraph("generate_pdf_report(): 768-line ReportLab PDF builder with styled tables, score badges, and legal citations.", table_cell)],

        # Frontend Core
        [Paragraph("frontend/src/App.tsx", table_cell_code), Paragraph("Frontend", table_cell), Paragraph("React Router v7 routes, RequireAuth and AdminOnly navigation guards, Theme/Auth/Role provider wrappers.", table_cell)],
        [Paragraph("frontend/src/services/api.ts", table_cell_code), Paragraph("Frontend", table_cell), Paragraph("Centralized API client: login, register, getUsers, analyzeProducts, getHistory, estimatePenalty, extractText, checkCompliance.", table_cell)],
        [Paragraph("frontend/src/components/EvidenceViewer.tsx", table_cell_code), Paragraph("Frontend", table_cell), Paragraph("Interactive packaging image viewer with scaled 2D bounding boxes, confidence badges, and panel switching.", table_cell)],
        [Paragraph("frontend/src/pages/Analyze.tsx", table_cell_code), Paragraph("Frontend", table_cell), Paragraph("4-slot multi-panel packaging upload (Front, Back, Side 1, Side 2) with drag-and-drop and camera capture.", table_cell)],
        [Paragraph("frontend/src/pages/AnalyzeListing.tsx", table_cell_code), Paragraph("Frontend", table_cell), Paragraph("E-commerce listing text screening mode with sample loader, declaration grid, and inline rule checklist.", table_cell)],
        [Paragraph("frontend/src/pages/Results.tsx", table_cell_code), Paragraph("Frontend", table_cell), Paragraph("1771-line comprehensive audit dossier page: EvidenceViewer, score circle, rule matrix, penalty calculator, show-cause modal, multi-format export triggers.", table_cell)],
        [Paragraph("runner.py", table_cell_code), Paragraph("Automation", table_cell), Paragraph("Unified multi-service runner: clears ports 5173/8000, detects LAN IP, prints QR code, and supervises backend+frontend processes.", table_cell)]
    ]

    file_tbl = Table(file_map_data, colWidths=[155, 60, 308])
    file_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT])
    ]))
    story.append(file_tbl)
    story.append(Spacer(1, 14))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 6: COMPLETE REST API REFERENCE
    # ═══════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("6. REST API Specifications &amp; Endpoints Reference", h1_style))
    story.append(Paragraph(
        "Comprehensive inventory of all backend REST endpoints hosted under the <font name='Courier' color='#4f46e5'>/api</font> prefix.",
        body_style
    ))

    api_ref_data = [
        [Paragraph("HTTP", table_header), Paragraph("Endpoint Path", table_header), Paragraph("Auth Level", table_header), Paragraph("Request Payload / Parameters", table_header), Paragraph("Response Description", table_header)],
        [Paragraph("POST", table_cell_bold), Paragraph("/api/analyze", table_cell_code), Paragraph("Public / Any", table_cell), Paragraph("Multipart: files (1-4 images), labels (JSON array)", table_cell), Paragraph("AnalysisResponse (complete audit payload)", table_cell)],
        [Paragraph("POST", table_cell_bold), Paragraph("/api/analyze/text", table_cell_code), Paragraph("Public / Any", table_cell), Paragraph("JSON: { text: string }", table_cell), Paragraph("AnalysisResponse (without images)", table_cell)],
        [Paragraph("POST", table_cell_bold), Paragraph("/api/ocr", table_cell_code), Paragraph("Public / Any", table_cell), Paragraph("Multipart: file (single image)", table_cell), Paragraph("OCRResult (raw text, words, bounding boxes)", table_cell)],
        [Paragraph("POST", table_cell_bold), Paragraph("/api/extract", table_cell_code), Paragraph("Public / Any", table_cell), Paragraph("JSON: { text: string }", table_cell), Paragraph("ProductInfo (extracted statutory fields)", table_cell)],
        [Paragraph("POST", table_cell_bold), Paragraph("/api/compliance/check", table_cell_code), Paragraph("Public / Any", table_cell), Paragraph("JSON: ProductInfo object", table_cell), Paragraph("ComplianceResult (checks, score, recs)", table_cell)],
        [Paragraph("GET", table_cell_bold), Paragraph("/api/compliance/rules", table_cell_code), Paragraph("Public / Any", table_cell), Paragraph("None", table_cell), Paragraph("List of all 14 RuleDefinition objects", table_cell)],
        [Paragraph("GET", table_cell_bold), Paragraph("/api/demo/cases", table_cell_code), Paragraph("Public / Any", table_cell), Paragraph("None", table_cell), Paragraph("Catalog of 3 benchmark test cases", table_cell)],
        [Paragraph("GET", table_cell_bold), Paragraph("/api/demo/{case_id}", table_cell_code), Paragraph("Public / Any", table_cell), Paragraph("Path: case_id ('1', '2', or '3')", table_cell), Paragraph("In-memory demo AnalysisResponse", table_cell)],
        [Paragraph("GET", table_cell_bold), Paragraph("/api/history", table_cell_code), Paragraph("Bearer Token", table_cell), Paragraph("None", table_cell), Paragraph("List of real user screening HistoryItem records", table_cell)],
        [Paragraph("GET", table_cell_bold), Paragraph("/api/history/{id}", table_cell_code), Paragraph("Public / Any", table_cell), Paragraph("Path: id (UUID or demo ID)", table_cell), Paragraph("AnalysisResponse for requested ID", table_cell)],
        [Paragraph("DELETE", table_cell_bold), Paragraph("/api/history/{id}", table_cell_code), Paragraph("Officer / Admin", table_cell), Paragraph("Path: id", table_cell), Paragraph("Deletes analysis record and image files", table_cell)],
        [Paragraph("DELETE", table_cell_bold), Paragraph("/api/history", table_cell_code), Paragraph("Admin Only", table_cell), Paragraph("None", table_cell), Paragraph("Purges all user analysis history from database", table_cell)],
        [Paragraph("GET", table_cell_bold), Paragraph("/api/stats", table_cell_code), Paragraph("Bearer Token", table_cell), Paragraph("None", table_cell), Paragraph("DashboardStats (counts, avg score, recent)", table_cell)],
        [Paragraph("GET", table_cell_bold), Paragraph("/api/stats/trends", table_cell_code), Paragraph("Bearer Token", table_cell), Paragraph("Query: days (int, 7-90, default 14)", table_cell), Paragraph("Daily compliance counts for Recharts trends", table_cell)],
        [Paragraph("GET", table_cell_bold), Paragraph("/api/report/{id}", table_cell_code), Paragraph("Public / Any", table_cell), Paragraph("Path: id", table_cell), Paragraph("Downloadable ReportLab PDF document", table_cell)],
        [Paragraph("GET", table_cell_bold), Paragraph("/api/report/{id}/xlsx", table_cell_code), Paragraph("Public / Any", table_cell), Paragraph("Path: id", table_cell), Paragraph("Downloadable openpyxl 3-sheet Excel (.xlsx)", table_cell)],
        [Paragraph("GET", table_cell_bold), Paragraph("/api/report/{id}/csv", table_cell_code), Paragraph("Public / Any", table_cell), Paragraph("Path: id", table_cell), Paragraph("Downloadable CSV spreadsheet report", table_cell)],
        [Paragraph("POST", table_cell_bold), Paragraph("/api/enforcement/penalty", table_cell_code), Paragraph("Officer / Admin", table_cell), Paragraph("JSON: { analysis_id, repeat_offence, prior_notices }", table_cell), Paragraph("PenaltyEstimate (Sec 36/38 fine bracket)", table_cell)],
        [Paragraph("POST", table_cell_bold), Paragraph("/api/enforcement/notice", table_cell_code), Paragraph("Officer / Admin", table_cell), Paragraph("JSON: { analysis_id, notice_reference, officer_name }", table_cell), Paragraph("ShowCauseNotice (formatted legal notice)", table_cell)],
        [Paragraph("POST", table_cell_bold), Paragraph("/api/auth/login", table_cell_code), Paragraph("Public / Any", table_cell), Paragraph("JSON: { username, password }", table_cell), Paragraph("AuthResponse: { token, user: UserOut }", table_cell)],
        [Paragraph("POST", table_cell_bold), Paragraph("/api/auth/register", table_cell_code), Paragraph("Public / Any", table_cell), Paragraph("JSON: { username, password, full_name, role }", table_cell), Paragraph("AuthResponse (creates public merchant)", table_cell)],
        [Paragraph("POST", table_cell_bold), Paragraph("/api/auth/users", table_cell_code), Paragraph("Admin Only", table_cell), Paragraph("JSON: { username, password, role, jurisdiction }", table_cell), Paragraph("Creates officer or merchant account", table_cell)],
        [Paragraph("PUT", table_cell_bold), Paragraph("/api/auth/users/{username}", table_cell_code), Paragraph("Admin Only", table_cell), Paragraph("JSON: { full_name, jurisdiction, role, new_password }", table_cell), Paragraph("Updates user account / resets password", table_cell)],
        [Paragraph("DELETE", table_cell_bold), Paragraph("/api/auth/users/{username}", table_cell_code), Paragraph("Admin Only", table_cell), Paragraph("Path: username", table_cell), Paragraph("204 No Content (deletes user account)", table_cell)],
        [Paragraph("GET", table_cell_bold), Paragraph("/api/health", table_cell_code), Paragraph("Public / Any", table_cell), Paragraph("None", table_cell), Paragraph("{ status: 'healthy', ocr_available, engine }", table_cell)],
    ]

    api_tbl = Table(api_ref_data, colWidths=[40, 115, 75, 145, 148])
    api_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT])
    ]))
    story.append(api_tbl)
    story.append(Spacer(1, 14))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 7: SUMMARY & CONCLUSION
    # ═══════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 10))
    conclusion_html = """<b>CONCLUSION &amp; REGULATORY IMPACT:</b><br/>
    MetrCheck AI delivers an objective, evidence-backed automated compliance pipeline that scales legal metrology and food safety inspections from minutes per package to sub-second processing.
    By marrying computer vision OCR with deterministic legal rule evaluation and formal enforcement tools, it equips enforcement officers with court-ready evidence while providing manufacturers with clear, actionable guidance to correct labeling non-compliances prior to market entry.
    """
    c_table = Table([[Paragraph(conclusion_html, callout_style)]], colWidths=[523])
    c_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_ACCENT_LIGHT),
        ('BOX', (0, 0), (-1, -1), 1, COLOR_ACCENT),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(c_table)

    # Build PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated complete architectural PDF: {filename}")


if __name__ == "__main__":
    output_pdf = "MetrCheck_AI_Complete_Architecture_and_Code_Flow.pdf"
    build_pdf(output_pdf)
