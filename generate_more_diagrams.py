import os
from PIL import Image, ImageDraw, ImageFont

def create_compliance_decision_diagram(output_path: str):
    w, h = 1800, 780
    img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("arialbd.ttf", 34)
        font_subtitle = ImageFont.truetype("arial.ttf", 22)
        font_header = ImageFont.truetype("arialbd.ttf", 24)
        font_box_title = ImageFont.truetype("arialbd.ttf", 21)
        font_text = ImageFont.truetype("arial.ttf", 18)
        font_badge = ImageFont.truetype("arialbd.ttf", 18)
    except Exception:
        font_title = ImageFont.load_default()
        font_subtitle = font_title
        font_header = font_title
        font_box_title = font_title
        font_text = font_title
        font_badge = font_title

    # Top banner
    draw.rectangle([(0, 0), (w, 100)], fill=(244, 63, 94))
    draw.text((40, 25), "METRCHECK AI — STATUTORY COMPLIANCE & SCORING DECISION MATRIX", fill=(255, 255, 255), font=font_title)
    draw.text((40, 65), "Codified Rules, Weighted Point Calculation, and Multi-Level Threshold Classification", fill=(255, 228, 230), font=font_subtitle)

    # 3 Main Pillars
    pillars = [
        ("1. LEGAL METROLOGY (9 Rules)",
         [
             ("LM-001: Mfr/Packer/Importer", "Rule 6(1)(a) — Physical address & PIN code"),
             ("LM-002: Common / Generic Name", "Rule 6(1)(b) — Identity of commodity"),
             ("LM-003: Net Quantity & Units", "Rule 6(1)(c) — Standard metric units (g, kg, ml)"),
             ("LM-004: Maximum Retail Price", "Rule 6(1)(e) — MRP inclusive of all taxes"),
             ("LM-005: Consumer Care Info", "Rule 6(1)(f) — Helpline phone, email & address"),
             ("LM-006: Country of Origin", "Rule 6(1)(d) — Mandatory for all goods"),
             ("LM-007: Unit Sale Price (USP)", "Rule 6(11) — Price per g/kg/ml for consumers"),
             ("LM-008: Date of Mfg / Pre-pack", "Rule 6(1)(d) — Month & Year marking"),
             ("LM-009: Misleading & Rule 12", "Rule 6(1)(e) & Rule 12 min font height"),
         ],
         (255, 241, 242), (244, 63, 94), (190, 18, 60)),

        ("2. FSSAI FOOD REGS (5 Rules)",
         [
             ("FS-001: 14-Digit FSSAI Lic/Logo", "FSS Regulations — 14 digits & state decoding"),
             ("FS-002: Standardized Food Name", "FSS Act — Specific commodity denomination"),
             ("FS-003: List of Ingredients", "FSS Labelling — Descending order of weight"),
             ("FS-004: Nutrition Facts Panel", "FSS Labelling — Energy, Carbs, Sugar, Fats"),
             ("FS-005: Date Marking / Expiry", "FSS Labelling — Best Before / Use-By date"),
             ("Applicability Condition", "Automatically activated for food commodities"),
             ("Non-Food Handling", "Marked NOT_APPLICABLE (excluded from score)"),
             ("OCR Character Repair", "Auto-recovers 'FSSA1' and swapped digits"),
             ("State Code Parsing", "Decodes Central vs State Licensing jurisdiction"),
         ],
         (240, 253, 244), (34, 197, 94), (21, 128, 61)),

        ("3. SCORING & VERDICTS",
         [
             ("Weighted Scoring Formula", "Earned Points / Applicable Rules * 100"),
             ("PASS Weight = 1.0 (100%)", "Full compliance verified with high confidence"),
             ("WARNING Weight = 0.5 (50%)", "Minor defect / non-standard abbreviation"),
             ("NEEDS_REVIEW Weight = 0.85", "Uncertain OCR / requires visual inspection"),
             ("FAIL Weight = 0.0 (0%)", "Missing mandatory statutory declaration"),
             ("NOT_APPLICABLE = Excluded", "Excluded completely from total denominator"),
             ("Status: COMPLIANT", "Score >= 80% & Zero statutory failures"),
             ("Status: REVIEW REQUIRED", "Score < 80% or inspection flags present"),
             ("Status: POTENTIAL NON-COMPL", "Triggered if ANY statutory FAIL occurs"),
         ],
         (238, 242, 255), (99, 102, 241), (67, 56, 202)),
    ]

    card_w = 540
    card_h = 630
    start_x = 45
    start_y = 125
    spacing = 45

    for i, (title, items, bg_c, border_c, text_c) in enumerate(pillars):
        x = start_x + i * (card_w + spacing)
        y = start_y

        draw.rounded_rectangle([(x+4, y+4), (x + card_w + 4, y + card_h + 4)], radius=14, fill=(226, 232, 240))
        draw.rounded_rectangle([(x, y), (x + card_w, y + card_h)], radius=14, fill=bg_c, outline=border_c, width=2)
        
        # Header
        draw.rounded_rectangle([(x, y), (x + card_w, y + 46)], radius=14, fill=border_c)
        draw.text((x + 18, y + 10), title, fill=(255, 255, 255), font=font_header)

        # Items
        item_y = y + 60
        for item_title, item_sub in items:
            draw.rounded_rectangle([(x + 12, item_y), (x + card_w - 12, item_y + 54)], radius=8, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
            draw.text((x + 22, item_y + 6), item_title, fill=text_c, font=font_box_title)
            draw.text((x + 22, item_y + 30), item_sub, fill=(71, 85, 105), font=font_text)
            item_y += 62

    img.save(output_path, "PNG")
    print(f"Saved compliance decision diagram: {output_path}")

def create_rbac_diagram(output_path: str):
    w, h = 1800, 720
    img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("arialbd.ttf", 34)
        font_subtitle = ImageFont.truetype("arial.ttf", 22)
        font_header = ImageFont.truetype("arialbd.ttf", 24)
        font_box_title = ImageFont.truetype("arialbd.ttf", 22)
        font_text = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        font_title = ImageFont.load_default()
        font_subtitle = font_title
        font_header = font_title
        font_box_title = font_title
        font_text = font_title

    # Header
    draw.rectangle([(0, 0), (w, 100)], fill=(16, 185, 129))
    draw.text((40, 25), "METRCHECK AI — SECURITY & ROLE-BASED ACCESS CONTROL (RBAC)", fill=(255, 255, 255), font=font_title)
    draw.text((40, 65), "Cryptographic Auth Architecture, Role Hierarchy, and Access Permission Matrix", fill=(209, 250, 229), font=font_subtitle)

    # 3 Roles
    roles = [
        ("1. SYSTEM ADMINISTRATOR (ADMIN)",
         "Full Administrative Control & User Governance",
         [
             ("User Account Creation", "Provision new Officers & Merchants (/api/auth/users)"),
             ("User Modification & Deletion", "Update profiles, reset passwords, delete accounts"),
             ("Global History Management", "Full audit log access & complete database purge"),
             ("System Configuration", "Configure OCR engines, storage paths & test isolation"),
             ("Root Privileges", "Protected: Admin account cannot be altered by lower roles"),
         ],
         (240, 253, 244), (16, 185, 129), (4, 120, 87)),

        ("2. ENFORCEMENT OFFICER (DoCA)",
         "Regulatory Inspection & Enforcement Workflows",
         [
             ("Package & Listing Screening", "Upload multi-panel images or paste listing text"),
             ("Evidence & Bounding Boxes", "Review 2D spatial overlays & OCR confidence scores"),
             ("Penalty Calculator (Sec 36/38)", "Estimate statutory fines (1st vs repeat offences)"),
             ("Show-Cause Notice Generator", "Export formatted statutory notices for violators"),
             ("Audit Report Downloads", "Export multi-page PDF, XLSX, CSV, JSON dossiers"),
         ],
         (238, 242, 255), (79, 70, 229), (67, 56, 202)),

        ("3. MERCHANT / PUBLIC USER",
         "Pre-Market Compliance Self-Screening",
         [
             ("Self-Service Label Audit", "Upload packaging artwork to detect omissions"),
             ("E-Commerce Listing Check", "Verify catalogue descriptions before publishing"),
             ("Corrective Action Guidance", "Receive step-by-step label rectification steps"),
             ("Rule Registry Browser", "Explore Legal Metrology & FSSAI statutory standards"),
             ("Isolated Permissions", "No access to enforcement tools or admin console"),
         ],
         (254, 243, 199), (217, 119, 6), (180, 83, 9)),
    ]

    card_w = 540
    card_h = 570
    start_x = 45
    start_y = 125
    spacing = 45

    for i, (title, subtitle, perms, bg_c, border_c, text_c) in enumerate(roles):
        x = start_x + i * (card_w + spacing)
        y = start_y

        draw.rounded_rectangle([(x+4, y+4), (x + card_w + 4, y + card_h + 4)], radius=14, fill=(226, 232, 240))
        draw.rounded_rectangle([(x, y), (x + card_w, y + card_h)], radius=14, fill=bg_c, outline=border_c, width=2)
        
        # Header
        draw.rounded_rectangle([(x, y), (x + card_w, y + 46)], radius=14, fill=border_c)
        draw.text((x + 18, y + 10), title, fill=(255, 255, 255), font=font_header)

        # Subtitle
        draw.text((x + 18, y + 56), subtitle, fill=(100, 116, 139), font=font_text)
        draw.line([(x + 18, y + 84), (x + card_w - 18, y + 84)], fill=(226, 232, 240), width=1)

        # Perms
        item_y = y + 96
        for perm_title, perm_desc in perms:
            draw.rounded_rectangle([(x + 12, item_y), (x + card_w - 12, item_y + 80)], radius=8, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
            draw.text((x + 22, item_y + 10), perm_title, fill=text_c, font=font_box_title)
            draw.text((x + 22, item_y + 40), perm_desc, fill=(71, 85, 105), font=font_text)
            item_y += 90

    img.save(output_path, "PNG")
    print(f"Saved RBAC diagram: {output_path}")

if __name__ == "__main__":
    os.makedirs("doc_assets", exist_ok=True)
    create_compliance_decision_diagram("doc_assets/compliance_tree_diagram.png")
    create_rbac_diagram("doc_assets/rbac_security_diagram.png")
