# PHASE 5 — SIH 2024 / 2026 DEMONSTRATION RUNBOOK
## MetrCheck AI — Automated Legal Metrology & Food Safety Packaging Compliance Verifier

---

## 1. Pre-Demo Checklist (5 Minutes Before Presentation)

- [ ] **Windows Laptop Power**: Connect to AC power (prevents CPU throttling during PaddleOCR deep learning inference).
- [ ] **Python Virtual Environment**: Confirm `.\venv\Scripts\python.exe` is present and functional.
- [ ] **Node.js / npm**: Confirm `node -v` (v18+) and frontend dependencies installed.
- [ ] **PaddleOCR Model Cache**: Verified `~/.paddlex/official_models/` exists locally (100% offline capable).
- [ ] **Sample Images Prepared**:
  - `backend/fixtures/alpino_front.png` (*Alpino Super Oats Front*)
  - `backend/fixtures/alpino_back.png` (*Alpino Super Oats Back*)
  - Optional demo non-food listing text.
- [ ] **Browser Prepared**: Chrome/Edge open to `http://localhost:5173`.

---

## 2. Startup Commands

Open two PowerShell / Command Prompt terminals in the project root:

### Terminal 1: Backend Server (FastAPI + Uvicorn)
```powershell
.\venv\Scripts\python.exe runner.py
# OR:
# .\venv\Scripts\uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```
*Backend URL*: `http://localhost:8000`  
*API Docs*: `http://localhost:8000/docs`

### Terminal 2: Frontend Web UI (React + Vite)
```powershell
cd frontend
npm run dev
```
*Frontend URL*: `http://localhost:5173`

---

## 3. Golden Demo Sequence (Judge-Facing Presentation Flow)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 1. Problem Introduction (30s)                                                   │
│    "Manual packaging compliance checking takes 20-30 mins per SKU, leading to   │
│     widespread consumer fraud and uninspected packaged goods."                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 2. Real Package Image Upload (20s)                                              │
│    - Navigate to Analyze page                                                   │
│    - Upload Front Label image into Front slot                                   │
│    - Upload Back Label image into Back slot                                     │
│    - Click "Start Full Packaging Analysis"                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 3. Deep Learning & OCR Pipeline in Action (40s)                                 │
│    - Explain the live pipeline stages displayed in the UI:                      │
│      Image Quality Check -> Deep Learning OCR -> Extraction -> Rules -> Proof   │
│    - PaddleOCR extracts ~447 real text tokens on CPU with orientation handling  │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 4. Compliance Dashboard & Score (30s)                                           │
│    - Show Overall Compliance Score (96.5%) & Status (REVIEW REQUIRED)           │
│    - Explain that MetrCheck AI evaluates both Legal Metrology (LM-001..009)     │
│      and FSSAI Labelling Regulations (FS-001..005)                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 5. Human-Verifiable Evidence Viewer (45s)                                       │
│    - Open Evidence Viewer                                                       │
│    - Click LM-002 (Generic Name) -> Show tight bounding box on Front image      │
│    - Click FS-001 (FSSAI Licence) -> Show exact 14-digit token on Back image    │
│    - Click LM-003 (Net Quantity) -> Show exact weight line                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 6. Explainable Review & Proviso Handling (30s)                                  │
│    - Click LM-004 (MRP) -> Explain why faint dot-matrix stamp flags NEEDS_REVIEW │
│    - Click LM-008 -> Explain Rule 6(1)(d) food proviso delegation to FSSAI      │
│    - Click LM-009 -> Explain calculated pricing integrity check                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 7. Controlled Failure & Immediate Recovery Demo (30s)                           │
│    - Upload a corrupt/non-image file -> System cleanly rejects with HTTP 400    │
│    - Re-upload valid package -> Immediate instant success                       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. What to Show vs What NOT to Show

| DO SHOW (Core Strengths) | DO NOT SHOW (Avoid Misleading) |
|---|---|
| Real live PaddleOCR text extraction from camera/upload | Do not claim LLM is hallucinating compliance rules |
| Multi-image front/back evidence mapping | Do not claim pixel font-size is certified legally |
| Visual bounding boxes on statutory tokens | Do not claim system replaces statutory legal courts |
| Explainable `NEEDS_REVIEW` on faint ink stamps | Do not claim 100% OCR accuracy on blurred/glare labels |
| Food vs Non-food automatic rule switching | Do not use synthetic fake mock data during live demo |

---

## 5. Technical Explanation for Each Pipeline Stage

1. **Image Ingestion**:
   - Accepts multi-panel uploads (Front, Back, Sides). Sanitizes dimensions to $\le 1800\text{px}$ preserving aspect ratio.
2. **Deep Learning OCR (PaddleOCR PP-OCRv4)**:
   - Uses DBNet detection + SVTR recognition on CPU. Handles rotated text, angled packaging, and high-density information panels.
3. **Deterministic Declaration Extraction**:
   - Contextually anchored NLP patterns and lookaheads extract MRP, Net Qty, FSSAI Lic, Mfg Address, and Ingredients.
4. **Regulatory Rule Evaluation**:
   - Legal Metrology (Packaged Commodities) Rules 2011 (Rules 6, 11, 12, 18) and FSSAI 2020 regulations evaluated deterministically.
5. **Precise Evidence Localization**:
   - Adheres to the **Minimum Evidence Region Principle**. Encloses only the exact statutory tokens supporting each finding.

---

## 6. Failure Recovery Procedure

If a demo error occurs (e.g. accidental wrong file upload):
1. The UI will display a red alert badge with the specific server response (e.g., *"Uploaded file is corrupted or not a valid image"*).
2. The UI automatically resets `isProcessing` to `false`.
3. Simply click *"Clear All"* or re-select the valid `alpino_front.png` and `alpino_back.png` files and click *"Start Analysis"*.

---

## 7. Comprehensive Judge Q&A Guide (40 Technical Questions)

### Core Concept & Problem
1. **Why is this problem needed?**
   - India has millions of packaged retail commodities. State Legal Metrology and Food Safety enforcement officers cannot manually inspect billions of packages. Non-compliant packaging leads to consumer overpricing, hidden quantities, and health hazards.
2. **Why can't this be checked manually?**
   - Manual checking is slow (20–30 mins/pack), inconsistent, and prone to human oversight. MetrCheck AI screens in seconds with complete visual proof.
3. **What exactly does AI do in this system?**
   - AI (Deep Learning Computer Vision via PaddleOCR) detects and recognizes text characters, angles, and bounding polygons from natural camera photos.
4. **Why PaddleOCR?**
   - PaddleOCR (PP-OCRv4) uses modern DBNet detection and SVTR recognition, specifically optimized for irregular, curved, and rotated text on consumer packaging.
5. **Why not Tesseract?**
   - Tesseract relies on legacy binarization and struggles with noisy packaging backgrounds, colored gradients, curved text lines, and rotated stamps.
6. **How does OCR work in this project?**
   - `PaddleOCREngine` runs text detection $\to$ angle orientation classification $\to$ text line recognition, returning tokens, confidences, and bounding boxes.

### Extraction & Compliance Logic
7. **How does extraction work?**
   - Deterministic NLP extractors use contextual proximity windows, unit normalization, and optical character repair dictionaries.
8. **How does compliance checking work?**
   - The compliance engine feeds extracted declarations into rule evaluators representing statutory requirements and computes mathematical compliance scores.
9. **How are Legal Metrology rules represented?**
   - As declarative `RuleDefinition` objects grounded in Legal Metrology (Packaged Commodities) Rules 2011 (e.g., `LM-001` to `LM-009`).
10. **How are FSSAI rules handled?**
    - Governed by FSSAI (Labelling and Display) Regulations 2020 (`FS-001` to `FS-005`), active only for food products.
11. **How does the system know whether a product is food?**
    - `PackageContext.infer_context` scans for FSSAI licence presence, nutritional tables, ingredients lists, and food commodity keywords.
12. **How does evidence localization work?**
    - `EvidenceLocator` matches statutory declaration values to OCR token sequences, enforcing spatial proximity constraints to build tight bounding boxes.
13. **How do you prevent wrong OCR from causing false compliance?**
    - High confidence thresholds ($\ge 70\%$) are required for `PASS`. Ambiguous or low-confidence tokens are flagged as `NEEDS_REVIEW`.
14. **What happens when OCR confidence is low?**
    - The rule is assigned `NEEDS_REVIEW` with an interactive visual highlight and recommendation for human manual inspection.
15. **What happens if the image is blurry?**
    - Laplacian variance quality assessment flags the image as low clarity and alerts the inspector to re-capture the image.
16. **What happens if information is missing?**
    - The rule fails (`FAIL`), reducing the score and generating a statutory violation notice.

### Multi-Image & Evidence Binding
17. **How does the system handle multiple images?**
    - Images are labeled (Front, Back, Side 1, Side 2) and processed. Words retain their `image_index` to map evidence to the exact photo.
18. **How do you know which evidence belongs to which image?**
    - Each `EvidenceItem` contains `image_index`, `image_label`, and normalized coordinates relative to that specific panel.
19. **Why does MRP sometimes show NEEDS_REVIEW?**
    - Dot-matrix stamped prices or faint ink are flagged for manual verification rather than guessing incorrect pricing.
20. **Why can a rule be NOT_APPLICABLE?**
    - Non-food commodities do not require FSSAI checks. Single-ingredient foods are exempt from ingredient tables. Food packages delegate date marking under Rule 6(1)(d).
21. **What is DERIVED_FIELD evidence?**
    - A calculated compliance check (e.g., `LM-009` verifying USP mathematically matches $\text{MRP} / \text{Net Qty}$) that has no single visual token.

### Legal & Production Boundaries
22. **Is this legally certifying a package?**
    - No. MetrCheck AI is a pre-enforcement screening and audit support tool. Statutory authority remains with the designated government officer.
23. **What are the limitations?**
    - CPU inference takes ~17s per image; severe motion blur requires re-capture; physical millimeter font size is estimated from calibrated pixels.
24. **What happens if regulations change?**
    - Rules are decoupled in the `compliance/rules/` registry and can be updated without altering the OCR or extraction engine.
25. **How can this become production-ready?**
    - Deploy on GPU-enabled edge/cloud instances (reducing latency to <1.5s), connect to national FSSAI FoSCoS database via API, and bundle mobile apps.

### Architecture & Engineering
26. **What is the backend architecture?**
    - FastAPI REST API with async endpoints, Pydantic data schemas, and thread-safe deep learning inference locks.
27. **What is the frontend architecture?**
    - React 19, TypeScript, Vite, Tailwind CSS, Lucide icons, and interactive SVG Evidence Viewer.
28. **What API endpoint is used?**
    - `POST /api/analyze` (multipart form data for multi-image upload).
29. **Why FastAPI?**
    - High performance, native async support, automatic OpenAPI schema generation, and robust validation.
30. **Why React/Vite?**
    - Sub-millisecond HMR during development, lightweight client bundle, and fast component re-renders for interactive SVG overlays.
31. **How is SQLite used?**
    - Persistent local storage of analysis records in WAL mode with busy timeout handling.
32. **How is PaddleOCR model reuse handled?**
    - Global thread-safe singleton (`_PADDLE_OCR_INSTANCE`) initialized on cold start and cached across all subsequent requests.
33. **How do you handle concurrent requests?**
    - `_PADDLE_INFERENCE_LOCK` serializes C++ model executions to prevent thread memory corruption.
34. **What happens if the backend crashes?**
    - Uvicorn auto-restarts; database in WAL mode guarantees zero data corruption.
35. **What happens if an uploaded file is corrupted?**
    - PIL integrity check intercepts it and returns HTTP 400 Bad Request; temp files are cleaned immediately.
36. **What is the maximum upload size?**
    - 10MB per file, enforced on both client and server.
37. **What is the approximate warm analysis time?**
    - ~17s for 1 panel, ~83s for 2 panels on standard Windows CPU. (Under 2s on GPU).
38. **What is the cold-start limitation?**
    - First run initializes deep learning weights in ~4-5s; all subsequent requests are warm.
39. **What is the future scope?**
    - Real-time mobile AR bounding box scanning, direct barcode GS1 database lookup, multilingual Indian language label support.
40. **What is each team member's role?**
    - *Computer Vision & Deep Learning*: PaddleOCR integration & pre-processing.
    - *Backend & Regulatory Logic*: FastAPI endpoints, Legal Metrology/FSSAI rule engines.
    - *Frontend & Evidence Viewer*: React UI, interactive SVG overlays, results dashboard.

---

## 8. Challenge Question: "Many Solutions Already Exist"

**Answer**:
> *"Existing tools either provide raw OCR dumps without legal awareness or generic image classification. MetrCheck AI is the first unified statutory compliance engine that bridges Deep Learning OCR with the actual Legal Metrology (Packaged Commodities) Rules 2011 and FSSAI 2020 Regulations. We provide human-verifiable visual evidence localization, proviso-aware legal applicability, and automated statutory show-cause notice generation."*

---

## 9. Challenge Question: "Why AI?"

**Answer**:
> *"We use AI where perception is needed—extracting text and bounding boxes from noisy, rotated, and curved physical packaging photos where rigid rules fail. But for legal compliance evaluation, we use deterministic, explainable rule logic rather than unpredictable generative AI. This guarantees zero hallucination, 100% repeatability, and complete statutory accountability."*

---

## 10. Team Presentation Roles Template

- **Presenter 1 (Problem & Live Demo)**: Leads problem statement, uploads images, and walks judges through the compliance dashboard and evidence viewer.
- **Presenter 2 (AI & Computer Vision)**: Explains PaddleOCR deep learning architecture, textline orientation classification, and bounding box localization.
- **Presenter 3 (Regulatory Architecture & Backend)**: Explains Legal Metrology Act, FSSAI regulations, rule applicability, SQLite persistence, and failure recovery.
