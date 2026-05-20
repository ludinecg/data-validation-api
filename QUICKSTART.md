# Quick Start Guide

Get the API running in 5 minutes.

## Option 1: Run Locally (Recommended for Development)

```bash
# Navigate to project
cd data-validation-api

# Create & activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the API
python3 app.py
```

The API is now live at `http://localhost:5000`.

## Option 2: With Docker

```bash
# Build image
docker build -t transaction-validator .

# Run container
docker run -p 5000:5000 transaction-validator
```

## Quick Test

In another terminal:

```bash
# Health check
curl http://localhost:5000/health

# Test validation
curl -X POST http://localhost:5000/validate/transaction \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 100.00,
    "transaction_type": "TRANSFER",
    "account_id": 12345,
    "timestamp": "2024-05-18T14:30:00Z"
  }'

# View docs
open http://localhost:5000/docs
```

## Run Full Test Suite

```bash
bash test_api.sh
```

(Make sure the API is running in another terminal)

## Deploy to Render

1. Push to GitHub:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

2. Go to [render.com](https://render.com)

3. Click "New" → "Web Service"

4. Select your repo

5. Render auto-detects `render.yaml` → Deploy

That's it! Your API is live.

---

## Next Steps

- Check out `/docs` for full API documentation
- Read [README.md](README.md) for detailed info
- Review [app.py](app.py) source code (well-commented)
- Modify fraud rules in the `CONSTANTS` section of `app.py`
