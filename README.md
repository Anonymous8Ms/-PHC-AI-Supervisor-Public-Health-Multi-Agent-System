# 🏥 PHC AI Supervisor — Public Health Multi-Agent System

**That is the power of PHC AI Supervisor.**

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    PHC AI Supervisor                     │
│                   (4-Agent System)                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐    ┌──────────────────┐              │
│  │ Voice / Form │    │ Photo + GPS      │              │
│  │ Ingestion    │    │ Data Ingestion   │              │
│  └──────┬───────┘    └────────┬─────────┘              │
│         │                     │                         │
│         └──────────┬──────────┘                         │
│                    ▼                                    │
│  ┌──────────────────────────────────────┐              │
│  │   INGESTION AGENT                     │              │
│  │   - Validates worker & household      │              │
│  │   - Summarizes symptoms via Gemini    │              │
│  │   - Stores visit as "pending"         │              │
│  └──────────────┬───────────────────────┘              │
│                 │                                       │
│                 ▼                                       │
│  ┌──────────────────────────────────────┐              │
│  │   VERIFICATION AGENT                  │              │
│  │   - GPS distance check (Haversine)    │              │
│  │   - Photo hash reuse detection        │              │
│  │   - Timing anomaly (Sunday/late)      │              │
│  │   - Gemini generates fraud reason     │              │
│  └──────────────┬───────────────────────┘              │
│                 │                                       │
│                 ▼                                       │
│  ┌──────────────────────────────────────┐              │
│  │   PREDICTION AGENT                    │              │
│  │   - Analyzes 7/14/30-day coverage     │              │
│  │   - Gemini flags underserved zones    │              │
│  │   - Creates outbreak/missed alerts    │              │
│  └──────────────┬───────────────────────┘              │
│                 │                                       │
│                 ▼                                       │
│  ┌──────────────────────────────────────┐              │
│  │   SUPERVISOR AGENT (Chat)             │              │
│  │   - Natural language queries          │              │
│  │   - Responds in English or Hindi      │              │
│  │   - Worker stats, alerts, zone risks   │              │
│  └──────────────┬───────────────────────┘              │
│                 │                                       │
│                 ▼                                       │
│  ┌──────────────────────────────────────┐              │
│  │   SUPERVISOR DASHBOARD                │              │
│  │   - KPI cards, alert feed, zone map   │              │
│  │   - Worker list with visit details    │              │
│  │   - AI chat panel with suggestions    │              │
│  └──────────────────────────────────────┘              │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone <your-repo-url>
cd health-agent
pip install -r requirements.txt
```

### 2. Add Your Gemini API Key

Create a `.env` file (or edit the existing one):

```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
FLASK_PORT=5000
FLASK_DEBUG=True
```

> Get your API key from [Google AI Studio](https://aistudio.google.com/app/apikey)

### 3. Run the Backend

```bash
python app.py
```

Flask starts at `http://127.0.0.1:5000`

### 4. Open the Frontend

```bash
open frontend/index.html
```

Or simply double-click `frontend/index.html`.

---

## 🧪 Demo Data (Pre-Loaded)

The system auto-generates realistic demo data on first run:

| Entity | Count | Details |
|--------|-------|---------|
| **PHCs** | 3 | PHC Kurud, PHC Jagdalpur, PHC Dhamtari (Chhattisgarh) |
| **Health Workers** | 12 | Indian names, Hindi/Odia languages |
| **Households** | 40 | Distributed across zones with risk levels |
| **Visits** | 80 | Mix of verified, pending, and **4 fake visits** |
| **Alerts** | 10 | Fake visits, missed areas, outbreak risks, worker burnout |

**4 fake visits are deliberately injected** with:
- GPS far from household (>20 km)
- Reused photo hashes
- Sunday or late-night timing

This ensures the Verification Agent has real fraud to detect on first run.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/dashboard` | KPI summary + recent alerts + zone summary |
| `GET` | `/api/alerts` | All alerts (filter: `?resolved=false`) |
| `POST` | `/api/alerts/:id/resolve` | Mark alert as resolved |
| `POST` | `/api/visit/submit` | IngestionAgent processes new visit |
| `POST` | `/api/visit/:id/verify` | VerificationAgent analyzes visit |
| `POST` | `/api/predict` | PredictionAgent runs zone risk analysis |
| `POST` | `/api/chat` | SupervisorAgent chat (`{query, language}`) |
| `GET` | `/api/workers` | All workers with visit counts |
| `GET` | `/api/workers/:id` | Worker detail + last 10 visits |
| `GET` | `/api/zones` | Zone risk levels + visit stats |
| `POST` | `/api/demo/reset` | Reset DB + regenerate demo data |

---

## 🤖 The 4 AI Agents

### 1. 📝 Ingestion Agent
Receives health worker visit reports, validates references, uses **Gemini** to summarize symptoms, and stores the visit as `pending`.

### 2. 🔍 Verification Agent
Detects fake visits using:
- **Haversine distance** — is the GPS within 500m of the household?
- **Photo reuse** — same photo hash in another visit within 30 days?
- **Timing anomaly** — Sunday visit or before 6 AM / after 9 PM?

Uses **Gemini** to generate a natural-language fraud explanation. Falls back to rule-based logic if Gemini is unavailable.

### 3. 📊 Prediction Agent
Analyzes visit coverage per zone (7d, 14d, 30d). Uses **Gemini** to identify underserved zones and predict outbreak risk. Creates alerts automatically. Falls back to statistical thresholds if Gemini fails.

### 4. 💬 Supervisor Agent
Natural-language chat for PHC supervisors. Supports:
- English and **Hindi** queries
- Worker lookup by name (e.g., *"Lata Bai ki report kaisi hai?"*)
- Zone risk summaries
- Alert prioritization
- Fallback responses when Gemini is unavailable

---

## 🎨 Frontend Features

- **Live Dashboard** — KPI cards auto-refresh every 30 seconds
- **Alert Feed** — Severity-colored cards with Resolve buttons
- **Zone Map Panel** — Risk filter + search, color-coded zone cards
- **Worker List** — Click to expand recent visits with GPS & status
- **AI Chat Panel** — Toggle chat, language selector (English/Hindi), suggested question chips, real-time typing indicator

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.10+, Flask, SQLAlchemy (SQLite) |
| **AI Model** | Google Gemini 1.5 Flash via `google-generativeai` |
| **Frontend** | Vanilla HTML, CSS, JavaScript (no frameworks) |
| **Database** | SQLite (zero-config, file-based) |
| **CORS** | `flask-cors` for cross-origin frontend access |
| **Env Config** | `python-dotenv` for API key management |

---

## 🌟 Why This Solution?

### The Real Problem
ASHA and ANM visits in rural India are logged on paper. Supervisors cannot verify household checks, fake reporting slips through, and PHCs have zero live insight into underserved zones.

### Our Solution
A **multi-agent AI system** that:
1. **Ingests** every visit with AI-generated summaries
2. **Verifies** fraud with GPS, photo, and timing checks
3. **Predicts** which zones are at risk before they become crisis zones
4. **Chats** with supervisors in their own language

### Impact
- **Fake visits** caught in real-time, not months later during audits
- **Underserved zones** identified before outbreaks occur
- **Supervisors** get answers in seconds, not days of manual report review

---

## 🧪 Try These Chat Queries

| Query | What Happens |
|-------|-------------|
| `"What alerts should I review first?"` | Supervisor Agent lists top-priority alerts |
| `"Which zones are critical today?"` | Critical zones with risk reasoning |
| `"Lata Bai ki report kaisi hai?"` | Hindi response with worker stats |
| `"Show me workers with no visits today"` | Inactive workers flagged |
| `"Which worker has flagged visits?"` | Fraud detection summary |
| `"Summarize active fake visit alerts"` | All fake visits in one response |

---

## 🔄 Fallback Design

Every agent has a **working fallback** if the Gemini API is unavailable:
- **Ingestion:** Default summary based on symptoms
- **Verification:** Rule-based fraud detection with structured reasons
- **Prediction:** Statistical thresholds (unvisited households + low visit counts)
- **Supervisor:** Keyword-matched responses in English and Hindi

The system **never breaks** — it gracefully degrades.

---

## 📂 Project Structure

```
health-agent/
├── .env                          # Gemini API key (not committed)
├── requirements.txt              # Python dependencies
├── app.py                        # Flask API entry point
├── database.py                   # SQLAlchemy engine & session
├── models.py                     # Database schema (6 tables)
├── config.py                     # Gemini client config
├── demo_data.py                  # Realistic demo data generator
├── agents/
│   ├── ingestion_agent.py          # Agent 1: Visit intake & summarization
│   ├── verification_agent.py     # Agent 2: Fraud detection (GPS/photo/timing)
│   ├── prediction_agent.py       # Agent 3: Underserved zone prediction
│   └── supervisor_agent.py       # Agent 4: Natural language chat
└── frontend/
    ├── index.html                  # Dashboard layout
    ├── style.css                 # Professional UI (731 lines)
    └── app.js                    # Interactivity, API calls, chat
```

---


*"From paper logs to AI-powered public health — one agent at a time."*
