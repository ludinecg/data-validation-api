# Transaction Validator API

A lightweight, high-performance REST API for validating financial transactions in real-time. Detects potential fraud signals using heuristic analysis while maintaining sub-10ms latency.

**Status**: Production-ready | **License**: MIT

### Live API
The API is deployed on Render and available at:
```
https://data-validation-api.onrender.com
```

Quick test:
```bash
curl https://data-validation-api.onrender.com/health
```

---

## Overview

This service validates transaction structure and detects fraud signals without blocking legitimate transactions. It's designed as a data quality layer for payment pipelines, returning risk assessments for downstream review systems.

### Core Features

- Real-time transaction validation with detailed error reporting
- Heuristic-based fraud signal detection (non-blocking)
- Stateless design for horizontal scaling
- Sub-10ms response times per request
- Docker and Render deployment ready
- Comprehensive API documentation endpoint

### What It Does NOT Do

- Block or reject transactions (signals only)
- Store transaction history (stateless by design)
- Perform ML-based fraud detection
- Require external databases

---

## Technical Stack

| Component | Technology |
|-----------|-----------|
| Framework | Flask 3.0.0 |
| Language | Python 3.11+ |
| Server | Gunicorn (WSGI) |
| Deployment | Render (free tier) |
| Container | Docker (multi-stage build) |
| Package Manager | pip |

---

## Getting Started

### Option 1: Local Development

```bash
# Clone repository
cd data-validation-api

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run API (listens on http://localhost:5000)
python3 app.py
```

### Option 2: Docker

```bash
# Build image
docker build -t transaction-validator .

# Run container
docker run -p 5000:5000 transaction-validator
```

### Quick Test

```bash
# Health check
curl http://localhost:5000/health

# View API documentation
open http://localhost:5000/docs

# Run full test suite
bash test_api.sh
```

---

## API Endpoints

### GET /health

Health check endpoint for monitoring and load balancers.

```bash
curl http://localhost:5000/health
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "status": "healthy",
    "service": "transaction-validator"
  },
  "timestamp": "2024-05-20T14:30:00.123456"
}
```

---

### POST /validate/transaction

Validates transaction data and returns fraud signals and risk score.

**Request:**
```bash
curl -X POST http://localhost:5000/validate/transaction \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 5430.50,
    "transaction_type": "TRANSFER",
    "account_id": 12345,
    "timestamp": "2024-05-20T14:30:00Z",
    "description": "Payment for Q2 services"
  }'
```

**Required Fields:**

| Field | Type | Range | Example |
|-------|------|-------|---------|
| `amount` | float | $0.01 - $999,999,999.99 | `5430.50` |
| `transaction_type` | string | TRANSFER, PAYMENT, DEPOSIT, WITHDRAWAL | `"TRANSFER"` |
| `account_id` | integer | 1 - 99,999 | `12345` |
| `timestamp` | ISO 8601 | Within 90 days, not future | `"2024-05-20T14:30:00Z"` |

**Optional Fields:**

| Field | Type | Limit |
|-------|------|-------|
| `description` | string | 500 characters max |

**Success Response (200):**
```json
{
  "status": "success",
  "data": {
    "transaction_id": "TXN-1234567890",
    "is_valid": true,
    "amount": 5430.50,
    "transaction_type": "TRANSFER",
    "account_id": 12345,
    "fraud_signals": [
      {
        "type": "HIGH_VALUE",
        "severity": "MEDIUM",
        "message": "Transaction amount $5,430.50 exceeds $50,000 threshold"
      }
    ],
    "risk_score": 25
  },
  "timestamp": "2024-05-20T14:30:00.123456"
}
```

**Validation Error Response (400):**
```json
{
  "status": "error",
  "message": "Transaction validation failed",
  "errors": [
    "Amount must be >= $0.01",
    "Transaction type must be one of: TRANSFER, PAYMENT, DEPOSIT, WITHDRAWAL"
  ],
  "timestamp": "2024-05-20T14:30:00.123456"
}
```

**Other Error Responses:**
- **415**: Content-Type is not `application/json`
- **404**: Endpoint not found (try `/docs`)
- **500**: Server error (check logs)

---

### GET /docs

Interactive HTML documentation with fraud signal descriptions and examples.

```bash
open http://localhost:5000/docs
```

---

## Fraud Signals Explained

The API detects three types of fraud signals:

### HIGH_VALUE
**Severity**: MEDIUM  
**Trigger**: Transaction amount >= $50,000  
**Interpretation**: Large transactions are legitimate but warrant monitoring.

```json
{
  "type": "HIGH_VALUE",
  "severity": "MEDIUM",
  "message": "Transaction amount $75,000.00 exceeds $50,000 threshold"
}
```

### EXCESSIVE_WITHDRAWAL
**Severity**: HIGH  
**Trigger**: Withdrawal > $100,000 (daily limit)  
**Interpretation**: Exceeds normal daily withdrawal pattern.

```json
{
  "type": "EXCESSIVE_WITHDRAWAL",
  "severity": "HIGH",
  "message": "Withdrawal of $150,000.00 exceeds daily limit of $100,000"
}
```

### ROUND_AMOUNT
**Severity**: LOW  
**Trigger**: Amount is multiple of $100 and >= $1,000  
**Interpretation**: Round numbers appear less frequently in real data. May indicate testing or unusual activity.

```json
{
  "type": "ROUND_AMOUNT",
  "severity": "LOW",
  "message": "Round amounts ($5,000) occur less frequently in real transactions"
}
```

---

## Risk Score

Risk score is calculated as:
```
risk_score = number_of_fraud_signals * 25
```

- **0**: No signals detected
- **25**: One signal detected
- **50**: Two signals detected
- **100+**: Multiple signals detected

The risk score is advisory. Transactions with high risk scores should be reviewed, not automatically blocked.

---

## Configuration

### Fraud Detection Thresholds

Edit these constants in `app.py` (lines 20-30):

```python
SINGLE_TXN_HIGH_RISK = 50_000      # HIGH_VALUE threshold
DAILY_LIMIT = 100_000              # EXCESSIVE_WITHDRAWAL threshold
SUSPICIOUS_HOUR_THRESHOLD = 10     # Planned feature
```

### Environment Variables

Set in `render.yaml` or your local environment:

```bash
PORT=5000                          # Server port (default: 5000)
FLASK_ENV=production               # Flask environment
PYTHONUNBUFFERED=1                 # Unbuffered logging
```

---

## Testing

### Manual Tests

Run provided test suite:

```bash
bash test_api.sh
```

Tests cover:
- Health check (200)
- Valid transaction (200)
- Missing required fields (400)
- Negative amounts (400)
- Invalid transaction types (400)
- High-value transactions (200 with fraud signals)
- Invalid timestamps (400)
- Missing Content-Type header (415)

### Example Requests

**Valid transaction:**
```bash
curl -X POST http://localhost:5000/validate/transaction \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 100.00,
    "transaction_type": "TRANSFER",
    "account_id": 54321,
    "timestamp": "2024-05-20T10:15:30Z"
  }'
```

**High-risk transaction:**
```bash
curl -X POST http://localhost:5000/validate/transaction \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 75000.00,
    "transaction_type": "WITHDRAWAL",
    "account_id": 99999,
    "timestamp": "2024-05-20T14:30:00Z"
  }'
```

**Missing required field:**
```bash
curl -X POST http://localhost:5000/validate/transaction \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 100.00,
    "transaction_type": "TRANSFER"
  }'
```

---

## Deployment

### Render (Recommended)

1. **Push to GitHub**
   ```bash
   git push origin main
   ```

2. **Connect to Render**
   - Go to render.com
   - Click "New" → "Web Service"
   - Select your GitHub repository
   - Render auto-detects `render.yaml` configuration

3. **Deploy**
   - Click "Deploy"
   - Service is live at `https://data-validation-api.onrender.com`

4. **Verify**
   ```bash
   curl https://data-validation-api.onrender.com/health
   ```

### Docker

```bash
docker build -t transaction-validator .
docker run -p 5000:5000 transaction-validator
```

---

## Performance

### Benchmarks

| Metric | Value |
|--------|-------|
| Response latency (local) | <10ms |
| Response latency (Render) | 50-100ms (includes network) |
| Throughput (free tier) | ~100 req/s |
| Memory usage | ~50MB baseline |
| Workers (gunicorn) | 2 (configurable) |

### Scaling

To improve performance on Render:
- Upgrade to paid plan (more CPU/RAM)
- Increase workers in `render.yaml`: `--workers 4` (2-4x CPU cores)
- Use async framework (consider uvicorn for Flask+asyncio)

---

## Development

### Project Structure

```
data-validation-api/
├── app.py                 # Main application (all logic)
├── requirements.txt       # Python dependencies
├── render.yaml            # Render deployment config
├── Dockerfile             # Container definition
├── test_api.sh            # Test suite
├── README.md              # This file
├── ARCHITECTURE.md        # Technical architecture
├── LICENSE                # MIT License
├── .gitignore             # Git ignore rules
├── .dockerignore           # Docker build ignore
└── venv/                  # Virtual environment (not committed)
```

### Adding a New Fraud Signal

1. Implement logic in `check_fraud_signals()`:
```python
if amount % 500 == 0 and amount >= 5000:
    signals.append({
        "type": "UNUSUAL_AMOUNT",
        "severity": "LOW",
        "message": "Transaction amount pattern may indicate testing"
    })
```

2. Update `/docs` HTML to document the new signal

3. Test:
```bash
bash test_api.sh
```

### Adding a New Endpoint

```python
@app.route("/api/accounts/<int:account_id>/risk", methods=["GET"])
def get_account_risk(account_id):
    """Get aggregated risk profile for an account."""
    return success_response({
        "account_id": account_id,
        "risk_level": "LOW",
        "signals_this_week": 0
    })
```

---

## Logging

The API logs all requests to stdout. Render captures logs automatically.

**Log Format:**
```
2024-05-20 14:30:00 | INFO | → POST /validate/transaction | Client: 192.168.1.1 | Body: {...}
2024-05-20 14:30:00 | INFO | Transaction validated: TXN-1234567890 | Risk: 25
```

Access logs in Render dashboard: Dashboard → Your Service → Logs tab

---

## Known Limitations

- **No persistence**: Transactions are validated but not stored
- **Simple heuristics**: Based on rules, not ML models
- **Single instance**: Free tier is single-threaded
- **No rate limiting**: Add `flask-limiter` if needed
- **No authentication**: All endpoints are public (add API keys if needed)

---

## Future Roadmap

- Batch validation endpoint (`POST /validate/batch`)
- Rate limiting per account or API key
- Request signing (HMAC) for webhook security
- PostgreSQL integration for transaction history
- Webhook support for fraud alerts
- OpenAPI/Swagger integration
- Integration with Stripe Radar or AWS Fraud Detector

---

## Troubleshooting

### "Connection refused" on localhost

Make sure the API is running:
```bash
python3 app.py
```

Check that port 5000 is not already in use:
```bash
lsof -i :5000
```

### "Invalid Content-Type" error

All requests must include the `Content-Type: application/json` header:
```bash
curl -X POST http://localhost:5000/validate/transaction \
  -H "Content-Type: application/json" \
  -d '...'
```

### "Timestamps keep getting rejected"

Timestamps must be in ISO 8601 format with UTC timezone:
```
Valid:   2024-05-20T14:30:00Z
Invalid: 2024-05-20 14:30:00
Invalid: 05/20/2024
```

### API returns 500 errors after Render deployment

Check Render logs:
1. Go to Render dashboard
2. Select your service
3. Click "Logs" tab
4. Common issues:
   - Missing `requirements.txt`
   - Syntax error in `app.py`
   - Port binding issues

---

## Contributing

For feature requests or bug reports, please open an issue with:
- Description of the issue
- Steps to reproduce
- Expected vs. actual behavior
- Environment (local, Docker, Render)

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Author

**Ludin Castillo** | Data Engineer & BI Specialist  
[LinkedIn](https://linkedin.com/in/ludincastillo) | [GitHub](https://github.com/ludinecg)

---

**Built with Python, Flask, and attention to detail.**
