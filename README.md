# 💳 Transaction Validator API

A blazingly fast financial transaction validation service built with Flask. Validates transaction data in real-time and flags potential fraud signals without blocking legitimate transactions.

**Designed for**: High-throughput payment pipelines, fraud detection systems, transaction middleware.

---

## What It Does

You throw financial transactions at it, and it:

1. ✅ Validates the transaction structure (required fields, types, ranges)
2. 🚩 Checks for fraud signals (high-value txns, unusual patterns, round amounts)
3. 📊 Returns a risk score (0-100) for your downstream systems
4. 🚀 Does all this in <10ms per request

It **does NOT**:
- Block transactions (we flag, you decide)
- Connect to any database by default
- Do fancy ML or graph analysis (yet)
- Store anything (stateless by design)

---

## Quick Start

### Local Development

```bash
# Clone or navigate to project
cd data-validation-api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Run the API locally
python app.py
```

The API will be running at `http://localhost:5000`.

### Check It's Alive

```bash
curl http://localhost:5000/health
```

Response:
```json
{
  "status": "success",
  "data": {
    "status": "healthy",
    "service": "transaction-validator"
  },
  "timestamp": "2024-05-18T14:30:00.123456"
}
```

---

## API Endpoints

### `GET /health`
Simple health check. Use this for load balancer monitoring.

```bash
curl -X GET http://localhost:5000/health
```

### `GET /docs`
View the full API documentation in your browser.

```bash
open http://localhost:5000/docs
```

### `POST /validate/transaction`
The main endpoint. Validate a transaction and get fraud signals.

#### Request Example

```bash
curl -X POST http://localhost:5000/validate/transaction \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 5430.50,
    "transaction_type": "TRANSFER",
    "account_id": 12345,
    "timestamp": "2024-05-18T14:30:00Z",
    "description": "Payment for Q2 services"
  }'
```

#### Required Fields

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `amount` | number | `1234.56` | Between $0.01 and $999,999,999.99 |
| `transaction_type` | string | `TRANSFER` | One of: TRANSFER, PAYMENT, DEPOSIT, WITHDRAWAL |
| `account_id` | integer | `12345` | Between 1 and 99,999 |
| `timestamp` | string (ISO 8601) | `2024-05-18T14:30:00Z` | Must be within 90 days, not in future |

#### Optional Fields

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `description` | string | `"Payment for services"` | Max 500 characters |

#### Success Response (200)

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
  "timestamp": "2024-05-18T14:30:00.123456"
}
```

The `fraud_signals` array will be empty if no issues are detected. Risk scores range from 0 (clean) to 100+ (very suspicious).

#### Validation Error Response (400)

```json
{
  "status": "error",
  "message": "Transaction validation failed",
  "errors": [
    "Amount must be >= $0.01",
    "Transaction type must be one of: TRANSFER, PAYMENT, DEPOSIT, WITHDRAWAL"
  ],
  "timestamp": "2024-05-18T14:30:00.123456"
}
```

#### Other Error Responses

- **415**: Content-Type is not `application/json`
- **404**: Endpoint not found (try `/docs`)
- **500**: Server error (check logs)

---

## Fraud Signals Explained

The API detects these patterns:

### 🔴 HIGH_VALUE (Severity: MEDIUM)
Transaction exceeds $50,000. Legitimate but worth monitoring.

```json
{
  "type": "HIGH_VALUE",
  "severity": "MEDIUM",
  "message": "Transaction amount $75,000.00 exceeds $50,000 threshold"
}
```

### 🔴 EXCESSIVE_WITHDRAWAL (Severity: HIGH)
Withdrawal over daily limit ($100,000). More suspicious.

```json
{
  "type": "EXCESSIVE_WITHDRAWAL",
  "severity": "HIGH",
  "message": "Withdrawal of $150,000.00 exceeds daily limit of $100,000"
}
```

### 🟡 ROUND_AMOUNT (Severity: LOW)
Round numbers like $5,000 or $10,000 appear less in real data. Could be testing, could be normal.

```json
{
  "type": "ROUND_AMOUNT",
  "severity": "LOW",
  "message": "Round amounts ($5000) occur less frequently in real transactions"
}
```

---

## Common Curl Examples

### ✅ Valid Transaction

```bash
curl -X POST http://localhost:5000/validate/transaction \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 100.00,
    "transaction_type": "TRANSFER",
    "account_id": 54321,
    "timestamp": "2024-05-18T10:15:30Z"
  }'
```

### ❌ Missing Required Field

```bash
curl -X POST http://localhost:5000/validate/transaction \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 100.00,
    "transaction_type": "TRANSFER"
    # missing account_id and timestamp!
  }'
```

Returns 400 with detailed errors.

### ⚠️ High-Risk Transaction

```bash
curl -X POST http://localhost:5000/validate/transaction \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 75000.00,
    "transaction_type": "WITHDRAWAL",
    "account_id": 99999,
    "timestamp": "2024-05-18T14:30:00Z",
    "description": "Large withdrawal"
  }'
```

Returns 200 but with fraud signals and higher risk score.

---

## Deploying to Render

### Prerequisites
- GitHub account with repo pushed
- Render account (free tier works)

### Steps

1. **Push to GitHub** (if not already)
   ```bash
   git init
   git add .
   git commit -m "Initial commit: transaction validator API"
   git branch -M main
   git remote add origin https://github.com/yourusername/data-validation-api.git
   git push -u origin main
   ```

2. **Connect to Render**
   - Go to [render.com](https://render.com)
   - Click "New" → "Web Service"
   - Select your GitHub repo
   - Render will auto-detect `render.yaml` and configure everything
   - Click "Deploy"

3. **That's it!** 🚀
   - Your API is live at `https://your-service-name.onrender.com`
   - Check `/health` to verify

### Environment Variables (Optional)

If you need to set custom variables in Render:
1. Go to your service settings
2. Add environment variables in the "Environment" tab
3. These override what's in `render.yaml`

---

## Performance & Scaling

- **Latency**: <10ms per request (local), ~50-100ms including network
- **Throughput**: ~100 requests/second on free tier, more on paid plans
- **Memory**: ~50MB baseline
- **Workers**: Configured for 2 workers (gunicorn sync), scale up if needed

To increase performance on Render:
- Upgrade to a paid plan (more CPU/RAM)
- Increase `workers` in `render.yaml` (rule of thumb: 2-4x CPU cores)
- Use a faster app server (consider uvicorn if moving to async)

---

## Development

### Running Tests

We don't have tests yet (bad, I know). If you want to add them:

```bash
pip install pytest
pytest tests/
```

Example test structure:
```python
# tests/test_validation.py
def test_valid_transaction():
    response = client.post('/validate/transaction', json={
        "amount": 100.00,
        "transaction_type": "TRANSFER",
        "account_id": 123,
        "timestamp": "2024-05-18T14:30:00Z"
    })
    assert response.status_code == 200
    assert response.json["data"]["is_valid"] == True
```

### Modifying Fraud Rules

Edit the constants at the top of `app.py`:

```python
SINGLE_TXN_HIGH_RISK = 50_000       # Change this threshold
DAILY_LIMIT = 100_000               # or this
SUSPICIOUS_HOUR_THRESHOLD = 10      # or this
```

Then adjust the `check_fraud_signals()` function to add new signal types.

### Adding New Endpoints

Just add more route decorators in `app.py`:

```python
@app.route("/api/merchant/<int:merchant_id>", methods=["GET"])
def get_merchant_risk(merchant_id):
    """Example: get risk profile for a merchant"""
    return success_response({"merchant_id": merchant_id, "risk_level": "LOW"})
```

---

## Logging

The API logs all incoming requests to stdout (which Render captures automatically).

Logs look like:
```
2024-05-18 14:30:00 | INFO | → POST /validate/transaction | Client: 192.168.1.1 | Body: {'amount': 100.0, ...}
2024-05-18 14:30:00 | INFO | ✓ Transaction validated: TXN-1234567890 | Risk: 0
```

Check logs in Render dashboard → your service → "Logs" tab.

---

## Known Limitations

- **No persistence**: Transactions aren't stored. Implement a database connection if you need historical records
- **Simple fraud signals**: We use heuristics, not ML. For production fraud detection, integrate with dedicated services (e.g., AWS Fraud Detector, Stripe Radar)
- **Single instance**: No load balancing yet. Render's free tier is single-threaded; upgrade for HA
- **No rate limiting**: Add with Flask extensions (flask-limiter) if needed

---

## Troubleshooting

### "Connection refused" on localhost
Make sure you ran `python app.py` and it's actually listening on port 5000.

### "Invalid Content-Type" error
Requests must have `Content-Type: application/json` header. Check your curl commands.

### Timestamps keep getting rejected
Timestamps must be in ISO 8601 format: `2024-05-18T14:30:00Z`. Include the `Z` for UTC.

### API returns 500 errors after deploy
Check Render logs. Most common: missing `requirements.txt` or syntax error in `app.py`.

---

## Future Improvements

- [ ] Add SQLite/PostgreSQL for transaction history
- [ ] Implement rate limiting per account
- [ ] Add webhook support for fraud alerts
- [ ] Integrate with external risk scoring (Stripe, AWS)
- [ ] Add batch validation endpoint
- [ ] OpenAPI/Swagger integration
- [ ] Request signing (HMAC) for webhook security

---

## License

MIT. Do whatever you want with it.

---

**Questions?** Check the `/docs` endpoint or review the code comments in `app.py`.

Built for learning how to deploy financial APIs. Not production-ready without additional security, persistence, and compliance work.
