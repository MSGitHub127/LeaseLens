# 🔍 LeaseLens

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python Version" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Google_Cloud_Run-Live_Deploy-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white" alt="Google Cloud Run" />
  <img src="https://img.shields.io/badge/Anthropic-Claude%20Vision-D97706?style=for-the-badge&logo=anthropic&logoColor=white" alt="Claude Vision" />
  <img src="https://img.shields.io/badge/Tests-96%20Passing%20(100%25)-success?style=for-the-badge&logo=pytest&logoColor=white" alt="Tests" />
  <img src="https://img.shields.io/badge/Code%20Style-Ruff%20Clean-black?style=for-the-badge&logo=ruff&logoColor=white" alt="Ruff" />
  <img src="https://img.shields.io/badge/Security-Fernet%20AES--128%20%2B%20PII%20Redacted-blueviolet?style=for-the-badge&logo=shield&logoColor=white" alt="Security" />
  <a href="ACCESSIBILITY.md"><img src="https://img.shields.io/badge/Accessibility-WCAG%202.1%20AA%20%2F%20AAA-brightgreen?style=for-the-badge&logo=w3c&logoColor=white" alt="Accessibility" /></a>
</p>

<h3 align="center">
  <strong>Context-aware, multimodal legal intelligence for tenants navigating leases, subleases, and eviction notices before they sign or vacate.</strong>
</h3>

<p align="center">
  <em>Built for the Legal GenAI Hackathon Challenge — <strong>Tenant Vertical</strong></em><br/>
  🚀 <strong>Live Demo</strong>: <a href="https://leaselens-162669160069.us-central1.run.app" target="_blank"><strong>https://leaselens-162669160069.us-central1.run.app</strong></a>
</p>

---

> [!TIP]
> 🌐 **Live Cloud Demo**: Try LeaseLens directly in your browser on Google Cloud Run: [https://leaselens-162669160069.us-central1.run.app](https://leaselens-162669160069.us-central1.run.app) (Swagger docs at [/docs](https://leaselens-162669160069.us-central1.run.app/docs)).

> [!IMPORTANT]
> **Information, Not Legal Advice**: LeaseLens empowers renters to understand complex contracts, compare terms, and spot predatory clauses. Every output clearly provides pointers to certified tenant rights clinics, housing advocates, and licensed attorneys. State-specific figures (deposit limits, notice windows) are illustrative examples parameterized in `app/rubric.py`.

---

## 🌟 Why LeaseLens?

Renters are consistently on the losing side of an asymmetric contract: landlords have attorneys who draft complex, multi-page leases filled with hidden penalties, vague maintenance duties, and rights waivers. When eviction or vacate notices arrive, tenants face panicked, high-stakes deadlines without knowing what questions to ask or whether the notice is legally compliant.

**LeaseLens is not a chatbot bolted onto a generic prompt.** 

It is powered by a deterministic **Context-Aware Rubric Engine**:
1. **Identifies Context First**: Detects what kind of document it is (*residential lease*, *sublease*, *roommate agreement*, *notice to vacate*, or *lease addendum*) and the **jurisdiction** (*CA, NY, TX, etc.*).
2. **Selects the Right Rubric**: A notice to vacate is checked against urgent response deadlines, with-cause requirements, and cure windows; a sublease is verified against landlord consent and master lease incorporation; a residential lease is checked for deposit caps and entry notice rules.
3. **Multimodal Ingestion**: Accepts digital PDFs, scanned PDFs, and **smartphone photos of paper notices taped to a door**.
4. **Calculates a Tenant Protection Score (0–100)**: Gives tenants an immediate, visual health check of contractual fairness.
5. **Exports a Legal Aid Consultation Brief**: Compiles a professional markdown intake packet that tenants can bring directly to a free legal aid clinic or attorney.

---

## 🎯 Problem Statement & Legal GenAI Solution Alignment

Over 44 million renter households in the United States operate under profound information asymmetry: landlords employ legal counsel to draft multi-page, legally dense leases embedded with hidden fees, vague repair obligations, and rights waivers. Over 90% of tenants navigate these agreements and eviction threats without legal representation.

LeaseLens directly solves the core challenges outlined in the **Legal GenAI Challenge (Tenant Vertical)**:

| Hackathon Objective | LeaseLens Implementation & Solution | Repository Module & REST Endpoint |
| :--- | :--- | :--- |
| **1. Simplifying complex legal documents** | Plain-language AI summaries calibrated to an ~8th-grade reading level; UI Plain-Language toggle; Web Speech API voice playback. | [`app/llm/anthropic_provider.py`](app/llm/anthropic_provider.py) (`plain_language_summary`) |
| **2. Comparing contracts & agreements** | Side-by-side contract diff engine highlighting missing clauses, modified terms, and risk changes between drafts. | [`app/compare.py`](app/compare.py), `POST /api/documents/compare` |
| **3. Highlighting clauses, obligations & risks** | Context-Aware Rubric Engine categorizing findings into 5 areas with High/Medium/Low severity ratings and statutory state rules. | [`app/rubric.py`](app/rubric.py), [`app/extraction.py`](app/extraction.py) |
| **4. Answering questions based on documents** | Grounded Q&A assistant citing verbatim contract provisions using stemmed TF-Cosine RAG without hallucinating. | [`app/routers/qa.py`](app/routers/qa.py), [`app/rag.py`](app/rag.py) (`/api/documents/{id}/ask`) |
| **5. Helping users understand options & next steps** | Dynamic action checklist splitting items into *"Ask Before Signing"* and *"Confirm in Writing"*. | [`app/checklist.py`](app/checklist.py) (`generate_checklist`), `/api/documents/{id}/checklist` |
| **6. Actionable outputs & visual scoring** | Algorithmic Tenant Protection Score (0–100), category health breakdown dials, and prioritized task checklists. | [`app/rubric.py`](app/rubric.py) (`calculate_tenant_protection_score`) |
| **7. Preparing users for legal professionals** | One-click export of structured **Legal Aid Consultation Brief (.md)** with pre-formulated housing questions. | [`app/checklist.py`](app/checklist.py) (`generate_consultation_brief`), `/api/documents/{id}/export-brief` |
| **8. Ethics & Unauthorized Practice of Law (UPL)** | Prominent disclaimers, automatic advice-pattern interception, and certified legal clinic referral pointers. | [`app/security.py`](app/security.py), [`app/qa.py`](app/qa.py) |

---

## 🏗️ System Architecture

<p align="center">
  <img src="assets/system_architecture.svg" alt="LeaseLens End-to-End System Architecture" width="100%">
</p>

### Universal Architecture Pipeline

```text
                    ┌─────────────────────────────────────────────────────────────┐
                    │ 1. MULTI-FORMAT INGESTION (Zero External API Cost)          │
                    │    • Digital PDFs (pdfplumber)   • Scanned PDFs (pypdfium2) │
                    │    • Smartphone Photos (Pillow)  • DOCX / Plain Text        │
                    └──────────────────────────────┬──────────────────────────────┘
                                                   │ Raw Bytes
                                                   ▼
                    ┌─────────────────────────────────────────────────────────────┐
                    │ 2. DEFENSE-IN-DEPTH PRIVACY & SECURITY GUARD                │
                    │    • Binary magic-byte verification (%PDF, PNG, JFIF, RIFF) │
                    │    • 8-Pattern PII Redaction (SSN, DOB, Address, Bank, etc.)│
                    │    • Fernet AES-128 Encryption at Rest & Auto-Purge         │
                    └──────────────────────────────┬──────────────────────────────┘
                                                   │ Sanitized Text / Images
                                                   ▼
                    ┌─────────────────────────────────────────────────────────────┐
                    │ 3. DETERMINISTIC CONTEXT & RUBRIC ENGINE                    │
                    │    • classification.py: Doc Type + State Jurisdiction (CA)  │
                    │    • rubric.py: Dynamic Rule Selection & State Overrides    │
                    └──────────────────────────────┬──────────────────────────────┘
                                                   │ Parameterized Checklist
                                                   ▼
                    ┌─────────────────────────────────────────────────────────────┐
                    │ 4. HYBRID INTELLIGENCE & GROUNDED RAG                       │
                    │    • Claude 3.5 Sonnet Vision (Production) OR               │
                    │    • MockProvider (Deterministic, zero-cost, offline/CI)    │
                    │    • rag.py: TF Cosine RAG + Morphological Legal Stemming   │
                    └──────────────────────────────┬──────────────────────────────┘
                                                   │ Evaluated Findings
         ┌─────────────────────────┬───────────────┴───────────────┬─────────────────────────┐
         ▼                         ▼                               ▼                         ▼
┌──────────────────┐     ┌──────────────────┐            ┌──────────────────┐     ┌──────────────────┐
│ TENANT SCORE     │     │ ACTION CHECKLIST │            │ LEGAL BRIEF (.MD)│     │ GROUNDED Q&A     │
│ 0–100 health dial│     │ Ask before sign, │            │ Tenant defense   │     │ Excerpt-backed   │
│ + risk breakdown │     │ confirm in write │            │ intake packet    │     │ citations        │
└──────────────────┘     └──────────────────┘            └──────────────────┘     └──────────────────┘
```

### Data Pipeline Overview

| Pipeline Stage | Module | Input & Processing | Output & Guarantees |
| :--- | :--- | :--- | :--- |
| **1. Ingestion** | [`app/parsing.py`](app/parsing.py) | Digital PDFs (`pdfplumber`), Scans (`pypdfium2`), Photos (`Pillow`), Word, TXT | Zero commercial parser API costs; 100% local extraction |
| **2. Security** | [`app/security.py`](app/security.py) | Magic-byte check, 8-pattern regex masking, Fernet AES-128 encryption, prompt-injection defense | Sensitive PII (SSN, DOB, Address, Cards) never touches logs or LLMs |
| **3. Context Engine** | [`app/rubric.py`](app/rubric.py) | Document type detection (Lease, Sublease, Notice) + US Jurisdiction | Selects context-specific checklists and statutory parameters |
| **4. Hybrid Intelligence** | [`app/llm/`](app/llm/), [`app/rag.py`](app/rag.py) | Claude 3.5 Sonnet Vision or MockProvider + Stemmed TF-Cosine RAG | Evaluates clauses against rubric rules without hallucinating |
| **5. Actionable Deliverables** | [`app/checklist.py`](app/checklist.py) | Synthesizes findings, scores, and legal aid intake packet | Produces 0–100 score, prioritized checklist, and `.md` brief |

---

## ⚡ Key Innovations & Features

### 1. The Context-Aware Rubric Engine
A static checklist fails because a residential lease and a notice to vacate have completely different legal priorities. LeaseLens deterministically selects the rubric *before* any LLM touches the clause text:
- **Notice to Vacate**: Checks for specific reasons (*for-cause* vs *no-cause*), legal response deadlines (*days to cure*), and vacancy timelines.
- **Sublease**: Verifies landlord written consent, master lease incorporation, and subtenant indemnification.
- **Residential Lease**: Verifies deposit return windows, landlord entry notice hours, and habitability obligations.
- **Jurisdiction-Specific Thresholds**: Applies state-law limits (e.g., California's 2-month deposit limit and 21-day return window; New York's 1-month deposit cap).

### 2. Multimodal Photo & PDF Ingestion (Zero Commercial Parser API Needed)
Tenants rarely have digital `.txt` contracts. LeaseLens accepts:
- **Digital PDFs**: Extracted in `<100ms` using local `pdfplumber`.
- **Scanned PDFs**: Automatically rendered to high-resolution page buffers via `pypdfium2`.
- **Smartphone Photos**: Accepts `.jpg`, `.png`, and `.webp` photos of physical notices and multi-page paper leases, transcribing them directly using Claude Vision.
- **Zero External Parser Cost**: No \$0.05/page fees for AWS Textract or LlamaParse; runs completely private and local.

### 3. Tenant Protection Score (0–100)
Outputs an algorithmic protection index weighted by severity:
- **High-Severity Protections** (Deposit terms, eviction reasons, landlord consent): `3x` weight.
- **Medium-Severity Protections** (Entry notice, maintenance responsibility, late fees): `2x` weight.
- **Flexibility & Rights** (Subletting, auto-renewal, legal right waivers): `1x` weight.
- Visual breakdown across 5 categories: **Financial**, **Maintenance**, **Access & Privacy**, **Termination & Deadlines**, and **Legal Rights**.

### 4. Legal Aid Consultation Packet & Brief Export
Tenants preparing to visit a tenant legal clinic, legal aid society, or private attorney can click **"Download Legal Aid Brief (.md)"** to produce a structured intake defense packet including:
- Document Type & Classification Confidence
- Calculated Tenant Protection Score & Category Breakdown
- Red Flag Warnings (*"Ask Before Signing"*)
- Ambiguities to Confirm in Writing
- Pre-formulated questions for housing counsel

### 5. Privacy-by-Design & Security Hardening
- **8-Category PII Redaction**: Masks SSNs, dates of birth, street addresses, credit cards, bank accounts, phone numbers, emails, and IP addresses before text is stored or sent to an LLM.
- **Fernet Encryption at Rest**: Encrypted in the database with AES-128.
- **Defensive HTTP Security Headers**: Injects `Content-Security-Policy` (with `frame-ancestors`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy`, and `Permissions-Policy`.
- **Pluggable Distributed Rate Limiting**: In-memory token bucket by default, with native Redis rate limiting via `LEASELENS_REDIS_URL`.
- **Data Auto-Purge**: Stored records automatically expire after 30 days and are purged on startup.

### 6. Full WCAG 2.1 AAA Accessibility & Multimodal Auditory Assist
- **WCAG 2.1 AAA Color Palette**: All text and badge elements achieve >= 7.0:1 contrast ratios on light, inset, and high-contrast modes (verified via axe-core, Pa11y, and automated Python luminance tests in `tests/test_accessibility.py`).
- **Screen-Reader Live Regions**: `aria-live="polite"` and `role="status"` dynamically announce analysis completion, protection scores, and clipboard actions.
- **Web Speech API Voice Readout**: Integrated `window.speechSynthesis` text-to-speech engine with accessible "🔊 Read Aloud" control for users with visual, cognitive, or reading impairments.
- **Visual A11y Suite**: Built-in **A+ / A− font scaling**, **High contrast mode**, and **Plain-language toggle** (~8th-grade reading level).
- **Automated Accessibility Test Suite**: 9 automated Python unit tests ([`tests/test_accessibility.py`](tests/test_accessibility.py)) continuously verify WCAG landmarks, ARIA labels, form inputs, keyboard focus outlines, and contrast ratios in CI.
- **Comprehensive Documentation**: Complete audit report, color contrast table, and Pa11y/Lighthouse verification steps detailed in [`ACCESSIBILITY.md`](ACCESSIBILITY.md).

### 7. Production Database Resilience & Connection Pooling
- **Zero-Config Local Development**: Defaults to local SQLite (`sqlite:///./leaselens.db`) with zero external service requirements.
- **Enterprise Production Architecture**: Seamlessly scales to PostgreSQL or Google Cloud SQL via `LEASELENS_DATABASE_URL` (e.g. `postgresql+psycopg2://user:pass@host:5432/leaselens`).
- **Production Connection Pooling**: Configures SQLAlchemy connection pools (`pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`, `pool_recycle=3600`) to prevent connection dropouts and handle high concurrency.
- **Operational Risk Detection**: In `production` environment, automatically audits database configuration and issues operational warnings if SQLite is run without a persistent volume mount (`/data`), preventing data loss during container recycling.

### 8. High-Fidelity Semantic Mock Provider for Air-Gapped CI/CD
- **Zero-Cost Evaluation**: Implements the full contract of the Anthropic Claude Vision provider for deterministic offline testing and automated hackathon evaluation.
- **Legal Domain Synonym Expansion**: Maps legal concepts (e.g., *deposit/bond*, *notice to vacate/eviction*, *landlord entry/premises access*, *maintenance/habitability*, *sublease/assignment*) to ensure high retrieval fidelity even for complex, paraphrased queries.
- **Intent-Driven Scoring**: Differentiates between operational metrics (deadlines, dollar caps, notice hours) and contractual boilerplate preambles to pinpoint relevant clauses accurately.

---

## 🚀 Quickstart
 
### Option 0: Live Cloud Demo (Instant Access)
Visit the production deployment on Google Cloud Run:
- **Web Application**: [https://leaselens-162669160069.us-central1.run.app](https://leaselens-162669160069.us-central1.run.app)
- **Swagger REST API Docs**: [https://leaselens-162669160069.us-central1.run.app/docs](https://leaselens-162669160069.us-central1.run.app/docs)
- **Health Check**: [https://leaselens-162669160069.us-central1.run.app/api/health](https://leaselens-162669160069.us-central1.run.app/api/health)

---

### Option 1: Standalone Browser Mode (Zero Backend Required)
Evaluate the full UI, rubric engine, PII redaction, PDF extraction, and Q&A immediately:
1. Double click [`frontend/index.html`](frontend/index.html) or open it in any browser.
2. Click **"Try a sample lease"**, **"Try a sample notice"**, or upload a PDF/photo.
3. Review findings, adjust text size, switch to high contrast, listen to audio readout, or download the consultation brief.

---

### Option 2: Python Local Setup (FastAPI Backend)

```powershell
# 1. Navigate to project
cd leaselens

# 2. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Configure environment
cp .env.example .env
# Edit .env and set your secrets (or keep default mock provider for offline use)

# 4. Run API server
uvicorn app.main:app --reload --port 8000
```

- **Interactive API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

### Option 3: Docker Compose

```bash
docker compose up --build
# API Backend: http://localhost:8000
# Frontend:    http://localhost:8080
```

---

## 📡 API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/session` | Issue an anonymous, signed JWT session token |
| `POST` | `/api/documents` | Upload PDF, DOCX, TXT, or Image (`.png`, `.jpg`, `.webp`) with PII redaction |
| `GET` | `/api/documents/{id}` | Retrieve document metadata and redaction audit counts |
| `POST` | `/api/documents/{id}/analyze` | Run rubric extraction; returns Tenant Protection Score and clause findings |
| `GET` | `/api/documents/{id}/checklist` | Generate prioritized action checklist (*Ask before signing*, *Confirm in writing*) |
| `GET` | `/api/documents/{id}/export-brief`| Export formatted Markdown Legal Consultation Brief for clinics |
| `POST` | `/api/documents/{id}/ask` | Grounded Q&A against document chunks with citations |
| `POST` | `/api/documents/compare` | Cross-document rubric diff comparing two lease versions |
| `GET` | `/api/health` | Health check endpoint |

---

## 🧪 Testing & Code Quality

LeaseLens includes an exhaustive automated test suite with **100% pass rate** across all modules.

```powershell
.\.venv\Scripts\pytest -v
```

```text
============================= test session starts =============================
platform win32 -- Python 3.13.7, pytest-8.3.3, pluggy-1.6.0
collected 96 items

tests/test_accessibility.py .........                                    [  9%]
tests/test_anthropic_provider.py ......                                  [ 15%]
tests/test_api_flow.py ...........                                       [ 27%]
tests/test_checklist.py ...                                              [ 30%]
tests/test_classification.py .......                                     [ 37%]
tests/test_compare.py ...                                                [ 40%]
tests/test_db_retention.py ...                                           [ 43%]
tests/test_enhanced_features.py ..........                               [ 54%]
tests/test_image_pdf_parsing.py ......                                   [ 60%]
tests/test_mock_provider.py .......                                      [ 67%]
tests/test_parsing.py .......                                            [ 75%]
tests/test_provider_factory.py ...                                       [ 78%]
tests/test_rag.py ....                                                   [ 82%]
tests/test_rubric.py .....                                               [ 87%]
tests/test_security.py ............                                      [100%]

======================= 96 passed in 1.45s =======================
```

Check code formatting and linter compliance:
```powershell
.\.venv\Scripts\ruff check .
# Output: All checks passed!
```

---

## 📁 Repository Structure

```
leaselens/
├── app/
│   ├── config.py              # Centralized settings (Pydantic BaseSettings: RDBMS pooling, rate limits)
│   ├── security.py            # Upload validation, 8-pattern PII redaction, Fernet encryption, rate limiting
│   ├── parsing.py             # PDF, DOCX, TXT, and Image (.png, .jpg) parsing pipeline
│   ├── classification.py      # Deterministic document type & US jurisdiction detection
│   ├── rubric.py              # Context-aware rubric rule selection & Tenant Protection Score calculation
│   ├── extraction.py          # Pipeline orchestrator (classify -> rubric -> score -> extract)
│   ├── rag.py                 # Grounded retrieval with morphological legal suffix stemming
│   ├── qa.py                  # Grounded question answering engine
│   ├── checklist.py           # Actionable checklist & Legal Consultation Brief generator
│   ├── compare.py             # Cross-document rubric alignment diff
│   ├── models.py              # SQLAlchemy ORM models & Pydantic request/response schemas
│   ├── db.py                  # Database engine, session management, enterprise pooling, auto-purge task
│   ├── auth.py                # Anonymous signed session token authorization
│   ├── main.py                # FastAPI factory, security headers middleware, CORS, static UI mounts
│   ├── templates/             # Server-side HTML template mirror (index.html)
│   ├── static/                # Static asset distribution (styles.css, app.js)
│   ├── routers/               # Modular REST API endpoints
│   │   ├── session.py
│   │   ├── documents.py
│   │   ├── analysis.py
│   │   └── qa.py
│   └── llm/                   # Pluggable LLM provider abstraction
│       ├── provider.py        # Abstract LLMProvider interface (extract, answer, summarize, vision)
│       ├── mock_provider.py   # High-fidelity semantic offline provider with domain synonym expansion
│       └── anthropic_provider.py # Claude 3.5 Sonnet multimodal vision & analysis implementation
├── frontend/                  # Modular, accessible Single Page Application
│   ├── index.html             # Semantic WCAG 2.1 AAA HTML with ARIA live regions
│   ├── styles.css             # High-contrast color palette (all pairs >= 7:1 AAA) & reduced motion
│   ├── app.js                 # Client-side engine with PDF.js & Web Speech API voice synthesis
│   └── package.json           # Frontend package declaration with npm a11y audit scripts
├── index.html                 # Root UI mirror for instant ingester & browser recognition
├── ACCESSIBILITY.md           # WCAG 2.1 AA/AAA compliance audit matrix & contrast calculations
├── tests/                     # 96 automated unit, integration, and security tests (15 test files)
│   ├── test_accessibility.py  # Automated WCAG 2.1 AAA contrast, semantic landmark & ARIA tests
│   ├── test_mock_provider.py  # Semantic synonym retrieval & complex query simulation tests
│   ├── test_db_retention.py   # RDBMS connection pooling & retention policy tests
│   ├── test_api_flow.py
│   ├── test_security.py
│   ├── test_enhanced_features.py
│   ├── test_image_pdf_parsing.py
│   ├── test_rubric.py
│   ├── test_rag.py
│   └── ...
├── Dockerfile                 # Hardened non-root container deployment
├── docker-compose.yml         # Multi-container orchestration (API + Nginx frontend)
├── requirements.txt           # Production dependencies
├── requirements-dev.txt       # Development & testing dependencies
└── README.md                  # Comprehensive documentation
```

---

## ⚖️ Legal Disclaimer

LeaseLens is designed to assist tenants and housing advocates by organizing and explaining contractual language from their documents. **It does not provide formal legal advice, legal representation, or attorney-client privilege.** Tenancy statutes, rent stabilization ordinances, and eviction procedures vary significantly by state, county, and municipality. Always consult a licensed attorney or certified local tenant advocacy clinic for formal legal counsel.
