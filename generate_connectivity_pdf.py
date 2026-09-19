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
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.pdfgen import canvas

# ── Color Palette ────────────────────────────────────────────────────────────
COLOR_PRIMARY = colors.HexColor('#1e1b4b')        # Deep indigo / slate 950
COLOR_ACCENT = colors.HexColor('#4f46e5')         # Indigo 600
COLOR_ACCENT_LIGHT = colors.HexColor('#e0e7ff')   # Indigo 100
COLOR_SECONDARY = colors.HexColor('#059669')      # Emerald 600
COLOR_SECONDARY_LIGHT = colors.HexColor('#d1fae5')# Emerald 100
COLOR_WARNING = colors.HexColor('#d97706')        # Amber 600
COLOR_WARNING_LIGHT = colors.HexColor('#fef3c7')  # Amber 100
COLOR_DANGER = colors.HexColor('#dc2626')         # Red 600
COLOR_DANGER_LIGHT = colors.HexColor('#fee2e2')   # Red 100
COLOR_TEXT_MAIN = colors.HexColor('#0f172a')      # Slate 900
COLOR_TEXT_MUTED = colors.HexColor('#475569')     # Slate 600
COLOR_BG_LIGHT = colors.HexColor('#f8fafc')       # Slate 50
COLOR_BG_CARD = colors.HexColor('#f1f5f9')        # Slate 100
COLOR_BORDER = colors.HexColor('#cbd5e1')         # Slate 300
COLOR_BORDER_LIGHT = colors.HexColor('#e2e8f0')   # Slate 200


# ── Numbered Canvas with Running Headers & Footers ──────────────────────────
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

        # Running header on page 2+
        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(COLOR_ACCENT)
            self.drawString(36, page_h - 26, "METRCHECK AI")
            self.setFont("Helvetica", 8)
            self.setFillColor(COLOR_TEXT_MUTED)
            self.drawString(108, page_h - 26, "|   End-to-End System Connectivity & Architectural Wiring Guide")
            self.drawRightString(page_w - 36, page_h - 26, "Smart India Hackathon SIH26034")

            self.setStrokeColor(COLOR_BORDER_LIGHT)
            self.setLineWidth(0.75)
            self.line(36, page_h - 32, page_w - 36, page_h - 32)

            # Footer
            self.line(36, 36, page_w - 36, 36)
            self.drawString(36, 24, "Legal Metrology Compliance AI — Technical Integration & Inter-Service Architecture")
            page_text = f"Page {self._pageNumber} of {page_count}"
            self.drawRightString(page_w - 36, 24, page_text)

        self.restoreState()


def build_connectivity_pdf(filename: str):
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=42,
        bottomMargin=42
    )

    styles = getSampleStyleSheet()

    # Typography styles
    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=30,
        textColor=COLOR_PRIMARY,
        alignment=TA_LEFT,
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=COLOR_ACCENT,
        alignment=TA_LEFT,
        spaceAfter=12
    )

    h1_style = ParagraphStyle(
        'DocH1',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=COLOR_PRIMARY,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'DocH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=COLOR_ACCENT,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=COLOR_TEXT_MAIN,
        spaceAfter=5
    )

    body_bold = ParagraphStyle(
        'DocBodyBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    callout_style = ParagraphStyle(
        'DocCallout',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11.5,
        textColor=COLOR_TEXT_MAIN
    )

    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10.5,
        textColor=colors.white,
        alignment=TA_LEFT
    )

    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
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
        fontSize=7.2,
        leading=9.2,
        textColor=COLOR_ACCENT
    )

    story = []

    # ═══════════════════════════════════════════════════════════════════════════
    # HEADER / BADGE
    # ═══════════════════════════════════════════════════════════════════════════
    badge_data = [[
        Paragraph("<font color='#4f46e5'><b>SMART INDIA HACKATHON 2026</b></font> | Problem Statement: <b>SIH26034</b>", body_style),
        Paragraph(f"Generated: <b>{datetime.now().strftime('%d %b %Y')}</b> | Reference: <b>SYS-CONN-v1.0</b>", ParagraphStyle('RightDate', parent=body_style, alignment=TA_RIGHT))
    ]]
    badge_table = Table(badge_data, colWidths=[300, 223])
    badge_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_ACCENT_LIGHT),
        ('BOX', (0, 0), (-1, -1), 1, COLOR_ACCENT),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(badge_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("MetrCheck AI — System Connectivity &amp; Integration Guide", title_style))
    story.append(Paragraph("Comprehensive Architectural Breakdown of Client-Server, Database, AI Pipeline, and Statutory Integrations", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=COLOR_ACCENT, spaceBefore=0, spaceAfter=8))

    # Executive Summary Box
    summary_text = """<b>EXECUTIVE SUMMARY &amp; INTEGRATION TOPOLOGY:</b><br/>
    <b>MetrCheck AI</b> implements a modular, high-throughput, and fault-tolerant architecture designed to automate statutory label compliance under the <b>Legal Metrology (Packaged Commodities) Rules, 2011</b> and <b>FSSAI Regulations, 2020</b>.
    All system connections are decoupled into 5 operational tiers:
    <b>(1) Client-to-Backend REST Gateway</b> with development &amp; production reverse proxying;
    <b>(2) Asynchronous Relational Persistence</b> using SQLite in WAL mode;
    <b>(3) 7-Stage Internal Pipeline Orchestration</b> linking Computer Vision, PaddleOCR PP-OCRv4, Contextual Regex Parsing, and Codified Legal Metrology Rules;
    <b>(4) External Statutory &amp; Infrastructure Verifications</b> (FoSCoS FSSAI API, GS1 DataKart GTIN Barcode API, OpenCV ArUco Physical Metric Calibration, and SMTP Mail Delivery); and
    <b>(5) Multi-Device &amp; Field Connectivity</b> (LAN IP auto-detection with Terminal ASCII QR code, Cloudflare HTTPS zero-prompt tunneling, and native Capacitor Android APK compilation).
    """
    summary_table = Table([[Paragraph(summary_text, callout_style)]], colWidths=[523])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_BG_LIGHT),
        ('BOX', (0, 0), (-1, -1), 1, COLOR_BORDER),
        ('LINELEFT', (0, 0), (0, -1), 4, COLOR_ACCENT),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 10))

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 1: FRONTEND-TO-BACKEND CONNECTIVITY
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("1. Frontend-to-Backend Client-Server Connection", h1_style))
    story.append(Paragraph(
        "Communication between the <b>React 19 / Vite</b> frontend and the <b>FastAPI</b> Python backend is handled through asynchronous HTTP REST endpoints over JSON and multipart form data. Multiple reverse proxying and CORS safeguards ensure seamless local, network, and containerized operation.",
        body_style
    ))

    fe_be_data = [
        [Paragraph("Mechanism", table_header), Paragraph("Implementation / File", table_header), Paragraph("Technical Details &amp; Operational Functionality", table_header)],
        [
            Paragraph("<b>Vite Dev Reverse Proxy</b>", table_cell_bold),
            Paragraph("<code>frontend/vite.config.ts</code>", table_cell_code),
            Paragraph("Routes all requests starting with <code>/api</code> and <code>/uploads</code> to <code>http://127.0.0.1:8000</code>. Completely eliminates browser Cross-Origin Resource Sharing (CORS) friction during development.", table_cell)
        ],
        [
            Paragraph("<b>Production Nginx Proxy</b>", table_cell_bold),
            Paragraph("<code>frontend/nginx.conf</code><br/><code>docker-compose.yml</code>", table_cell_code),
            Paragraph("In Docker deployment, Nginx listens on port 80/8080 and reverse-proxies <code>/api</code> and <code>/uploads</code> to the internal Docker service container <code>http://backend:8000</code> while preserving client IP headers.", table_cell)
        ],
        [
            Paragraph("<b>Centralized API Client</b>", table_cell_bold),
            Paragraph("<code>frontend/src/services/api.ts</code>", table_cell_code),
            Paragraph("Wraps browser <code>fetch()</code> with dynamic host detection (reads <code>localStorage: metrcheck_api_url</code> or <code>VITE_API_URL</code>), unified error handling, and automated 401 session expiration handling.", table_cell)
        ],
        [
            Paragraph("<b>Bearer Token Interceptor</b>", table_cell_bold),
            Paragraph("<code>frontend/src/services/api.ts:authHeaders()</code>", table_cell_code),
            Paragraph("Pulls stored authentication token from <code>localStorage (metrcheck-token)</code> and injects <code>Authorization: Bearer &lt;token&gt;</code> into every protected HTTP request header.", table_cell)
        ],
        [
            Paragraph("<b>FastAPI CORS Middleware</b>", table_cell_bold),
            Paragraph("<code>backend/main.py</code><br/><code>backend/config.py</code>", table_cell_code),
            Paragraph("Enables <code>CORSMiddleware</code> with configurable <code>CORS_ORIGINS</code> (default <code>['*']</code>), allowing direct cross-origin API calls from mobile browsers, local LAN IPs, or tunneled hostnames.", table_cell)
        ],
        [
            Paragraph("<b>Multipart Multi-Panel Ingestion</b>", table_cell_bold),
            Paragraph("<code>POST /api/analyze</code><br/><code>api.ts:analyzeProducts()</code>", table_cell_code),
            Paragraph("Packages 1 to 4 image files (Front, Back, Sides) alongside JSON panel metadata in a single <code>FormData</code> payload with automated MIME validation.", table_cell)
        ],
    ]
    fe_be_table = Table(fe_be_data, colWidths=[105, 140, 278])
    fe_be_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT])
    ]))
    story.append(fe_be_table)
    story.append(Spacer(1, 10))

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 2: BACKEND-TO-DATABASE CONNECTION
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("2. Backend-to-Database Connection (Persistence Architecture)", h1_style))
    story.append(Paragraph(
        "Persistence is achieved through a high-concurrency asynchronous SQLite connection managed via <b>aiosqlite</b> in <font name='Courier' color='#4f46e5'>backend/database/db.py</font>.",
        body_style
    ))

    db_details = """
    <b>Key Database Connection Features:</b><br/>
    &bull; <b>Write-Ahead Logging (WAL Mode):</b> Initialized on every connection via <code>PRAGMA journal_mode=WAL;</code>. Enables concurrent readers while writes occur without database locking.<br/>
    &bull; <b>Busy Timeout Guard:</b> Configured with <code>PRAGMA busy_timeout=5000;</code> to ensure transactions retry for up to 5 seconds under heavy multi-panel inspection bursts before raising lock exceptions.<br/>
    &bull; <b>FastAPI Lifespan Startup:</b> <code>init_db()</code> runs automatically at application boot, creating or upgrading tables idempotently (<code>analyses</code>, <code>users</code>, <code>password_resets</code>, <code>account_audit_logs</code>).<br/>
    &bull; <b>Automated Test Isolation Guard:</b> <code>_check_safety_guard()</code> inspects <code>TEST_MODE</code> and <code>sys.modules['pytest']</code>. If automated tests attempt to connect to the production <code>metrc_check.db</code>, execution is immediately aborted to prevent data corruption.
    """
    db_table = Table([[Paragraph(db_details, callout_style)]], colWidths=[523])
    db_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_BG_LIGHT),
        ('BOX', (0, 0), (-1, -1), 1, COLOR_BORDER),
        ('LINELEFT', (0, 0), (0, -1), 4, COLOR_SECONDARY),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(db_table)
    story.append(Spacer(1, 10))

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 3: INTERNAL ENGINE ORCHESTRATION PIPELINE
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("3. Internal Pipeline &amp; Multi-Service Orchestration", h1_style))
    story.append(Paragraph(
        "When an inspection request arrives, <font name='Courier' color='#4f46e5'>backend/services/analysis_service.py:analyze_products()</font> coordinates an asynchronous 7-stage processing pipeline connecting internal computer vision, deep learning, statutory parsing, and scoring engines.",
        body_style
    ))

    pipeline_table_data = [
        [Paragraph("Stage", table_header), Paragraph("Internal Component", table_header), Paragraph("Data Ingested &amp; Operational Transition", table_header)],
        [
            Paragraph("<b>1. Image Ingestion</b>", table_cell_bold),
            Paragraph("<code>services/image_service.py</code><br/><code>utils/validators.py</code>", table_cell_code),
            Paragraph("MIME whitelist check (PNG, JPEG, WebP) and 10MB file limit. Generates UUID and writes sanitized files to <code>backend/uploads/</code>.", table_cell)
        ],
        [
            Paragraph("<b>2. CV Preprocessing</b>", table_cell_bold),
            Paragraph("<code>ocr/preprocessing.py</code><br/><code>ocr/quality.py</code>", table_cell_code),
            Paragraph("Performs EXIF rotation correction, 4-point homography perspective warp, Lanczos upscaling, and Laplacian variance blur &amp; contrast quality evaluation.", table_cell)
        ],
        [
            Paragraph("<b>3. Deep Learning OCR</b>", table_cell_bold),
            Paragraph("<code>ocr/factory.py</code><br/><code>ocr/paddle_engine.py</code>", table_cell_code),
            Paragraph("Singleton PaddleOCR PP-OCRv4 (DBNet text detection + SVTR recognition) runs concurrently across panels with thread-safe locks and Windows OneDNN/PIR workarounds. Returns words and 2D bounding boxes.", table_cell)
        ],
        [
            Paragraph("<b>4. Text Normalization</b>", table_cell_bold),
            Paragraph("<code>ocr/cleaner.py</code><br/><code>ocr/repair.py</code>", table_cell_code),
            Paragraph("Strips OCR artifacts while preserving currency (₹), units, and dates. Applies regex repair heuristics for swapped letters (e.g. FSSAI digits, Net Qty '9' &rarr; 'g').", table_cell)
        ],
        [
            Paragraph("<b>5. Structured Extraction</b>", table_cell_bold),
            Paragraph("<code>extraction/extractor.py</code><br/><code>extraction/patterns.py</code>", table_cell_code),
            Paragraph("Contextual regex parser extracts MRP, Net Quantity, Dates, Manufacturer Name/Address/PIN, Consumer Helpline, Barcodes, and Country of Origin into a typed <code>ProductInfo</code> schema.", table_cell)
        ],
        [
            Paragraph("<b>6. Statutory Rules</b>", table_cell_bold),
            Paragraph("<code>compliance/engine.py</code><br/><code>compliance/rules/</code>", table_cell_code),
            Paragraph("Validates declarations against 14 codified rules (LM-001..LM-009 &amp; FS-001..FS-005). <code>scorer.py</code> computes weighted points (0–100 score).", table_cell)
        ],
        [
            Paragraph("<b>7. Dossier Generation</b>", table_cell_bold),
            Paragraph("<code>services/report_service.py</code><br/><code>enforcement/penalties.py</code>", table_cell_code),
            Paragraph("Calculates Legal Metrology Act Sec 36/38 penalty brackets, produces court-ready show-cause notices, generates PDF/XLSX/CSV/JSON reports, and persists record to SQLite.", table_cell)
        ],
    ]
    pipe_table = Table(pipeline_table_data, colWidths=[90, 140, 293])
    pipe_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT])
    ]))
    story.append(pipe_table)
    story.append(Spacer(1, 10))

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 4: EXTERNAL SERVICES & STATUTORY INTEGRATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("4. External Services &amp; Statutory Integrations", h1_style))
    story.append(Paragraph(
        "MetrCheck AI connects to external regulatory databases and physical measurement standards with resilient offline/cache fallbacks:",
        body_style
    ))

    ext_data = [
        [Paragraph("Integration Target", table_header), Paragraph("Protocol / Location", table_header), Paragraph("Operational Function &amp; Fallback Resilience", table_header)],
        [
            Paragraph("<b>FSSAI FoSCoS Verification</b>", table_cell_bold),
            Paragraph("REST API (HTTPS)<br/><code>integrations/fssai/verifier.py</code>", table_cell_code),
            Paragraph("Connects to government FoSCoS API to verify 14-digit licence validity and business name. <b>Fallback:</b> Validates mathematical 14-digit structure (starting with 1 or 2), parses state jurisdiction code, and queries local offline cache.", table_cell)
        ],
        [
            Paragraph("<b>GS1 DataKart GTIN Barcode</b>", table_cell_bold),
            Paragraph("REST API (HTTPS)<br/><code>integrations/gs1/verifier.py</code>", table_cell_code),
            Paragraph("Connects to GS1 DataKart cloud to verify product GTIN barcode ownership and registered brand name. <b>Fallback:</b> Executes standard GS1 Modulo-10 check-digit algorithm and checks local GTIN cache.", table_cell)
        ],
        [
            Paragraph("<b>Physical ArUco Calibration</b>", table_cell_bold),
            Paragraph("OpenCV Computer Vision<br/><code>services/calibration_service.py</code>", table_cell_code),
            Paragraph("Detects physical 50mm ArUco fiducial calibration markers placed on packaging artwork to calculate real-world pixel-to-millimeter ratio. Evaluates statutory Rule 12 minimum font heights. <b>Fallback:</b> DPI factor (0.18 mm/px).", table_cell)
        ],
        [
            Paragraph("<b>SMTP Email Server</b>", table_cell_bold),
            Paragraph("SMTP / STARTTLS (Port 587)<br/><code>auth/security.py</code>", table_cell_code),
            Paragraph("Connects to enterprise mail server (e.g. Gmail/Gov SMTP) to deliver officer invitation tokens and secure password reset links. <b>Fallback:</b> Generates in-app dev activation tokens when SMTP is unconfigured.", table_cell)
        ],
    ]
    ext_table = Table(ext_data, colWidths=[115, 135, 273])
    ext_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT])
    ]))
    story.append(ext_table)
    story.append(Spacer(1, 10))

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 5: CROSS-DEVICE, MOBILE & NETWORK CONNECTIVITY
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("5. Cross-Device, Mobile &amp; Field Network Connectivity", h1_style))
    story.append(Paragraph(
        "MetrCheck AI provides three dedicated pathways to connect field inspection devices, smartphones, and tablets to the processing server:",
        body_style
    ))

    network_data = [
        [Paragraph("Connectivity Mode", table_header), Paragraph("Configuration Script", table_header), Paragraph("Architecture &amp; End-User Experience", table_header)],
        [
            Paragraph("<b>Local Wi-Fi Network &amp; ASCII QR Code</b>", table_cell_bold),
            Paragraph("<code>runner.py</code><br/><code>allow_firewall.bat</code>", table_cell_code),
            Paragraph("<code>runner.py</code> probes active LAN IP via UDP socket (8.8.8.8) and prints an interactive ASCII QR Code in the terminal. Inspectors scan the QR code with their mobile camera to connect instantly via <code>http://&lt;LAN_IP&gt;:5173</code>. Firewall batch script ensures ports 5173 and 8000 are unblocked.", table_cell)
        ],
        [
            Paragraph("<b>Cloudflare Zero-Prompt Tunnel</b>", table_cell_bold),
            Paragraph("<code>tunnel.bat</code>", table_cell_code),
            Paragraph("Spawns a public HTTPS cloud tunnel via <code>npx cloudflared tunnel --url http://localhost:5173</code>. Generates a secure, temporary public URL (e.g. <code>https://xyz.trycloudflare.com</code>) that allows judges, remote officers, or phones to test without being on the same local Wi-Fi.", table_cell)
        ],
        [
            Paragraph("<b>Native Android APK Bridge</b>", table_cell_bold),
            Paragraph("<code>build_apk.bat</code><br/><code>frontend/android/</code>", table_cell_code),
            Paragraph("Bundles React frontend via Vite, synchronizes web assets into Capacitor Android wrapper, and compiles native debug APK (<code>app-debug.apk</code>) with direct hardware camera and gallery capture permissions.", table_cell)
        ],
    ]
    net_table = Table(network_data, colWidths=[120, 120, 283])
    net_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT])
    ]))
    story.append(net_table)
    story.append(Spacer(1, 10))

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 6: SECURITY & ROLE-BASED ACCESS CONTROL (RBAC) WIRING
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("6. Authentication &amp; Security Layer Wiring", h1_style))
    story.append(Paragraph(
        "MetrCheck AI secures all inter-service operations with zero third-party cryptographic dependencies, utilizing Python's built-in <b>hashlib</b> and <b>hmac</b> modules:",
        body_style
    ))

    sec_summary = """
    &bull; <b>Password Hashing:</b> Salted with <code>os.urandom(16)</code> and hashed using <b>PBKDF2-HMAC-SHA256</b> with <b>200,000 iterations</b>. Passwords are never stored in plaintext, and comparisons use <code>hmac.compare_digest</code> to defeat timing attacks.<br/>
    &bull; <b>Stateless HMAC-SHA256 Bearer Tokens:</b> Encodes user identity, role, issue time, and expiration (480 minutes). Signed with server-side <code>SECRET_KEY</code>.<br/>
    &bull; <b>Role Hierarchy:</b> Enforced via FastAPI dependency injection (<code>require_roles(*roles)</code>):<br/>
    &nbsp;&nbsp;&bull; <b>ADMIN:</b> Full system access, user provisioning, database purge, and audit logs.<br/>
    &nbsp;&nbsp;&bull; <b>ENFORCEMENT_OFFICER:</b> Analysis, history, Sec 36/38 statutory penalty estimator, show-cause notices.<br/>
    &nbsp;&nbsp;&bull; <b>MERCHANT_PUBLIC:</b> Multi-panel upload, listing text screening, and inspection report downloads.
    """
    sec_table = Table([[Paragraph(sec_summary, callout_style)]], colWidths=[523])
    sec_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_BG_LIGHT),
        ('BOX', (0, 0), (-1, -1), 1, COLOR_BORDER),
        ('LINELEFT', (0, 0), (0, -1), 4, COLOR_ACCENT),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(sec_table)
    story.append(Spacer(1, 10))

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 7: MASTER CONNECTION & PORT MATRIX
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("7. Master Connectivity, Protocol &amp; Port Matrix", h1_style))

    matrix_data = [
        [Paragraph("Source", table_header), Paragraph("Destination", table_header), Paragraph("Port / Protocol", table_header), Paragraph("Key Module / Endpoint", table_header)],
        [Paragraph("Browser / Phone", table_cell), Paragraph("Vite Dev Server", table_cell), Paragraph("TCP 5173 (HTTP)", table_cell_code), Paragraph("<code>frontend/vite.config.ts</code>", table_cell_code)],
        [Paragraph("Vite Dev Server", table_cell), Paragraph("FastAPI Backend", table_cell), Paragraph("TCP 8000 (HTTP Proxy)", table_cell_code), Paragraph("<code>vite.config.ts:proxy</code>", table_cell_code)],
        [Paragraph("Nginx Container", table_cell), Paragraph("FastAPI Backend", table_cell), Paragraph("TCP 8000 (HTTP Proxy)", table_cell_code), Paragraph("<code>frontend/nginx.conf</code>", table_cell_code)],
        [Paragraph("FastAPI App", table_cell), Paragraph("SQLite File", table_cell), Paragraph("Async File I/O (WAL)", table_cell_code), Paragraph("<code>backend/database/db.py</code>", table_cell_code)],
        [Paragraph("FastAPI App", table_cell), Paragraph("PaddleOCR Engine", table_cell), Paragraph("In-Process PyPaddle", table_cell_code), Paragraph("<code>backend/ocr/paddle_engine.py</code>", table_cell_code)],
        [Paragraph("FastAPI App", table_cell), Paragraph("FoSCoS API", table_cell), Paragraph("TCP 443 (HTTPS)", table_cell_code), Paragraph("<code>integrations/fssai/verifier.py</code>", table_cell_code)],
        [Paragraph("FastAPI App", table_cell), Paragraph("GS1 DataKart", table_cell), Paragraph("TCP 443 (HTTPS)", table_cell_code), Paragraph("<code>integrations/gs1/verifier.py</code>", table_cell_code)],
        [Paragraph("FastAPI App", table_cell), Paragraph("SMTP Server", table_cell), Paragraph("TCP 587 (STARTTLS)", table_cell_code), Paragraph("<code>backend/auth/security.py</code>", table_cell_code)],
        [Paragraph("Mobile Device", table_cell), Paragraph("Cloudflare Edge", table_cell), Paragraph("TCP 443 (HTTPS Tunnel)", table_cell_code), Paragraph("<code>tunnel.bat</code>", table_cell_code)],
    ]
    matrix_table = Table(matrix_data, colWidths=[95, 95, 115, 218])
    matrix_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT])
    ]))
    story.append(matrix_table)
    story.append(Spacer(1, 10))

    # Build PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully created PDF: {filename}")


if __name__ == "__main__":
    out_pdf = "MetrCheck_AI_Complete_System_Connectivity_Guide.pdf"
    build_connectivity_pdf(out_pdf)
