# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Transaction Validator API**: A Flask-based financial transaction validation service. It validates transaction structure, checks for fraud signals (high-value txns, unusual patterns, round amounts), and returns a risk score (0-100+). Stateless, fast (<10ms per request), no database by default.

**Key Design Principle**: This is a heuristic-based fraud flagging system, not a hard blocker. The API returns warnings for review by downstream systems—it never rejects transactions.

## Commands

### Development
```bash
# Activate virtual environment
source venv/bin/activate

# Run the API locally (listens on http://localhost:5000)
python app.py

# Test the API (requires running in another terminal)
bash test_api.sh

# Quick health check
curl http://localhost:5000/health

# View HTML docs
open http://localhost:5000/docs
```

### Docker
```bash
# Build image
docker build -t transaction-validator .

# Run container
docker run -p 5000:5000 transaction-validator
```

## Architecture

### Single-File Design
All code lives in [app.py](app.py)—no modularization yet. Structure:
1. **Constants** (lines 20–29): Validation thresholds (`MIN_AMOUNT`, `DAILY_LIMIT`, `SUSPICIOUS_HOUR_THRESHOLD`)
2. **Response Helpers** (lines 36–70): `success_response()`, `error_response()`, `log_request()` decorator
3. **Validation** (lines 77–144): `validate_transaction_payload()` checks required fields, types, ranges, timestamp age
4. **Fraud Detection** (lines 147–185): `check_fraud_signals()` flags HIGH_VALUE, EXCESSIVE_WITHDRAWAL, ROUND_AMOUNT
5. **Routes** (lines 192–504): `/health`, `/validate/transaction`, `/docs` (HTML)
6. **Error Handlers** (lines 581–603)
7. **Entry Point** (lines 610–618)

### Request/Response Shape
- **Validation**: Checks amount bounds, transaction type enum, account ID range, ISO 8601 timestamp (not >90 days old, not future)
- **Fraud Signals**: Returns array of signals with `type`, `severity`, `message`. Risk score = `num_signals * 25`
- **Error Handling**: Missing Content-Type returns 415. Invalid payload returns 400 with detailed error list. Validation errors do NOT block—they're returned in response.fraud_signals for downstream review

### Key Constants
Modify at top of [app.py](app.py):
- `SINGLE_TXN_HIGH_RISK = 50_000` — flag transactions above this
- `DAILY_LIMIT = 100_000` — flag withdrawals above this
- `SUSPICIOUS_HOUR_THRESHOLD = 10` — (planned feature, not yet used)

## Testing Strategy

**Manual Testing**: `bash test_api.sh` runs curl-based smoke tests against a running instance. Does not require pytest or complex test setup.

**No Unit Tests Yet**: README notes "we don't have tests yet (bad, I know)". If adding tests, follow the example structure in README.md (Flask test client with POST to `/validate/transaction`).

## Deployment

**Render**: Service auto-detects `render.yaml`. Deployment is: GitHub → Render UI → auto-deploy. Service listens on `0.0.0.0:5000` (port fixed).

**Docker**: Builds on Python 3.13, installs requirements.txt, runs gunicorn (2 workers via render.yaml).

## Known Limitations & TODOs

- **No persistence**: Transactions aren't stored (stateless by design)
- **Simple heuristics**: Not ML-based; see README for integration with Stripe Radar, AWS Fraud Detector
- **No rate limiting**: Add with flask-limiter if needed
- **Planned signals** (SUSPICIOUS_HOUR_THRESHOLD is defined but not used yet)
- **Batch validation**: Single-transaction only; batch endpoint is in README future work

## Common Edits

### Add a New Fraud Signal
1. Define logic in `check_fraud_signals()` → append to `signals[]`
2. Each signal: `{"type": "...", "severity": "LOW|MEDIUM|HIGH", "message": "..."}`
3. Risk score auto-increments by 25 per signal
4. Update `/docs` HTML (lines 506–522) to document

### Change Validation Rules
Edit constants (lines 20–29) or the `validate_transaction_payload()` function body. Add new errors to the `errors[]` list; they're returned in response.errors (400 status).

### Add a New Endpoint
Add a `@app.route()` decorator in the Routes section (lines 192+). Use `success_response()` and `error_response()` helpers for consistent JSON formatting.
