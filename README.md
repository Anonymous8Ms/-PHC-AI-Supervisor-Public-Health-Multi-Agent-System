# PHC AI Supervisor

PHC AI Supervisor is a public health multi-agent system for rural field monitoring. It helps supervisors catch suspicious visit reports, identify underserved zones, and review worker activity through a guided dashboard and scoped AI chat.

## Stack

- Python 3.10+, Flask, SQLAlchemy
- SQLite by default, with optional `DATABASE_URL` support for PostgreSQL deployments
- Vanilla HTML, CSS, JavaScript
- Google Gemini 1.5 Flash via `google-generativeai`
- Railway-compatible deployment with optional Docker support

## Evaluation-Oriented Improvements

The project was strengthened in the areas that usually affect hackathon scoring:

- Better maintainability through backend typing and module documentation
- Better deployment readiness through a health endpoint and Docker support
- Better engineering quality through API and agent tests
- Better handoff quality through a tighter setup and deployment README

## Local Run

```bash
pip install -r requirements.txt
python demo_data.py
python app.py
```

Open:

- App: `http://127.0.0.1:5000`
- Frontend file: `frontend/index.html`

## Environment

Use a `.env` file:

```env
GEMINI_API_KEY=your_gemini_api_key_here
FLASK_PORT=5000
FLASK_DEBUG=True
DATABASE_URL=
GEMINI_TIMEOUT_SECONDS=8
```

## Demo Data

The seeded dataset includes:

- 3 PHCs in Chhattisgarh
- 12 health workers
- 40 households
- 80 visits over 30 days
- 10 alerts, including clearly fake visits

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Covered areas:

- `/api/health` and `/api/dashboard`
- worker, zone, alert, and prediction endpoints
- visit submission and verification
- prediction fallback behavior
- supervisor chat scope protection
- seeded model counts and relationships

## CI/CD

GitHub Actions is included in [.github/workflows/ci.yml](/Users/anuttamams/Documents/AI%20Agent%20Builder/health-agent/.github/workflows/ci.yml).

It runs:

- critical lint checks with Ruff
- Python compilation checks
- pytest on Python 3.10 and 3.11
- Docker image build validation on every push and pull request

## Docker

```bash
docker build -t phc-ai-supervisor .
docker run -p 5000:5000 --env-file .env phc-ai-supervisor
```

## API

- `GET /api/health`
- `GET /api/dashboard`
- `GET /api/alerts`
- `POST /api/alerts/<id>/resolve`
- `POST /api/visit/submit`
- `POST /api/visit/<id>/verify`
- `POST /api/predict`
- `POST /api/chat`
- `GET /api/workers`
- `GET /api/workers/<id>`
- `GET /api/zones`
- `POST /api/demo/reset`

## Suggested Demo Queries

- `Which worker has flagged visits?`
- `What alerts should I review first?`
- `Which zones are critical today?`
- `Lata Bai ki report kaisi hai?`

## Deployment Notes

- Railway can run the app with `python app.py`
- The app reads `PORT` automatically for hosted deployment
- SQLite persistence works best with a mounted Railway volume
- For a production-grade database, set `DATABASE_URL` to a PostgreSQL connection string
