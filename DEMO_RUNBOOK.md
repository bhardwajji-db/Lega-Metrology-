# MetrCheck AI — 10-Minute SIH Judge Demonstration Runbook
**Smart India Hackathon 2026 | Problem Statement: PS 26034 (DoCA / MoCA)**  
**Project:** AI-Assisted Statutory Package Compliance & Enforcement System

---

## 1. Setup & Environment

### Access URLs
| Component | Local URL | Description |
|---|---|---|
| **Frontend Web Application** | `http://localhost:5173` | React 18 + Vite + Tailwind CSS UI |
| **Backend API Documentation** | `http://localhost:8000/docs` | FastAPI Swagger / OpenAPI Docs |
| **Backend Health Check** | `http://localhost:8000/api/health` | Service & OCR Engine Status |

### Default Demonstration Accounts (RBAC)
| Role | Username | Password | Permissions |
|---|---|---|---|
| **Enforcement Officer** | `officer` | `officer123` | Statutory screening, evidence verification, show-cause notices |
| **Audit Officer** | `audit` | `audit123` | Quality inspection, technical rule verification, OCR calibration |
| **Merchant / Public** | `merchant` | `merchant123` | Self-compliance pre-screening & report downloads |
| **Administrator** | Provisioned via CLI | `[REDACTED — ADMIN PASSWORD]` | Full system governance, user management, audit logs via `/admin/login` |

### Quick Start Verification
1. **Backend**:
   ```bash
   cd backend
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
2. **Frontend**:
   ```bash
   cd frontend
   npm run dev
   ```
3. Open `http://localhost:5173` in any modern web browser (Chrome / Edge / Firefox).

---

## 2. Executive Narrative (1-Minute Opening Pitch)

> **"Respected Judges, over 60% of pre-packaged commodities sold in retail markets and e-commerce platforms fail mandatory statutory labeling requirements under the Legal Metrology (Packaged Commodities) Rules, 2011 and FSSAI packaging regulations.**
>
> Today, enforcement officers from the Department of Consumer Affairs (DoCA) and State Legal Metrology Wings are constrained by slow, manual, subjective inspections covering less than 1% of market inventory.
>
> **MetrCheck AI** solves this with an enterprise-grade, automated statutory compliance and enforcement engine:
> 1. **Multi-Pass OCR & Visual Grounding**: Extracts text from multi-panel product packaging with pixel-accurate bounding box evidence.
> 2. **Rule 12 Mathematical Font Calibration**: Converts pixel dimensions to physical millimeters ($mm = px \times \text{factor}$) to verify statutory minimum numeral/letter heights (1.0mm to 6.0mm).
> 3. **Statutory Rule Engine**: Evaluates 10+ Legal Metrology Rules (LM-001 through LM-010) plus FSSAI regulations.
> 4. **Enforcement Automation**: Generates multi-format audit dossiers (PDF/Excel/CSV/JSON) and official Show-Cause Notices under Sections 36 & 38 of the Legal Metrology Act, 2009."

---

## 3. Step-by-Step Demonstration Walkthrough (10 Minutes)

### Step 1: Login & Role-Based Access Control (00:00 – 01:00)
1. Navigate to `http://localhost:5173/login`.
2. Enter **Username**: `officer` | **Password**: `officer123`.
3. Click the **"Sign In"** button.
4. **Judge Focus**: Point out the active user badge in the bottom-left sidebar: `Enforcement Officer (State Legal Metrology Wing)`. Note that role-based access control (RBAC) restricts administrative actions while exposing enforcement tools like statutory notices.

---

### Step 2: Multi-Panel Package Artwork Analysis (01:00 – 03:00)
1. Click **"Analyze Package"** (`/analyze`) in the sidebar navigation.
2. Observe the multi-panel input slots:
   - **Front Panel (Required)**: Captures Brand, Product Name, Net Quantity, Veg/Non-Veg logo.
   - **Back Panel (Recommended)**: Captures MRP, Dates (Mfg/Expiry), FSSAI Licence No., Manufacturer Address, Ingredients.
   - **Side Panels 1 & 2 (Optional)**: Captures Consumer Care Cell details, Nutritional Facts, Batch No.
3. **Sample Image Selection**:
   - The project repository includes designated test folders in `test_data/`:
     - `test_data/compliant/` — Reference compliant package samples.
     - `test_data/violation/` — Samples with missing MRP, incorrect net qty units, or missing manufacturer PIN code.
     - `test_data/warning/` — Samples with borderline font sizes or missing consumer care email.
   - *If custom sample files are not placed in `test_data/`*, drag and drop sample images from `backend/fixtures/` (`alpino_front.png` and `alpino_back.png`), or upload any packaged food/commodity photograph from your machine.
4. Click **"Run Statutory Compliance Analysis"**.
5. **Judge Focus**: Watch the real-time pipeline visualizer transition through 8 transparent stages: *Images Received $\rightarrow$ Quality & Blur Check $\rightarrow$ OCR Text Extraction $\rightarrow$ Entity Parsing $\rightarrow$ Legal Metrology Screening $\rightarrow$ Rule 12 Font Height Calibration $\rightarrow$ Dossier Compilation*.

--- 

### Step 3: Executive Dashboard & Score Card (03:00 – 04:15)
1. Click **"Dashboard"** (`/`) in the sidebar.
2. Review the high-level compliance intelligence:
   - **Compliance Health Score Card** (Overall score out of 100).
   - **Key Metrics**: Total Analyzed, Compliant %, Violations %, Average Score.
   - **Recent Statutory Inspections**: Quick access table with timestamp, product name, status badges (`COMPLIANT`, `NON_COMPLIANT`, `WARNING`), and direct links.
3. Click on the latest analyzed product record to open the **Results** page.

---

### Step 4: Deep-Dive Statutory Audit & Rule 12 Font Calibration (04:15 – 06:15)
On the **Results** page (`/results/:id`):
1. **Interactive Evidence Viewer (Visual Grounding)**:
   - Click on the package image or any rule item (e.g., `LM-003 Net Quantity` or `LM-004 MRP`).
   - The viewer highlights the exact bounding box on the original package image where the text was detected, eliminating AI hallucination.
2. **Rule 12 Font Size Analysis Card**:
   - Show the physical font height estimates:
     - **Extracted Net Quantity Height**: e.g., `~3.6 mm` (Statutory Minimum: `2.0 mm` for 100g pack $\rightarrow$ **COMPLIANT**).
     - **Extracted MRP Height**: e.g., `~2.7 mm` (Statutory Minimum: `2.0 mm` $\rightarrow$ **COMPLIANT**).
     - **Readability & OCR Quality Score**: e.g., `88.5 / 100 (EXCELLENT)`.
   - **Judge Focus**: Explain that font height conversion uses the calibrated factor configured in backend settings (`FONT_PX_TO_MM_FACTOR` or `OCR_IMAGE_DPI`), satisfying Rule 12 statutory legibility tables.
3. **Statutory Rule Checklist**:
   - Filter by domain (`Legal Metrology` vs `FSSAI`) or status (`Pass`, `Fail`, `Warning`).
   - Expand `LM-001` (Manufacturer Details), `LM-003` (Net Quantity), `LM-004` (MRP with "inclusive of all taxes"), `LM-005` (Date of Manufacture), `LM-006` (Consumer Care), `LM-007` (Unit Sale Price), `LM-008` (Country of Origin).
4. **Prioritized Corrective Recommendations**:
   - Review actionable, severity-ranked guidance for manufacturers and enforcement officers.

---

### Step 5: Multi-Format Audit Dossier Export (06:15 – 07:15)
On the top right of the **Results** page:
1. Click **"PDF Report"**:
   - Downloads a formal Government of India / DoCA formatted statutory inspection dossier.
   - Contains executive summary, rule checklist, font analysis table, embedded evidence thumbnail, and a tamper-evident verification QR code.
2. Click **"Excel"**:
   - Downloads an editable multi-tab spreadsheet (`.xlsx`) suitable for departmental record-keeping and bulk audit registers.
3. Click **"CSV Export"** or **"JSON"**:
   - Shows machine-readable exports for integration with state enforcement databases (e.g., National Consumer Helpline / e-Daakhil).

---

### Step 6: E-Commerce Product Listing Text Screening (07:15 – 08:15)
1. Click **"Listing Check"** (`/analyze-listing`) in the sidebar.
2. Explain to the judges: *"E-commerce marketplaces (Amazon, Flipkart, Blinkit, Zepto) list millions of pre-packaged goods. Inspectors need to verify raw listing text instantly without downloading images."*
3. Click **"Load Sample"** (or paste text e.g., `"Maggi 2-Minute Masala Noodles 70g, MRP Rs 14 incl. of all taxes, Mfg: 08/2026, FSSAI Lic 10012011000001, Nestlé India Ltd, 100/101 World Trade Centre, New Delhi 110001, Care: 1800-103-1947 care@in.nestle.com, Country of Origin: India"`).
4. Click **"Analyze Listing Text"**.
5. Observe instantaneous entity extraction and rule validation in < 500 milliseconds.

---

### Step 7: Administrator Governance & User Management (08:15 – 09:00)
1. Navigate to `/admin/login` (or click "Administrator Portal" in footer).
2. Log in with provisioned Administrator credentials.
3. Click **"User Management"** (`/admin/users`) in the sidebar.
4. Demonstrate governance actions:
   - **Create Account**: Add a new officer (e.g., `officer_mumbai`, Role: `Enforcement Officer`, Jurisdiction: `Maharashtra State Legal Metrology Controller`).
   - **Edit / Password Reset**: Update jurisdiction or reset officer credentials.
   - **Role Segregation**: Explain that public merchants cannot access officer notices or user administration.

---

### Step 8: Statutory Enforcement Notice & Penalty Calculation (09:00 – 10:00)
1. Switch back to an inspection result with a non-compliance (or open Demo Case 2 from `/demo`).
2. Logged in as `officer`, click the **"Statutory Notice Draft"** button (Gavel icon).
3. The **Statutory Show-Cause Notice Generator Modal** opens:
   - Displays a formal legal notice referencing **Section 36 & Section 38 of the Legal Metrology Act, 2009**.
   - Includes official Notice Reference Number (`LM/ENF/2026/SCN-...`), Officer ID, Officer Jurisdiction, and itemized statutory violations.
   - Computes compounding penalty estimate under Section 36(1) (₹25,000 for 1st offense, up to ₹50,000 for subsequent offenses).
4. Click **"Copy Notice Text"** or **"Print / Save PDF Notice"** to demonstrate immediate field dispatch.

---

## 4. Expected Demo Outcomes & Alignment with PS 26034

| Feature Demonstrated | What the Judge Sees | Statutory & Technical Significance (PS 26034) |
|---|---|---|
| **Multi-Panel OCR & Visual Grounding** | Bounding boxes highlight exact coordinates of Net Qty, MRP, Mfg date on image. | Eliminates LLM hallucination; provides undeniable visual proof admissible in appellate hearings. |
| **Rule 12 Mathematical Font Sizing** | Physical mm estimation ($mm = px \times \text{factor}$) compared against statutory table. | First-in-class automated verification of Rule 12 numeral/letter height legibility standards. |
| **Configurable Calibration (`config.py`)** | `FONT_PX_TO_MM_FACTOR` and `OCR_IMAGE_DPI` configurable via environment variables. | Adapts accurately to 300 DPI flatbed laboratory scans vs 96/141 DPI field camera captures. |
| **10+ Legal Metrology Rules** | Explicit checks for Rule 6(1)(a)-(h), Unit Sale Price, Consumer Care PIN codes. | Complete end-to-end statutory coverage matching Legal Metrology (Packaged Commodities) Rules, 2011. |
| **E-Commerce Listing Text Screening** | Sub-second compliance verification of raw text strings. | Enables automated scraping and real-time surveillance of e-commerce marketplaces. |
| **Statutory Show-Cause Notice Generator** | Ready-to-serve notice under Sections 36/38 with penalty calculation. | Converts technical audit findings into immediate administrative legal enforcement. |

---

## 5. Live Demonstration Fallbacks & Resilience Strategies

| Scenario / Potential Glitch | Recommended Fallback Action | Technical Resilience Built-In |
|---|---|---|
| **OCR Processing Delay / Camera Glare** | Use **Listing Check** (`/analyze-listing`) with the pre-loaded sample text. | Listing check bypasses OCR and tests entity parsing & compliance rules instantly. |
| **Zero Image Files Available on Machine** | Click **"Demo Mode"** (`/demo`) in the sidebar $\rightarrow$ select **Case 1 (Compliant)**, **Case 2 (Violation)**, or **Case 3 (Warning)**. | Demo mode loads pre-verified benchmark analyses without requiring file uploads. |
| **No Internet / Offline Venue** | Continue demonstration normally. | System runs **100% locally** (local SQLite DB, local PaddleOCR deep learning engine, local rule evaluator). |
| **LLM API Quota Exceeded / Latency** | System automatically falls back to regex extraction. | Backend includes dual-tier architecture: when LLM API key is empty/fails, regex extractor parses all statutory fields with zero downtime. |

---

## 6. Key Statutory Facts & Legal Metrology Talking Points

### Legal Metrology (Packaged Commodities) Rules, 2011 (as amended)
1. **Rule 6(1) Mandatory Declarations**: Every pre-packaged commodity must declare:
   - **Rule 6(1)(a)**: Name and complete address of the manufacturer, packer, or importer (including 6-digit PIN code).
   - **Rule 6(1)(b)**: Generic or common name of the commodity.
   - **Rule 6(1)(c)**: Net quantity in standard SI units (g, kg, ml, l, or number).
   - **Rule 6(1)(d)**: Month and year of manufacture, packing, or import.
   - **Rule 6(1)(e)**: Maximum Retail Price (MRP) in the exact format `"MRP Rs. ... incl. of all taxes"`.
   - **Rule 6(1)(f)**: Consumer Care Cell contact details (Name/Designation, Postal Address, Phone/Toll-Free, and Email).
   - **Rule 6(1)(n)**: Unit Sale Price (USP) per gram, kilogram, milliliter, liter, or piece for packages containing more than 1 unit.
   - **Rule 6(1)(b)**: Country of Origin for imported commodities.

2. **Rule 12 Table — Statutory Minimum Font Heights**:
   | Net Quantity / Weight Range | Minimum Height of Numerals & Letters |
   |---|---|
   | $\le 50\text{ g / ml}$ | **$1.0\text{ mm}$** |
   | $50\text{ g} < \text{Net Qty} \le 200\text{ g / ml}$ | **$2.0\text{ mm}$** |
   | $200\text{ g} < \text{Net Qty} \le 1000\text{ g / ml}$ ($1\text{ kg}$) | **$4.0\text{ mm}$** |
   | $> 1000\text{ g / } 1\text{ kg / } 1\text{ L}$ | **$6.0\text{ mm}$** |

3. **Legal Metrology Act, 2009 — Enforcement Provisions**:
   - **Section 36(1)**: Penalty for manufacturing, packing, or selling non-standard or non-compliant packages — Fine up to ₹25,000 (first offense), up to ₹50,000 (second offense), and up to ₹1,00,000 or imprisonment up to 1 year for subsequent offenses.
   - **Section 38**: Penalty for non-declaration of statutory information on pre-packaged commodities.
   - **Section 48**: Compounding of offenses by authorized Legal Metrology Controllers.

4. **Department Identity**:
   - **DoCA**: Department of Consumer Affairs, Ministry of Consumer Affairs, Food and Public Distribution, Government of India.
