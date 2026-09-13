# MetrCheck AI

**AI-Powered Legal Metrology Compliance Assistant**  
*Smart India Hackathon Problem Statement: SIH26034*

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-blue?logo=react&logoColor=white)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0%2B-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4%2B-38B2AC?logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Overview

**MetrCheck AI** is an intelligent compliance auditing assistant designed to inspect packaged product labels for conformity with the **Legal Metrology (Packaged Commodities) Rules, 2011**. 

By pairing Optical Character Recognition (OCR) with deterministic rule evaluation and natural language extraction, MetrCheck AI detects mandatory packaging declarations (such as MRP, Net Quantity, Manufacturer details, Dates, and Customer Care contacts), identifies omissions or formatting defects, and generates an explainable compliance score and audit report.

---

## Problem Statement

**SIH26034 — Legal Metrology Compliance AI**

Under the Indian Legal Metrology Act and the Packaged Commodities Rules (2011), all pre-packaged commodities sold across offline retail and e-commerce platforms must carry explicit mandatory declarations to safeguard consumer rights. 

Manual verification of packaging labels is:
- **Time-Intensive & Expensive**: Inspecting thousands of SKUs requires immense human labor.
- **Error-Prone**: Minor omissions, font size discrepancies, and improper metric units frequently slip past manual review.
- **Inconsistent**: Different inspectors may apply varying levels of scrutiny.

There is a critical need for an automated, objective, AI-driven inspection pipeline capable of ingesting packaging images, extracting declaration text with spatial coordinates, evaluating rules, and flagging non-compliant products instantly.

---

## Solution

MetrCheck AI implements an end-to-end multi-stage pipeline:

$$\text{Product Image} \longrightarrow \text{OCR Engine} \longrightarrow \text{Information Extraction} \longrightarrow \text{Compliance Check} \longrightarrow \text{Score} \longrightarrow \text{Report}$$

1. **Image Ingestion**: Accepts label images via drag-and-drop or sample selection.
2. **OCR Engine**: Detects raw text fragments and extracts 2D bounding boxes using PaddleOCR (PP-OCRv4 deep learning engine).
3. **Information Extraction**: Employs pattern recognition (regex) and structured parsing to extract key packaging attributes:
   - Maximum Retail Price (MRP inclusive of all taxes)
   - Net Quantity (metric weight, volume, or count)
   - Date of Manufacture / Packing / Import
   - Expiry Date / Best Before period
   - Manufacturer / Packer / Importer Name & Physical Address
   - Consumer Care Details (Phone & Email)
   - Country of Origin
4. **Compliance Check**: Validates extracted data against codified Legal Metrology rules and mandatory declaration requirements.
5. **Scoring & Explainability**: Generates a standardized compliance score (0–100) alongside fine-grained classification:
   - **Compliant**: Mandatory declarations present and valid.
   - **Warning**: Declarations present with non-critical formatting ambiguities or missing optional fields.
   - **Violation**: Missing mandatory declarations or non-standard representations.
6. **Report Generation**: Presents visual bounding-box highlights, field-by-field verdicts, and downloadable inspection audit reports.

---

## Architecture

```
User → Frontend (React+Vite+TS+Tailwind)
         ↕ REST API
       Backend (FastAPI+Python)
         ├── OCR Engine (PaddleOCR PP-OCRv4)
         ├── Extraction Engine (Regex/LLM)
         ├── Compliance Engine (Rules)
         └── SQLite Database
```

- **Frontend**: A modern, reactive single-page application built with React, Vite, TypeScript, and Tailwind CSS. Features image upload, bounding-box visualization, interactive score gauges, and analysis logs.
- **REST API**: Asynchronous FastAPI backend providing high-throughput endpoints for image upload, synchronous/asynchronous analysis, and historical retrieval.
- **OCR Engine**: PaddleOCR (PP-OCRv4) deep learning text detection (DBNet) & recognition (SVTR) with bounding-box coordinate tracking and angle classification.
- **Extraction Engine**: Hybrid extraction system using rule-based regular expressions with optional LLM augmentation for ambiguous or complex label layouts.
- **Compliance Engine**: Declarative rule validation matrix implementing provisions of the Legal Metrology (Packaged Commodities) Rules.
- **SQLite Database**: Lightweight, zero-configuration local relational storage for inspection history, audit metadata, and score tracking.

---

## Technology Stack

| Layer / Component | Technology | Description |
| :--- | :--- | :--- |
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS | Single-page application, responsive layout, type safety |
| **Backend** | Python 3.10+, FastAPI, Uvicorn, Pydantic | High-performance asynchronous REST API framework |
| **OCR** | PaddleOCR (`paddleocr`, `paddlepaddle`), Pillow | Deep learning text detection (DBNet), recognition (SVTR), angle classification, and coordinate mapping |
| **Database** | SQLite, aiosqlite | Lightweight persistence for audits and analysis history |
| **Charts** | Recharts | Visual compliance gauge and status distribution |
| **Icons** | Lucide React | Lightweight, consistent vector icons |

---

## Features

- **Drag-and-Drop Image Upload**: Clean interface supporting PNG, JPG, JPEG, and WebP product label uploads up to 10MB.
- **OCR Text Extraction with Bounding Boxes**: Visual overlay mapping recognized text coordinates directly over the packaging label.
- **Structured Information Extraction**: Automatic identification of MRP, Net Quantity, Dates, Manufacturer Address, Country of Origin, and Customer Care.
- **Configurable Compliance Rules Engine**: Modular rules covering mandatory declarations, metric unit standards, and mandatory contact details.
- **Explainable Compliance Scoring**: Transparent 0–100 score breakdown with color-coded tags (Passed, Warning, Violated).
- **Interactive Results Dashboard**: Clear side-by-side inspection view of the product label, extracted fields, and rule verification checklist.
- **Analysis History with SQLite Storage**: Persistent tracking of previous inspections for regulatory audit trails.
- **Downloadable Compliance Reports**: Export detailed compliance findings as structured reports for documentation and review.
- **Demo Mode with 3 Test Cases**: Built-in compliant, warning, and violation sample test cases to run complete simulations.
- **Modular Architecture**: Extensible codebase designed for plug-and-play OCR models and VLM backends.

---

## Quick Start

### Prerequisites
- **Python 3.10+ / 3.11**
- **Node.js 18+**

---

### Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy ..\.env.example .env
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

---

### Access

- **Frontend Application**: [http://localhost:5173](http://localhost:5173)
- **Interactive Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc API Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check Endpoint**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

## Demo Mode

For rapid evaluation and demonstration during hackathons and reviews, MetrCheck AI includes a zero-dependency **Demo Mode**. You can trigger pre-analyzed test cases directly from the dashboard:

| Case | Scenario | Expected Score | Details |
| :--- | :--- | :---: | :--- |
| **Case 1: Compliant** | Fully compliant packaged food label | **100 / 100** | All mandatory declarations present: MRP (incl. of all taxes), standard metric net weight (`500 g`), manufacturing date, manufacturer details with PIN code, customer helpline & email, Country of Origin (India). |
| **Case 2: Warning** | Minor formatting defect | **75 / 100** | Declarations are present, but uses non-standard metric abbreviation (`gms` instead of `g`) or missing dedicated consumer email while retaining telephone contact. |
| **Case 3: Violation** | Non-compliant packaging label | **35 / 100** | Critical omissions: Missing MRP declaration, missing consumer care contact info, and ambiguous manufacturer address without state or PIN code. |

To use Demo Mode:
1. Open the web interface at [http://localhost:5173](http://localhost:5173).
2. Click on the **Demo Cases** selector in the upload section.
3. Select **Compliant**, **Warning**, or **Violation** to review instant scoring and bounding-box highlights.

---

## API Endpoints

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Check API status, database connectivity, and OCR engine status |
| `POST` | `/api/analyze` | Upload a product label image for OCR processing and compliance analysis |
| `GET` | `/api/demo/{case_id}` | Retrieve mock analysis data for demo cases (`compliant`, `warning`, `violation`) |
| `GET` | `/api/history` | List all historical compliance analysis records |
| `GET` | `/api/history/{id}` | Retrieve full details of a specific inspection record |
| `GET` | `/api/report/{id}/download` | Download structured inspection audit report |
| `GET` | `/api/rules` | Fetch active Legal Metrology rules and validation parameters |

---

## Project Structure

```
Legal Metrology Compliance AI Prototype/
├── .env.example                     # Environment configuration template
├── .gitignore                       # Git ignore rules for Python, Node, and temporary files
├── README.md                        # Project documentation and setup guide
├── test_data/                       # Sample test packaging images for evaluations
│   ├── compliant/                   # Fully compliant packaging labels
│   │   └── .gitkeep
│   ├── warning/                     # Labels with minor or formatting warnings
│   │   └── .gitkeep
│   └── violation/                   # Labels with legal violations and omissions
│       └── .gitkeep
├── backend/                         # FastAPI Python backend
│   ├── api/                         # API route endpoints
│   │   ├── __init__.py
│   │   ├── analyze.py               # Label analysis & upload endpoint
│   │   ├── compliance_routes.py     # Compliance rules endpoints
│   │   ├── demo.py                  # Demo test case routes
│   │   ├── extract.py               # Entity extraction routes
│   │   ├── health.py                # Health & readiness checks
│   │   ├── history.py               # Inspection audit history
│   │   ├── ocr.py                   # Raw OCR inspection endpoint
│   │   └── report.py                # Downloadable report routes
│   ├── compliance/                  # Compliance engine
│   │   ├── __init__.py
│   │   ├── engine.py                # Rule evaluation logic
│   │   ├── rules.py                 # Legal Metrology rule definitions
│   │   └── scorer.py                # Compliance scoring algorithms
│   ├── database/                    # SQLite database layer
│   │   ├── __init__.py
│   │   └── db.py                    # Database connection & schema setup
│   ├── extraction/                  # Information extraction engine
│   │   ├── __init__.py
│   │   ├── extractor.py             # Regex & pattern-based extractor
│   │   ├── llm_extractor.py         # Optional LLM-assisted extractor
│   │   └── patterns.py              # Regex patterns for declarations
│   ├── models/                      # Pydantic models & data schemas
│   │   ├── __init__.py
│   │   └── schemas.py               # Request, response, and audit schemas
│   ├── ocr/                         # OCR engine abstraction
│   │   ├── __init__.py
│   │   ├── base.py                  # Abstract base OCR engine class
│   │   ├── factory.py               # OCR engine factory (PaddleOCR)
│   │   └── paddle_engine.py         # PaddleOCR PP-OCRv4 implementation
│   ├── services/                    # Business service layer
│   │   ├── __init__.py
│   │   ├── analysis_service.py      # Orchestrates OCR, extraction, and rules
│   │   ├── image_service.py         # Image preprocessing & validation
│   │   └── report_service.py        # Report generation utilities
│   ├── utils/                       # Shared helpers & validation
│   │   ├── __init__.py
│   │   └── validators.py            # Unit and format validators
│   ├── config.py                    # Application configuration & env settings
│   ├── main.py                      # FastAPI application entry point
│   └── requirements.txt             # Python backend dependencies
└── frontend/                        # React + TypeScript + Vite frontend
    ├── public/                      # Static assets
    ├── src/
    │   ├── assets/                  # Images and static media
    │   ├── components/              # UI components
    │   ├── services/
    │   │   └── api.ts               # Axios / Fetch client for backend API
    │   ├── types/
    │   │   └── index.ts             # TypeScript interface definitions
    │   ├── App.tsx                  # Main application component
    │   ├── index.css                # Tailwind CSS imports
    │   └── main.tsx                 # React DOM root entry point
    ├── index.html                   # HTML template
    ├── package.json                 # Node dependencies and scripts
    ├── tailwind.config.js           # Tailwind CSS configuration
    ├── tsconfig.json                # TypeScript compiler configuration
    └── vite.config.ts               # Vite build configuration
```

---

## Environment Variables

| Variable | Description | Default Value | Required |
| :--- | :--- | :--- | :---: |
| `OCR_ENGINE` | Optical Character Recognition backend (`paddleocr`) | `paddleocr` | No |
| `LLM_API_KEY` | Optional API key for LLM-assisted label parsing | *(empty)* | No |
| `UPLOAD_DIR` | Directory where uploaded product images are saved | `./uploads` | No |
| `DATABASE_PATH` | Path to SQLite database file | `./metrc_check.db` | No |
| `MAX_FILE_SIZE_MB` | Maximum allowed image file upload size in megabytes | `10` | No |
| `CORS_ORIGINS` | Comma-separated allowed HTTP origins for frontend CORS | `http://localhost:5173,http://localhost:3000` | No |
| `HOST` | Backend server network interface bind host | `0.0.0.0` | No |
| `PORT` | Backend server port number | `8000` | No |

---

## Future Improvements

- **Advanced Vision AI / VLM Integration**: Leverage multimodal models (e.g., Gemini Flash / GPT-4o) for zero-shot understanding of distorted, curved, or complex artistic packaging.
- **PaddleOCR & Cloud OCR**: Provide dual-engine support with PaddleOCR and cloud providers for higher accuracy under low-light and noisy conditions.
- **Hindi & Multilingual OCR**: Support label verification across all 22 official Indian languages.
- **Official Legal Metrology Rule Database**: Live integration with official gazette amendments and sector-specific commodity rules.
- **Inspector Dashboard**: Dedicated portal for regulatory officers with batch processing, filtering by violation category, and automated notice generation.
- **Bulk Image Analysis**: Automated ingestion pipeline for e-commerce catalog audits and warehouse batch scanning.
- **Mobile Application**: On-device scanning app with offline edge OCR for field inspectors.
- **QR / Barcode Verification**: Dual verification checking if embedded QR codes or EAN barcodes match on-pack declarations.
- **Cloud Deployment**: Containerized deployment with Docker and Kubernetes for high scalability.
- **Advanced Explainable AI**: Visual heatmaps and confidence calibration for every compliance assertion.

---

## Disclaimer

> **Important Notice**  
> This is a prototype developed for Smart India Hackathon 2026 (SIH26034). Compliance results are indicative and must be verified against current official Legal Metrology requirements. This tool does not provide legally binding determinations.

---

## License

This project is licensed under the [MIT License](LICENSE).
