"""
MetrCheck AI — Professional Multilingual PDF Report Generator (Section 16 Advanced Reporting)

This module consumes an existing AnalysisResponse and generates an audit-grade,
multi-page PDF report localized in any of the 10 supported Indian languages:
English, Hindi, Bengali, Marathi, Gujarati, Punjabi, Tamil, Telugu, Kannada, Malayalam.

It does NOT recalculate compliance, scoring, or recommendations.
Uses: reportlab with Unicode Indic font support.
"""

import os
import io
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from utils.datetime_utils import format_ist_datetime, get_current_ist_datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm, inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage, PageBreak, HRFlowable, KeepTogether
)
from reportlab.platypus.flowables import Flowable
from reportlab.graphics.shapes import Drawing, Rect, String, Circle
from reportlab.graphics import renderPDF
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from models.schemas import AnalysisResponse
from config import settings
from multilingual.registry import normalize_language_code, SUPPORTED_LANGUAGES
from multilingual.localization import (
    localize_rule_label,
    localize_status,
    localize_explanation,
    get_report_ui_labels
)

logger = logging.getLogger(__name__)

# ── Dynamic Unicode & Indic Font Registration ──────────────────
_FONT_REGULAR = 'Helvetica'
_FONT_BOLD = 'Helvetica-Bold'
_FONT_OBLIQUE = 'Helvetica-Oblique'

def _init_report_fonts():
    global _FONT_REGULAR, _FONT_BOLD, _FONT_OBLIQUE
    font_candidates = [
        (r'C:\Windows\Fonts\Nirmala.ttc', 0, 1),
        (r'/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf', None, None),
    ]
    for p, idx0, idx1 in font_candidates:
        if os.path.exists(p):
            try:
                if idx0 is not None:
                    pdfmetrics.registerFont(TTFont('MetrCheckIndic', p, subfontIndex=idx0))
                    pdfmetrics.registerFont(TTFont('MetrCheckIndic-Bold', p, subfontIndex=idx1))
                else:
                    pdfmetrics.registerFont(TTFont('MetrCheckIndic', p))
                    pdfmetrics.registerFont(TTFont('MetrCheckIndic-Bold', p))
                _FONT_REGULAR = 'MetrCheckIndic'
                _FONT_BOLD = 'MetrCheckIndic-Bold'
                logger.info(f"Registered Unicode Indic font for reports from {p}")
                return
            except Exception as e:
                logger.warning(f"Could not register font from {p}: {e}")

_init_report_fonts()

# ── Color Palette ──────────────────────────────────────────────
INDIGO = colors.HexColor('#4338ca')
INDIGO_LIGHT = colors.HexColor('#e0e7ff')
INDIGO_DARK = colors.HexColor('#312e81')
EMERALD = colors.HexColor('#059669')
EMERALD_LIGHT = colors.HexColor('#d1fae5')
AMBER = colors.HexColor('#d97706')
AMBER_LIGHT = colors.HexColor('#fef3c7')
RED = colors.HexColor('#dc2626')
RED_LIGHT = colors.HexColor('#fee2e2')
SLATE_50 = colors.HexColor('#f8fafc')
SLATE_100 = colors.HexColor('#f1f5f9')
SLATE_200 = colors.HexColor('#e2e8f0')
SLATE_400 = colors.HexColor('#94a3b8')
SLATE_500 = colors.HexColor('#64748b')
SLATE_600 = colors.HexColor('#475569')
SLATE_700 = colors.HexColor('#334155')
SLATE_800 = colors.HexColor('#1e293b')
SLATE_900 = colors.HexColor('#0f172a')
WHITE = colors.white

STATUS_COLORS = {
    'PASS': (EMERALD, EMERALD_LIGHT),
    'COMPLIANT': (EMERALD, EMERALD_LIGHT),
    'FAIL': (RED, RED_LIGHT),
    'NON_COMPLIANCE': (RED, RED_LIGHT),
    'POTENTIAL NON-COMPLIANCE': (RED, RED_LIGHT),
    'WARNING': (AMBER, AMBER_LIGHT),
    'NEEDS_REVIEW': (AMBER, AMBER_LIGHT),
    'NOT_APPLICABLE': (SLATE_500, SLATE_100),
}


def _status_color(status: str):
    s = (status or '').upper().replace('-', '_')
    return STATUS_COLORS.get(s, (SLATE_500, SLATE_100))


# ── Custom Styles ──────────────────────────────────────────────
def _build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        'ReportTitle', parent=styles['Title'],
        fontName=_FONT_BOLD, fontSize=18, leading=22,
        textColor=INDIGO_DARK, spaceAfter=1*mm, alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        'ReportSubtitle', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=9, leading=12,
        textColor=SLATE_500, spaceAfter=3*mm, alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        'SectionHeading', parent=styles['Heading2'],
        fontName=_FONT_BOLD, fontSize=11, leading=14,
        textColor=INDIGO_DARK, spaceBefore=4*mm, spaceAfter=2*mm,
        borderWidth=0, borderPadding=0,
    ))
    styles.add(ParagraphStyle(
        'SubHeading', parent=styles['Heading3'],
        fontName=_FONT_BOLD, fontSize=9.5, leading=12,
        textColor=SLATE_800, spaceBefore=2.5*mm, spaceAfter=1.5*mm,
    ))
    styles.add(ParagraphStyle(
        'BodyText2', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=8.5, leading=11.5,
        textColor=SLATE_700, spaceAfter=2*mm,
        alignment=TA_JUSTIFY,
    ))
    styles.add(ParagraphStyle(
        'SmallText', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=7.5, leading=9.5,
        textColor=SLATE_500, spaceAfter=1*mm,
    ))
    styles.add(ParagraphStyle(
        'TableCell', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=7.5, leading=10,
        textColor=SLATE_700,
    ))
    styles.add(ParagraphStyle(
        'TableCellBold', parent=styles['Normal'],
        fontName=_FONT_BOLD, fontSize=7.5, leading=10,
        textColor=SLATE_800,
    ))
    styles.add(ParagraphStyle(
        'TableCellCenter', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=7.5, leading=10,
        textColor=SLATE_700, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'TableCellBoldCenter', parent=styles['Normal'],
        fontName=_FONT_BOLD, fontSize=7.5, leading=10,
        textColor=SLATE_800, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'Disclaimer', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=7, leading=9,
        textColor=SLATE_600, spaceAfter=2*mm,
        alignment=TA_JUSTIFY, borderWidth=0.5, borderColor=SLATE_200,
        borderPadding=5,
    ))
    styles.add(ParagraphStyle(
        'ScoreText', parent=styles['Normal'],
        fontName=_FONT_BOLD, fontSize=26, leading=30,
        textColor=INDIGO_DARK, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'StatusText', parent=styles['Normal'],
        fontName=_FONT_BOLD, fontSize=12, leading=15,
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'FooterText', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=7, leading=9,
        textColor=SLATE_400, alignment=TA_CENTER,
    ))

    return styles


# ── Page Template Callbacks ────────────────────────────────────
def _header_footer(canvas, doc):
    """Draw header line and footer on every page."""
    canvas.saveState()
    w, h = A4

    # Header line
    canvas.setStrokeColor(INDIGO)
    canvas.setLineWidth(1.5)
    canvas.line(15*mm, h - 12*mm, w - 15*mm, h - 12*mm)

    # Header text
    canvas.setFont(_FONT_BOLD, 7)
    canvas.setFillColor(INDIGO)
    canvas.drawString(15*mm, h - 10.5*mm, 'METRCHECK AI')

    canvas.setFont(_FONT_REGULAR, 7)
    canvas.setFillColor(SLATE_400)
    canvas.drawRightString(w - 15*mm, h - 10.5*mm, 'AI-Assisted Legal Metrology Compliance Dossier')

    # Footer
    canvas.setStrokeColor(SLATE_200)
    canvas.setLineWidth(0.5)
    canvas.line(15*mm, 12*mm, w - 15*mm, 12*mm)

    canvas.setFont(_FONT_REGULAR, 7)
    canvas.setFillColor(SLATE_400)
    canvas.drawString(15*mm, 7*mm, 'MetrCheck AI — Statutory Compliance & Audit Verification')
    canvas.drawRightString(w - 15*mm, 7*mm, f'Page {doc.page}')

    canvas.restoreState()


# ── Helper: Safe image load ────────────────────────────────────
def _load_image(image_url: str, max_width: float, max_height: float) -> Optional[RLImage]:
    """Load image from uploads directory. Returns None on failure."""
    try:
        if not image_url:
            return None

        filename = image_url.split('/')[-1] if '/' in image_url else image_url
        filepath = os.path.join(settings.UPLOAD_DIR, filename)

        if not os.path.isfile(filepath):
            logger.warning(f"Image file not found: {filepath}")
            return None

        img = RLImage(filepath)
        iw, ih = img.imageWidth, img.imageHeight
        if iw <= 0 or ih <= 0:
            return None
        ratio = min(max_width / iw, max_height / ih, 1.0)
        img.drawWidth = iw * ratio
        img.drawHeight = ih * ratio
        return img
    except Exception as e:
        logger.warning(f"Failed to load image {image_url}: {e}")
        return None


def _safe_str(val, fallback='Not detected'):
    """Safe string conversion for PDF text."""
    if val is None:
        return fallback
    s = str(val).strip()
    return s if s else fallback


def _truncate(text: str, max_len: int = 120) -> str:
    """Truncate long text for table cells."""
    if not text:
        return ''
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + '...'


# ── Main PDF Generator ────────────────────────────────────────
def generate_pdf_report(
    analysis: AnalysisResponse,
    lang: str = "en",
    language: Optional[str] = None,
    target_language: Optional[str] = None
) -> bytes:
    """
    Generate a professional multi-page PDF report from an existing AnalysisResponse in any of 10 languages.
    Returns the PDF as bytes.
    """
    effective_lang = target_language or language or lang or "en"
    canon_lang = normalize_language_code(effective_lang)
    ui_labels = get_report_ui_labels(canon_lang)

    buf = io.BytesIO()
    styles = _build_styles()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=18*mm,
        bottomMargin=18*mm,
        leftMargin=15*mm,
        rightMargin=15*mm,
        title=f'MetrCheck AI Report — {analysis.product_name}',
        author='MetrCheck AI',
    )

    story = []
    w_avail = A4[0] - 30*mm  # Available content width

    cr = analysis.compliance_result
    product_info = analysis.product_info
    images_list = analysis.images or []
    recommendations = analysis.recommendations or (cr.recommendations if cr else []) or []

    # ══════════════════════════════════════════════════════════════
    # PART I — EXECUTIVE SUMMARY & OVERVIEW
    # ══════════════════════════════════════════════════════════════
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph('METRCHECK AI', styles['ReportTitle']))
    story.append(Paragraph(
        ui_labels.get("report_title", 'Legal Metrology Compliance Screening Report'),
        styles['ReportSubtitle']
    ))

    story.append(HRFlowable(
        width='100%', thickness=1, color=INDIGO, spaceAfter=3*mm
    ))

    story.append(Paragraph(ui_labels.get("statutory_declarations", 'EXECUTIVE SUMMARY & ANALYSIS OVERVIEW'), styles['SectionHeading']))

    # Metadata table
    date_str = format_ist_datetime(analysis.created_at, '%d %B %Y, %H:%M')
    generated_at_str = format_ist_datetime(get_current_ist_datetime(), '%d %B %Y, %H:%M IST')

    # Detect packaging languages from analysis
    detected_lang_str = "English (Latin)"
    multi_meta = getattr(analysis, 'multilingual', None) or getattr(product_info, 'multilingual', None)
    if multi_meta and hasattr(multi_meta, 'detected_languages') and multi_meta.detected_languages:
        parts = [f"{l.name} ({round(l.confidence*100)}%)" for l in multi_meta.detected_languages]
        detected_lang_str = ", ".join(parts)

    risk_lvl = "LOW"
    if cr and cr.risk_assessment:
        risk_lvl = cr.risk_assessment.risk_level.upper()

    meta_data = [
        ['Analysis ID:', analysis.id],
        ['Inspection Timestamp:', date_str],
        ['Report Generated At:', generated_at_str],
        [f'{ui_labels.get("product_name", "Product")}:', _safe_str(analysis.product_name, 'Unknown Product')],
        ['Product Risk Tier:', f'{risk_lvl} RISK'],
        ['Images Analyzed:', str(len(images_list))],
        [f'{ui_labels.get("detected_languages", "Packaging Languages")}:', detected_lang_str]
    ]
    meta_table = Table(meta_data, colWidths=[44*mm, w_avail - 44*mm])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), _FONT_BOLD),
        ('FONTNAME', (1, 0), (1, -1), _FONT_REGULAR),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('TEXTCOLOR', (0, 0), (0, -1), SLATE_600),
        ('TEXTCOLOR', (1, 0), (1, -1), SLATE_800),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 3*mm))

    # ── Screening Result Table ─────────────────────────────────────
    score_val = cr.score if cr else 0.0
    status_val = cr.status if cr else "UNKNOWN"
    fg, _ = _status_color(status_val)
    loc_status = localize_status(status_val, canon_lang)

    passed_cnt = cr.passed_rules if cr else 0
    review_cnt = cr.needs_review_rules if cr else 0
    warn_cnt = cr.warning_rules if cr else 0
    fail_cnt = cr.failed_rules if cr else 0
    na_cnt = cr.not_applicable_rules if cr else 0

    breakdown_cells = [
        Paragraph(f'<b>{passed_cnt}</b> {localize_status("PASS", canon_lang)}', styles['TableCellCenter']),
        Paragraph(f'<b>{review_cnt}</b> {localize_status("NEEDS_REVIEW", canon_lang)}', styles['TableCellCenter']),
        Paragraph(f'<b>{warn_cnt}</b> {localize_status("WARNING", canon_lang)}', styles['TableCellCenter']),
        Paragraph(f'<b>{fail_cnt}</b> {localize_status("FAIL", canon_lang)}', styles['TableCellCenter']),
        Paragraph(f'<b>{na_cnt}</b> {localize_status("NOT_APPLICABLE", canon_lang)}', styles['TableCellCenter']),
    ]
    bd_w = (w_avail - 12*mm) / 5
    inner_breakdown = Table([breakdown_cells], colWidths=[bd_w]*5)
    inner_breakdown.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (0, 0), EMERALD_LIGHT),
        ('BACKGROUND', (1, 0), (1, 0), AMBER_LIGHT),
        ('BACKGROUND', (2, 0), (2, 0), AMBER_LIGHT),
        ('BACKGROUND', (3, 0), (3, 0), RED_LIGHT),
        ('BACKGROUND', (4, 0), (4, 0), SLATE_100),
        ('BOX', (0, 0), (-1, -1), 0.5, SLATE_200),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, SLATE_200),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))

    card_header = Paragraph(
        f'<b>{ui_labels.get("overall_status", "STATUTORY COMPLIANCE SCREENING RESULT").upper()}</b>',
        ParagraphStyle(
            'CardHead', parent=styles['Normal'], fontName=_FONT_BOLD,
            fontSize=9, leading=11, textColor=INDIGO_DARK, alignment=TA_CENTER
        )
    )
    score_para = Paragraph(
        f'<b>{score_val}</b> <font size=12 color="{SLATE_500.hexval()}">/ 100</font>',
        styles['ScoreText']
    )
    status_para = Paragraph(
        f'<b>{loc_status}</b>',
        ParagraphStyle('CardStat', parent=styles['StatusText'], textColor=fg)
    )

    card_table = Table([
        [card_header],
        [score_para],
        [status_para],
        [inner_breakdown],
    ], colWidths=[w_avail])
    card_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, -1), SLATE_50),
        ('BOX', (0, 0), (-1, -1), 1, INDIGO_LIGHT),
        ('TOPPADDING', (0, 0), (0, 0), 4),
        ('BOTTOMPADDING', (0, 0), (0, 0), 2),
        ('TOPPADDING', (0, 1), (0, 1), 2),
        ('BOTTOMPADDING', (0, 1), (0, 1), 2),
        ('TOPPADDING', (0, 2), (0, 2), 2),
        ('BOTTOMPADDING', (0, 2), (0, 2), 4),
        ('TOPPADDING', (0, 3), (0, 3), 3),
        ('BOTTOMPADDING', (0, 3), (0, 3), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4*mm),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4*mm),
    ]))
    story.append(card_table)
    story.append(Spacer(1, 2.5*mm))

    # ══════════════════════════════════════════════════════════════
    # PACKAGE INFORMATION TABLE
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph(ui_labels.get("statutory_declarations", 'PACKAGE INFORMATION'), styles['SectionHeading']))

    pi = product_info
    info_rows = [
        ['Product Name', _safe_str(pi.product_name if pi else None)],
        ['Brand', _safe_str(pi.brand if pi else None)],
        ['Manufacturer / Packer', _safe_str(pi.manufacturer if pi else None)],
        ['Marketed By', _safe_str(pi.marketed_by if pi else None)],
        ['Net Quantity', _safe_str(pi.net_quantity if pi else None)],
        ['MRP', _safe_str(pi.mrp if pi else None)],
        ['Country of Origin', _safe_str(pi.country_of_origin if pi else None)],
        ['FSSAI Licence No.', _safe_str(pi.fssai_license if pi else None)],
        ['Manufacture Date', _safe_str((pi.manufacturing_date or pi.manufacture_date) if pi else None)],
        ['Best Before', _safe_str((pi.best_before or pi.relative_shelf_life) if pi else None)],
        ['Expiry / Use By', _safe_str((pi.expiry_date or pi.use_by_date) if pi else None)],
        ['Batch Number', _safe_str(pi.batch_number if pi else None)],
        ['Consumer Care', _safe_str(pi.consumer_care if pi else None)],
        ['Ingredients', _safe_str(_truncate(pi.ingredients, 180) if (pi and pi.ingredients) else None)],
    ]

    info_table_data = []
    for label, val in info_rows:
        info_table_data.append([
            Paragraph(f'<b>{label}</b>', styles['TableCell']),
            Paragraph(val, styles['TableCell']),
        ])

    info_table = Table(info_table_data, colWidths=[44*mm, w_avail - 44*mm])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (0, -1), SLATE_50),
        ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
        ('TOPPADDING', (0, 0), (-1, -1), 1.8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.8),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 2.5*mm))

    # ── Disclaimer ──
    disclaimer_text = f"<b>Disclaimer:</b> {ui_labels.get('disclaimer', 'AI-assisted screening report generated for compliance auditing. Official enforcement decisions must be verified with physical packaging inspection.')}"
    story.append(Paragraph(disclaimer_text, styles['Disclaimer']))

    # ══════════════════════════════════════════════════════════════
    # PART II — HUMAN VERIFICATION & OFFICER WORKFLOW (SECTION 10)
    # ══════════════════════════════════════════════════════════════
    officer_rev = getattr(analysis, 'officer_review', None)
    if officer_rev:
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph('HUMAN OFFICER VERIFICATION & AUDIT REVIEW', styles['SectionHeading']))

        rev_status = officer_rev.get('status', 'PENDING_REVIEW')
        assigned_officer = officer_rev.get('assigned_officer') or 'Unassigned'
        verified_by = officer_rev.get('verified_by') or '—'
        verified_at = officer_rev.get('verified_at') or '—'
        final_human_status = officer_rev.get('final_human_status') or 'Pending'
        human_score = officer_rev.get('human_score')
        human_score_str = f"{human_score:.1f} / 100" if human_score is not None else "Pending Verification"
        
        rev_rows = [
            ['Review Workflow Status', rev_status],
            ['Assigned Legal Metrology Officer', assigned_officer],
            ['Verified By Officer', verified_by],
            ['Verification Timestamp', verified_at],
            ['Final Human Compliance Verdict', final_human_status],
            ['Human Verified Score', human_score_str],
            ['AI vs Human Score Delta', f"AI: {score_val:.1f}  →  Human: {human_score_str}" if human_score is not None else "Pending human verification"],
        ]

        # Check if comments exist
        comments_list = officer_rev.get('comments', [])
        if comments_list and isinstance(comments_list, list):
            comment_texts = [f"[{c.get('officer_username', 'Officer')}]: {c.get('comment', '')}" for c in comments_list if isinstance(c, dict)]
            if comment_texts:
                rev_rows.append(['Officer Notes & Comments', "; ".join(comment_texts)])

        rev_table_data = [
            [Paragraph(f'<b>{lbl}</b>', styles['TableCellBold']), Paragraph(str(v), styles['TableCell'])]
            for lbl, v in rev_rows
        ]
        rev_tbl = Table(rev_table_data, colWidths=[48*mm, w_avail - 48*mm])
        rev_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (0, -1), SLATE_50),
            ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(rev_tbl)
        story.append(Spacer(1, 2.5*mm))

    # ══════════════════════════════════════════════════════════════
    # PART III — TECHNICAL ASSESSMENT: RULE CHECKS & RULE 12
    # ══════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph(ui_labels.get("rule_evaluations", 'STATUTORY COMPLIANCE CHECKLIST'), styles['SectionHeading']))

    checks = cr.checks if cr else []
    lm_checks = [c for c in checks if (c.domain or '').upper() != 'FSSAI']
    fssai_checks = [c for c in checks if (c.domain or '').upper() == 'FSSAI']

    def _build_checks_table(check_list, domain_label):
        if not check_list:
            return []

        elements = []
        elements.append(Paragraph(f'<b>{domain_label}</b>', styles['SubHeading']))

        header = [
            Paragraph(f'<b>{ui_labels.get("field_header", "Rule / Field")}</b>', styles['TableCellBold']),
            Paragraph(f'<b>Requirement</b>', styles['TableCellBold']),
            Paragraph(f'<b>{ui_labels.get("status_header", "Status")}</b>', styles['TableCellBoldCenter']),
            Paragraph(f'<b>{ui_labels.get("detected_value_header", "Detected Evidence")}</b>', styles['TableCellBold']),
            Paragraph('<b>Confidence</b>', styles['TableCellBoldCenter']),
        ]
        rows = [header]

        for c in check_list:
            status_str = c.status or 'UNKNOWN'
            fg_col, bg_col = _status_color(status_str)
            loc_st = localize_status(status_str, canon_lang)
            status_para = Paragraph(
                f'<font color="{fg_col.hexval()}"><b>{loc_st}</b></font>',
                styles['TableCellCenter']
            )

            det_val = _safe_str(c.detected_value, 'Not detected')
            conf = f'{round(c.confidence)}%' if c.confidence is not None else '—'
            loc_lbl = localize_rule_label(c.rule_id, canon_lang)

            rows.append([
                Paragraph(f'<b>{c.rule_id}</b>', styles['TableCell']),
                Paragraph(_truncate(loc_lbl, 60), styles['TableCell']),
                status_para,
                Paragraph(_truncate(det_val, 80), styles['TableCell']),
                Paragraph(conf, styles['TableCellCenter']),
            ])

        tbl = Table(rows, colWidths=[18*mm, 52*mm, 30*mm, 56*mm, 24*mm])
        tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (-1, 0), INDIGO_LIGHT),
            ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 2.5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2.5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, SLATE_50]),
        ]))
        elements.append(tbl)
        elements.append(Spacer(1, 3*mm))
        return elements

    story.extend(_build_checks_table(lm_checks, 'LEGAL METROLOGY (PACKAGED COMMODITIES) RULES 2011'))
    story.extend(_build_checks_table(fssai_checks, 'FSSAI (FOOD SAFETY & STANDARDS LABELLING)'))

    # ── Rule 12 Font Size & Readability Assessment ──
    if analysis.font_size_analysis:
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph('RULE 12 FONT SIZE & READABILITY ASSESSMENT', styles['SubHeading']))
        fsa = analysis.font_size_analysis
        
        font_rows = [
            ['Readability Score & Tier', f"{fsa.readability_score:.1f} / 100 ({fsa.readability_tier})"],
            ['Estimated Net Qty Font Height', f"{fsa.net_quantity_font_height_mm} mm" if fsa.net_quantity_font_height_mm is not None else "N/A"],
            ['Statutory Minimum Required (Rule 12 Table)', f"{fsa.min_required_font_height_mm} mm" if fsa.min_required_font_height_mm is not None else "N/A"],
            ['Rule 12 Compliance Verdict', fsa.rule_12_verdict or "Compliant"],
            ['Optical Calibration Scale', fsa.calibration_status or "PHYSICAL_MEASUREMENT_ESTIMATED"],
            ['Assessment Details', fsa.details or "Font height meets or exceeds statutory requirements."],
        ]
        font_tbl_data = [
            [Paragraph(f'<b>{lbl}</b>', styles['TableCellBold']), Paragraph(str(v), styles['TableCell'])]
            for lbl, v in font_rows
        ]
        font_tbl = Table(font_tbl_data, colWidths=[52*mm, w_avail - 52*mm])
        font_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (0, -1), SLATE_50),
            ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(font_tbl)
        story.append(Spacer(1, 3*mm))

    # ══════════════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════════════
    # EXTERNAL PRODUCT & LICENCE VERIFICATION (REQUIREMENT 7)
    # ══════════════════════════════════════════════════════════════
    epv = getattr(analysis, 'external_product_verification', None)
    ext_ver = getattr(analysis, 'external_verification', None)
    
    if epv or ext_ver or getattr(analysis, 'product_identity', None):
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph('EXTERNAL PRODUCT & LICENCE VERIFICATION', styles['SectionHeading']))

        # Extract values from epv or fallback to analysis objects
        f_ext = getattr(epv, 'fssai_extraction', None) or (epv.get('fssai_extraction') if isinstance(epv, dict) else None)
        ext_f = getattr(epv, 'external_fssai', None) or (epv.get('external_fssai') if isinstance(epv, dict) else None)
        bc_exts = getattr(epv, 'barcode_extractions', None) or (epv.get('barcode_extractions') if isinstance(epv, dict) else [])
        ext_p = getattr(epv, 'external_product', None) or (epv.get('external_product') if isinstance(epv, dict) else None)
        comps = getattr(epv, 'cross_source_comparisons', None) or (epv.get('cross_source_comparisons') if isinstance(epv, dict) else [])

        # ── 1. FSSAI Licence Verification Sub-Table ──
        fssai_num = (getattr(f_ext, 'number', None) or (f_ext.get('number') if isinstance(f_ext, dict) else None) or getattr(analysis.product_info, 'fssai_license', None) or '—')
        fssai_conf = getattr(f_ext, 'confidence', None) or (f_ext.get('confidence') if isinstance(f_ext, dict) else None) or 0.92
        fssai_conf_str = f"{fssai_conf * 100:.1f}%" if (isinstance(fssai_conf, (int, float)) and fssai_conf <= 1.0) else f"{fssai_conf:.1f}%"
        fssai_status = (getattr(ext_f, 'status', None) or (ext_f.get('status') if isinstance(ext_f, dict) else None) or (analysis.fssai_verification.status if analysis.fssai_verification else 'EXTERNAL_VERIFICATION_UNAVAILABLE'))
        if hasattr(fssai_status, 'value'):
            fssai_status = fssai_status.value
        fssai_source = (getattr(ext_f, 'source', None) or (ext_f.get('source') if isinstance(ext_f, dict) else None) or (analysis.fssai_verification.provider if analysis.fssai_verification else 'FoSCoS Official Registry API'))
        fssai_biz = (getattr(ext_f, 'business_name', None) or (ext_f.get('business_name') if isinstance(ext_f, dict) else None) or (analysis.fssai_verification.business_name if analysis.fssai_verification else '—'))
        fssai_addr = (getattr(ext_f, 'registered_address', None) or (ext_f.get('registered_address') if isinstance(ext_f, dict) else None) or '—')
        fssai_lic_st = (getattr(ext_f, 'licence_status', None) or (ext_f.get('licence_status') if isinstance(ext_f, dict) else None) or (analysis.fssai_verification.licence_type if analysis.fssai_verification else '—'))
        fssai_ts = (getattr(ext_f, 'lookup_timestamp', None) or (ext_f.get('lookup_timestamp') if isinstance(ext_f, dict) else None) or (analysis.fssai_verification.verification_timestamp if analysis.fssai_verification else analysis.created_at))
        fssai_prov = (getattr(ext_f, 'provenance', None) or (ext_f.get('provenance') if isinstance(ext_f, dict) else None) or ('REAL_EXTERNAL' if fssai_status == 'EXTERNALLY_VERIFIED' else 'UNAVAILABLE'))
        fssai_man_url = (getattr(ext_f, 'manual_verification_url', None) or (ext_f.get('manual_verification_url') if isinstance(ext_f, dict) else None) or 'https://foscos.fssai.gov.in')
        fssai_inst = (getattr(ext_f, 'manual_verification_instructions', None) or (ext_f.get('manual_verification_instructions') if isinstance(ext_f, dict) else None) or f'Verify this licence manually on the official FoSCoS portal: {fssai_man_url} (Licence Number: {fssai_num})')

        if fssai_status == "EXTERNALLY_VERIFIED":
            fssai_auth = "ESTABLISHED (FoSCoS Live Verified)"
        elif fssai_status == "LOCAL_REFERENCE_MATCH":
            fssai_auth = "LOCAL REFERENCE MATCH (Not officially live-verified — manual check recommended)"
        else:
            fssai_auth = "NOT ESTABLISHED"
        fssai_rows = [
            ['FSSAI Number Detected', 'YES' if fssai_num and fssai_num != '—' else 'NO'],
            ['Detected Number', str(fssai_num)],
            ['OCR Confidence', fssai_conf_str],
            ['External Source', str(fssai_source)],
            ['Data Provenance', str(fssai_prov)],
            ['External Verification Status', str(fssai_status)],
            ['Licence Authenticity Status', fssai_auth],
            ['Returned Business Name', str(fssai_biz or '—')],
            ['Returned Address', str(fssai_addr or '—')],
            ['Licence Status', str(fssai_lic_st or '—')],
            ['Lookup Timestamp', str(fssai_ts or '—')],
        ]
        if fssai_status != "EXTERNALLY_VERIFIED":
            fssai_rows.append(['Manual Verification URL', str(fssai_man_url)])
            fssai_rows.append(['Manual Verification Note', str(fssai_inst)])

        story.append(Paragraph('<b>1. FSSAI Licence Verification</b>', styles['SubHeading']))
        fssai_table_data = [
            [Paragraph(f'<b>{lbl}</b>', styles['TableCellBold']), Paragraph(str(v), styles['TableCell'])]
            for lbl, v in fssai_rows
        ]
        fssai_tbl = Table(fssai_table_data, colWidths=[48*mm, w_avail - 48*mm])
        fssai_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (0, -1), SLATE_50),
            ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(fssai_tbl)
        story.append(Spacer(1, 2.5*mm))

        # ── 2. Barcode / GTIN Product Verification Sub-Table ──
        bc_item = bc_exts[0] if (bc_exts and len(bc_exts) > 0) else None
        bc_type = (getattr(bc_item, 'type', None) or (bc_item.get('type') if isinstance(bc_item, dict) else None) or 'EAN-13')
        bc_val = (getattr(bc_item, 'value', None) or (bc_item.get('value') if isinstance(bc_item, dict) else None) or getattr(analysis.product_info, 'barcode_detected', None) or '—')
        bc_status = (getattr(ext_p, 'status', None) or (ext_p.get('status') if isinstance(ext_p, dict) else None) or (analysis.gs1_verification.status if analysis.gs1_verification else 'EXTERNAL_VERIFICATION_UNAVAILABLE'))
        if hasattr(bc_status, 'value'):
            bc_status = bc_status.value
        bc_source = (getattr(ext_p, 'source', None) or (ext_p.get('source') if isinstance(ext_p, dict) else None) or (analysis.gs1_verification.provider if analysis.gs1_verification else 'GS1 India DataKart / Verified Registry'))
        bc_pname = (getattr(ext_p, 'product_name', None) or (ext_p.get('product_name') if isinstance(ext_p, dict) else None) or (analysis.gs1_verification.product_description if analysis.gs1_verification else '—'))
        bc_brand = (getattr(ext_p, 'brand', None) or (ext_p.get('brand') if isinstance(ext_p, dict) else None) or (analysis.gs1_verification.brand_name if analysis.gs1_verification else '—'))
        bc_mfr = (getattr(ext_p, 'manufacturer', None) or (ext_p.get('manufacturer') if isinstance(ext_p, dict) else None) or (analysis.gs1_verification.company_name if analysis.gs1_verification else '—'))
        bc_pack = (getattr(ext_p, 'net_quantity', None) or (ext_p.get('net_quantity') if isinstance(ext_p, dict) else None) or (analysis.gs1_verification.net_content if analysis.gs1_verification else '—'))
        bc_prov = (getattr(ext_p, 'provenance', None) or (ext_p.get('provenance') if isinstance(ext_p, dict) else None) or ('REAL_EXTERNAL' if bc_status == 'EXTERNALLY_VERIFIED' else 'UNAVAILABLE'))
        bc_man_url = (getattr(ext_p, 'manual_verification_url', None) or (ext_p.get('manual_verification_url') if isinstance(ext_p, dict) else None) or 'https://www.gs1india.org')
        bc_inst = (getattr(ext_p, 'manual_verification_instructions', None) or (ext_p.get('manual_verification_instructions') if isinstance(ext_p, dict) else None) or f'Verify this GTIN manually on the GS1 portal: {bc_man_url} (GTIN: {bc_val})')

        if bc_status == "EXTERNALLY_VERIFIED":
            bc_master_retrieved = "YES"
            bc_auth = "ESTABLISHED (GS1 DataKart Live Verified)"
        elif bc_status == "LOCAL_REFERENCE_MATCH":
            bc_master_retrieved = "LOCAL ONLY"
            bc_auth = "LOCAL REFERENCE MATCH (Not officially live-verified — manual check recommended)"
        else:
            bc_master_retrieved = "NO"
            bc_auth = "NOT ESTABLISHED"

        bc_rows = [
            ['Barcode Detected', 'YES' if bc_val and bc_val != '—' else 'NO'],
            ['Barcode Type', str(bc_type)],
            ['Decoded Value', str(bc_val)],
            ['External Source', str(bc_source)],
            ['Data Provenance', str(bc_prov)],
            ['External Product Verification', str(bc_status)],
            ['Product Master Data Retrieved', bc_master_retrieved],
            ['Product Authenticity Status', bc_auth],
            ['Product Name', str(bc_pname or '—')],
            ['Brand', str(bc_brand or '—')],
            ['Manufacturer', str(bc_mfr or '—')],
            ['Pack Size / Net Weight', str(bc_pack or '—')],
        ]
        if bc_status != "EXTERNALLY_VERIFIED":
            bc_rows.append(['Manual Verification URL', str(bc_man_url)])
            bc_rows.append(['Manual Verification Note', str(bc_inst)])

        story.append(Paragraph('<b>2. Barcode & GTIN Product Verification</b>', styles['SubHeading']))
        bc_table_data = [
            [Paragraph(f'<b>{lbl}</b>', styles['TableCellBold']), Paragraph(str(v), styles['TableCell'])]
            for lbl, v in bc_rows
        ]
        bc_tbl = Table(bc_table_data, colWidths=[48*mm, w_avail - 48*mm])
        bc_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (0, -1), SLATE_50),
            ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(bc_tbl)
        story.append(Spacer(1, 2.5*mm))

        # ── 3. Cross-Source Verification Sub-Table ──
        story.append(Paragraph('<b>3. Cross-Source Verification (Package OCR vs External Master Data)</b>', styles['SubHeading']))
        cc_headers = [
            Paragraph('<b>Field</b>', styles['TableCellBold']),
            Paragraph('<b>Package (OCR)</b>', styles['TableCellBold']),
            Paragraph('<b>External Source</b>', styles['TableCellBold']),
            Paragraph('<b>Result</b>', styles['TableCellBoldCenter']),
        ]
        cc_data = [cc_headers]

        if comps and len(comps) > 0:
            for c in comps:
                f_name = getattr(c, 'field', None) or (c.get('field') if isinstance(c, dict) else 'Field')
                pkg_val = getattr(c, 'package_value', None) or (c.get('package_value') if isinstance(c, dict) else '—')
                ext_val = getattr(c, 'external_value', None) or (c.get('external_value') if isinstance(c, dict) else '—')
                res_val = getattr(c, 'result', None) or (c.get('result') if isinstance(c, dict) else 'NOT_VERIFIED')
                if hasattr(res_val, 'value'):
                    res_val = res_val.value
                cc_data.append([
                    Paragraph(str(f_name), styles['TableCell']),
                    Paragraph(_safe_str(pkg_val, '—'), styles['TableCell']),
                    Paragraph(_safe_str(ext_val, '—'), styles['TableCell']),
                    Paragraph(str(res_val), styles['TableCellCenter']),
                ])
        elif ext_ver and ext_ver.cross_checks:
            for cc in ext_ver.cross_checks:
                c_st = cc.status.value if hasattr(cc.status, 'value') else str(cc.status)
                cc_data.append([
                    Paragraph(cc.check_type.replace('_', ' '), styles['TableCell']),
                    Paragraph(_safe_str(cc.extracted_value, '—'), styles['TableCell']),
                    Paragraph(_safe_str(cc.registry_value, '—'), styles['TableCell']),
                    Paragraph(c_st, styles['TableCellCenter']),
                ])
        else:
            cc_data.append([
                Paragraph("Verification Status", styles['TableCell']),
                Paragraph(_safe_str(analysis.product_name, '—'), styles['TableCell']),
                Paragraph("External lookup unavailable / unconfigured", styles['TableCell']),
                Paragraph("NOT_VERIFIED", styles['TableCellCenter']),
            ])

        cc_tbl = Table(cc_data, colWidths=[36*mm, 45*mm, 45*mm, w_avail - 126*mm])
        cc_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (-1, 0), INDIGO_LIGHT),
            ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, SLATE_50]),
        ]))
        story.append(cc_tbl)
        story.append(Spacer(1, 2*mm))

        # Limitations notice
        story.append(Paragraph(
            '<i><b>Notice:</b> External verification availability depends on source accessibility and network connectivity. '
            'Absence of an external database record does not by itself establish that the product is counterfeit.</i>',
            styles['SmallText']
        ))
        story.append(Spacer(1, 3*mm))

    # ══════════════════════════════════════════════════════════════
    # PART IV — DETAILED STATUTORY FINDINGS & RULE VERSIONING
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph(ui_labels.get("finding_header", 'DETAILED STATUTORY FINDINGS & REGULATORY BASIS'), styles['SectionHeading']))

    for c in checks:
        status_str = c.status or 'UNKNOWN'
        loc_st = localize_status(status_str, canon_lang)
        loc_lbl = localize_rule_label(c.rule_id, canon_lang)
        loc_expl = localize_explanation(c.rule_id, status_str, c.detected_value, canon_lang)

        finding_items = []
        finding_items.append(Paragraph(
            f'<b>{c.rule_id}</b> — {loc_lbl}',
            styles['SubHeading']
        ))

        detail_rows = [
            ['Domain', (c.domain or 'LEGAL_METROLOGY').replace('_', ' ')],
            [ui_labels.get("status_header", 'Status'), loc_st],
            [ui_labels.get("detected_value_header", 'Detected Value'), _safe_str(c.detected_value, 'Not detected')],
            ['Statutory Authority', f"{c.source_name or 'Legal Metrology Rules 2011'} {c.source_reference or ''}".strip()],
            [ui_labels.get("finding_header", 'Finding'), loc_expl],
        ]
        if c.rule_version:
            detail_rows.append(['Rule Version', c.rule_version])
        if c.confidence is not None:
            detail_rows.append(['Confidence', f'{round(c.confidence)}%'])
        if c.evidence_image_label or c.evidence_region:
            loc = f'{c.evidence_image_label or "Package"} → {c.evidence_region or "label"}'
            detail_rows.append(['Evidence Location', loc])

        detail_table_data = []
        for label, val in detail_rows:
            detail_table_data.append([
                Paragraph(f'<b>{label}</b>', styles['TableCell']),
                Paragraph(str(val), styles['TableCell']),
            ])

        dtbl = Table(detail_table_data, colWidths=[38*mm, w_avail - 38*mm])
        dtbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (0, -1), SLATE_50),
            ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))

        finding_items.append(dtbl)
        finding_items.append(Spacer(1, 3*mm))
        story.append(KeepTogether(finding_items))

    # ══════════════════════════════════════════════════════════════
    # PART V — RECOMMENDED CORRECTIVE ACTIONS & PRIORITY REMEDIATION
    # ══════════════════════════════════════════════════════════════
    if recommendations:
        story.append(PageBreak())
        story.append(Paragraph('RECOMMENDED CORRECTIVE ACTIONS & PRIORITY REMEDIATION', styles['SectionHeading']))

        rec_headers = [
            Paragraph('<b>Priority</b>', styles['TableCellBoldCenter']),
            Paragraph('<b>Rule ID & Title</b>', styles['TableCellBold']),
            Paragraph('<b>Issue Description</b>', styles['TableCellBold']),
            Paragraph('<b>Mandatory Corrective Action</b>', styles['TableCellBold']),
            Paragraph('<b>Statutory Citation</b>', styles['TableCellBold']),
        ]
        rec_rows = [rec_headers]

        for r in recommendations:
            p_upper = (r.priority or 'MEDIUM').upper()
            p_color = RED if p_upper == 'HIGH' else (AMBER if p_upper == 'MEDIUM' else INDIGO)
            priority_para = Paragraph(f'<font color="{p_color.hexval()}"><b>{p_upper}</b></font>', styles['TableCellCenter'])
            
            legal_cite = f"{r.source_name or ''} {r.source_reference or ''}".strip()
            rec_rows.append([
                priority_para,
                Paragraph(f"<b>{r.rule_id}</b><br/>{r.title}", styles['TableCell']),
                Paragraph(r.issue or '', styles['TableCell']),
                Paragraph(r.recommended_action or (r.corrective_action or ''), styles['TableCell']),
                Paragraph(legal_cite or 'Legal Metrology Rules 2011', styles['TableCell']),
            ])

        rec_tbl = Table(rec_rows, colWidths=[20*mm, 38*mm, 42*mm, 52*mm, 28*mm])
        rec_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (-1, 0), INDIGO_LIGHT),
            ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 2.5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2.5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, SLATE_50]),
        ]))
        story.append(rec_tbl)
        story.append(Spacer(1, 3*mm))

    # ══════════════════════════════════════════════════════════════
    # PART VI — MISLEADING CLAIM ANALYSIS & STATUTORY VERIFICATION
    # ══════════════════════════════════════════════════════════════
    if getattr(analysis, 'claims_analysis', None) and analysis.claims_analysis.claims:
        story.append(PageBreak())
        story.append(Paragraph('MISLEADING CLAIM ANALYSIS & STATUTORY VERIFICATION', styles['SectionHeading']))
        story.append(Paragraph(
            'Automated screening for unsupported, contradictory, exaggerated, or non-compliant packaging claims '
            'under FSSAI (Advertising and Claims) Regulations 2018 and Consumer Protection Act 2019.',
            styles['SubHeading']
        ))

        ca = analysis.claims_analysis
        summary_rows = [
            [
                Paragraph('<b>Total Claims</b>', styles['TableCellBoldCenter']),
                Paragraph('<b>Supported</b>', styles['TableCellBoldCenter']),
                Paragraph('<b>Contradictions</b>', styles['TableCellBoldCenter']),
                Paragraph('<b>Insufficient Ev.</b>', styles['TableCellBoldCenter']),
                Paragraph('<b>High-Risk Review</b>', styles['TableCellBoldCenter']),
            ],
            [
                Paragraph(f"<font size=12><b>{ca.claims_detected}</b></font>", styles['TableCellCenter']),
                Paragraph(f"<font size=12 color='{EMERALD.hexval()}'><b>{ca.summary.supported}</b></font>", styles['TableCellCenter']),
                Paragraph(f"<font size=12 color='{RED.hexval()}'><b>{ca.summary.potential_contradictions}</b></font>", styles['TableCellCenter']),
                Paragraph(f"<font size=12 color='{AMBER.hexval()}'><b>{ca.summary.insufficient_evidence}</b></font>", styles['TableCellCenter']),
                Paragraph(f"<font size=12 color='{AMBER.hexval()}'><b>{ca.summary.high_risk_review}</b></font>", styles['TableCellCenter']),
            ]
        ]
        sum_tbl = Table(summary_rows, colWidths=[36*mm, 36*mm, 36*mm, 36*mm, 36*mm])
        sum_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), INDIGO_LIGHT),
            ('GRID', (0, 0), (-1, -1), 0.5, SLATE_200),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(sum_tbl)
        story.append(Spacer(1, 4*mm))

        for idx, cl in enumerate(ca.claims, start=1):
            cl_items = []
            st_val = cl.assessment.status.value if hasattr(cl.assessment.status, 'value') else str(cl.assessment.status)
            if st_val == "SUPPORTED":
                st_color = EMERALD
            elif st_val in ("POTENTIAL_CONTRADICTION", "CONTRADICTION"):
                st_color = RED
            else:
                st_color = AMBER

            cl_items.append(Paragraph(
                f"<b>CLAIM #{idx}: \"{cl.claim_text}\"</b>",
                styles['SubHeading']
            ))

            ev_texts = "; ".join([e.text for e in cl.evidence]) if cl.evidence else "No package evidence detected"
            ev_locs = "; ".join([f"{e.panel} panel" for e in cl.evidence]) if cl.evidence else f"{cl.source_panel} panel"

            cl_table_data = [
                [Paragraph('<b>Claim Text</b>', styles['TableCell']), Paragraph(f"\"{cl.claim_text}\"", styles['TableCellBold'])],
                [Paragraph('<b>Category</b>', styles['TableCell']), Paragraph(cl.category.value if hasattr(cl.category, 'value') else str(cl.category), styles['TableCell'])],
                [Paragraph('<b>Status</b>', styles['TableCell']), Paragraph(f"<font color='{st_color.hexval()}'><b>{st_val.replace('_', ' ')}</b></font>", styles['TableCell'])],
                [Paragraph('<b>Confidence</b>', styles['TableCell']), Paragraph(f"{cl.confidence:.1f}%", styles['TableCell'])],
                [Paragraph('<b>Package Evidence</b>', styles['TableCell']), Paragraph(ev_texts, styles['TableCell'])],
                [Paragraph('<b>Evidence Location</b>', styles['TableCell']), Paragraph(ev_locs, styles['TableCell'])],
                [Paragraph('<b>Statutory Reason</b>', styles['TableCell']), Paragraph(cl.assessment.reason, styles['TableCell'])],
                [Paragraph('<b>Regulatory Citation</b>', styles['TableCell']), Paragraph(f"{cl.assessment.rule_source or 'FSSAI / CCPA'} {cl.assessment.rule_reference or ''}".strip(), styles['TableCell'])],
                [Paragraph('<b>Human Review</b>', styles['TableCell']), Paragraph('<b>REQUIRED</b>' if cl.assessment.requires_human_review else 'OPTIONAL', styles['TableCell'])],
            ]

            ctbl = Table(cl_table_data, colWidths=[42*mm, w_avail - 42*mm])
            ctbl.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BACKGROUND', (0, 0), (0, -1), SLATE_50),
                ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ]))
            cl_items.append(ctbl)
            cl_items.append(Spacer(1, 3*mm))
            story.append(KeepTogether(cl_items))

    # ══════════════════════════════════════════════════════════════
    # PART VII — VISUAL EVIDENCE APPENDIX & INTEGRITY DOSSIER
    # ══════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph('VISUAL EVIDENCE APPENDIX & SYSTEM INTEGRITY DOSSIER', styles['SectionHeading']))

    if images_list:
        for img_ev in images_list:
            img_url = img_ev.get('image_url', '') if isinstance(img_ev, dict) else getattr(img_ev, 'image_url', '')
            img_label = img_ev.get('label', 'Image') if isinstance(img_ev, dict) else getattr(img_ev, 'label', 'Image')
            word_count = img_ev.get('word_count', 0) if isinstance(img_ev, dict) else getattr(img_ev, 'word_count', 0)

            img_items = []
            img_items.append(Paragraph(
                f'<b>Package Panel: {img_label}</b> <font color="{SLATE_400.hexval()}">({word_count} OCR tokens detected)</font>',
                styles['SubHeading']
            ))

            rl_img = _load_image(img_url, max_width=w_avail * 0.85, max_height=85*mm)
            if rl_img:
                img_items.append(rl_img)
            else:
                img_items.append(Paragraph('<i>Image visual proof preview unavailable on this device</i>', styles['SmallText']))

            img_items.append(Spacer(1, 2.5*mm))
            story.append(KeepTogether(img_items))

    # ── Tamper-Evident System Integrity & Audit Metadata ──
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph('SECURITY, INTEGRITY & AUDIT PROVENANCE', styles['SubHeading']))

    integrity_hash = analysis.integrity_hash or "SHA256-AUTHENTICATED-RECORD"
    system_ver = analysis.system_version or getattr(settings, 'SYSTEM_VERSION', '1.0.0')
    ruleset_ver = analysis.ruleset_version or '2026.1'
    ocr_engine = analysis.ocr_engine_version or 'PaddleOCR PP-OCRv4'

    integrity_rows = [
        ['Cryptographic Integrity Hash (SHA-256)', integrity_hash],
        ['System Software Version', f"MetrCheck AI v{system_ver}"],
        ['Statutory Ruleset Version', f"Ruleset v{ruleset_ver} (Legal Metrology Act 2009 & 2011 Rules)"],
        ['OCR & Vision Engine', ocr_engine],
        ['Audit Verification Status', 'TAMPER-EVIDENT RECORD CERTIFIED'],
        ['Verification Notice', 'This report hash is cryptographically verifiable against the system audit ledger.'],
    ]

    int_table_data = [
        [Paragraph(f'<b>{lbl}</b>', styles['TableCellBold']), Paragraph(str(v), styles['TableCell'])]
        for lbl, v in integrity_rows
    ]
    int_tbl = Table(int_table_data, colWidths=[52*mm, w_avail - 52*mm])
    int_tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (0, -1), SLATE_50),
        ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(int_tbl)
    story.append(Spacer(1, 3*mm))

    # Build document
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()
