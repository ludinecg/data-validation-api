"""
Financial transaction validation API built with Flask.
Validates transactions with configurable rules and returns detailed error messages.
"""

from flask import Flask, request, jsonify, render_template_string
from datetime import datetime, timedelta
from functools import wraps
import logging
from typing import Dict, Tuple, Any
import os

app = Flask(__name__)
logger = logging.getLogger(__name__)


# ============================================================================
# Validation Rules & Constants
# ============================================================================

TRANSACTION_TYPES = {"TRANSFER", "PAYMENT", "DEPOSIT", "WITHDRAWAL"}
MIN_AMOUNT = 0.01
MAX_AMOUNT = 999_999_999.99
MIN_ACCOUNT_ID = 1
MAX_ACCOUNT_ID = 99_999

# Fraud detection thresholds
DAILY_LIMIT = 100_000              # Maximum withdrawal amount per day
SINGLE_TXN_HIGH_RISK = 50_000      # Flag transactions above this amount
SUSPICIOUS_HOUR_THRESHOLD = 10     # Reserved for future use (transactions per hour)


# ============================================================================
# Response Helpers
# ============================================================================

def success_response(data: Any, status_code: int = 200) -> Tuple[Dict, int]:
    """Return a properly formatted success response."""
    return (
        {
            "status": "success",
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        },
        status_code,
    )


def error_response(message: str, errors: list = None, status_code: int = 400) -> Tuple[Dict, int]:
    """Return a properly formatted error response."""
    response = {
        "status": "error",
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if errors:
        response["errors"] = errors
    return response, status_code


def log_request(f):
    """Decorator to log incoming requests."""
    @wraps(f)
    def decorated(*args, **kwargs):
        logger.info(
            f"→ {request.method} {request.path} | "
            f"Client: {request.remote_addr} | "
            f"Body: {request.get_json()}"
        )
        return f(*args, **kwargs)
    return decorated


# ============================================================================
# Validation Functions
# ============================================================================

def validate_transaction_payload(payload: Dict) -> Tuple[bool, list]:
    """
    Validate the transaction payload structure and values.

    Args:
        payload: The transaction data to validate

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    required_fields = {"amount", "transaction_type", "account_id", "timestamp"}

    # Check required fields
    missing = required_fields - set(payload.keys())
    if missing:
        errors.append(f"Missing required fields: {', '.join(sorted(missing))}")
        return False, errors

    # Validate amount
    try:
        amount = float(payload.get("amount", 0))
        if amount < MIN_AMOUNT:
            errors.append(f"Amount must be >= ${MIN_AMOUNT}")
        elif amount > MAX_AMOUNT:
            errors.append(f"Amount cannot exceed ${MAX_AMOUNT:,.2f}")
    except (ValueError, TypeError):
        errors.append("Amount must be a valid number")

    # Validate transaction type
    txn_type = payload.get("transaction_type", "").upper()
    if txn_type not in TRANSACTION_TYPES:
        errors.append(f"Transaction type must be one of: {', '.join(TRANSACTION_TYPES)}")

    # Validate account ID
    try:
        account_id = int(payload.get("account_id", 0))
        if not (MIN_ACCOUNT_ID <= account_id <= MAX_ACCOUNT_ID):
            errors.append(f"Account ID must be between {MIN_ACCOUNT_ID} and {MAX_ACCOUNT_ID}")
    except (ValueError, TypeError):
        errors.append("Account ID must be a valid integer")

    # Validate timestamp format and age
    timestamp_str = payload.get("timestamp", "")
    try:
        txn_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        now = datetime.utcnow()

        # Check if timestamp is not in the future (allow 1 min clock skew)
        if txn_time > now + timedelta(minutes=1):
            errors.append("Transaction timestamp cannot be in the future")

        # Check if timestamp is not too old (>90 days)
        if (now - txn_time).days > 90:
            errors.append("Transaction timestamp cannot be older than 90 days")

    except (ValueError, TypeError):
        errors.append("Timestamp must be in ISO 8601 format (e.g., 2024-05-18T14:30:00Z)")

    # Validate optional fields if present
    if "description" in payload:
        desc = payload.get("description", "")
        if not isinstance(desc, str):
            errors.append("Description must be a string")
        elif len(desc) > 500:
            errors.append("Description cannot exceed 500 characters")

    return len(errors) == 0, errors


def check_fraud_signals(payload: Dict) -> Dict:
    """
    Check for potential fraud signals. These are heuristic flags, not hard blocks.

    Args:
        payload: The validated transaction data

    Returns:
        Dict with fraud signals detected
    """
    signals = []
    amount = float(payload.get("amount", 0))
    txn_type = payload.get("transaction_type", "").upper()

    # Signal 1: High-value transaction
    if amount >= SINGLE_TXN_HIGH_RISK:
        signals.append({
            "type": "HIGH_VALUE",
            "severity": "MEDIUM",
            "message": f"Transaction amount ${amount:,.2f} exceeds ${SINGLE_TXN_HIGH_RISK:,} threshold"
        })

    # Signal 2: Unusual transaction type for amount
    if txn_type == "WITHDRAWAL" and amount > DAILY_LIMIT:
        signals.append({
            "type": "EXCESSIVE_WITHDRAWAL",
            "severity": "HIGH",
            "message": f"Withdrawal of ${amount:,.2f} exceeds daily limit of ${DAILY_LIMIT:,}"
        })

    # Signal 3: Round numbers frequently appear in test transactions or unusual patterns
    if amount % 100 == 0 and amount >= 1000:
        signals.append({
            "type": "ROUND_AMOUNT",
            "severity": "LOW",
            "message": f"Round amounts (${amount:,.0f}) occur less frequently in real transactions"
        })

    return {"fraud_signals": signals, "risk_score": len(signals) * 25}


# ============================================================================
# API Endpoints
# ============================================================================

@app.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    Returns 200 if service is up.
    """
    return success_response({"status": "healthy", "service": "transaction-validator"})


@app.route("/validate/transaction", methods=["POST"])
@log_request
def validate_transaction():
    """
    Validate a financial transaction.

    Expected JSON payload:
    {
        "amount": 1234.56,
        "transaction_type": "TRANSFER",
        "account_id": 12345,
        "timestamp": "2024-05-18T14:30:00Z",
        "description": "Optional txn description"
    }

    Returns:
    - 200: Transaction is valid (with optional fraud signals)
    - 400: Validation failed with detailed errors
    - 415: Invalid Content-Type
    """

    # Check content type
    if not request.is_json:
        return error_response(
            "Content-Type must be application/json",
            status_code=415
        )

    payload = request.get_json()

    # Validate payload structure & values
    is_valid, validation_errors = validate_transaction_payload(payload)
    if not is_valid:
        logger.warning(f"Validation failed: {validation_errors}")
        return error_response(
            "Transaction validation failed",
            errors=validation_errors,
            status_code=400
        )

    # Check for fraud signals
    fraud_check = check_fraud_signals(payload)

    # Build response
    response_data = {
        "transaction_id": f"TXN-{hash(str(payload)) % 10**10:010d}",
        "is_valid": True,
        "amount": float(payload["amount"]),
        "transaction_type": payload["transaction_type"].upper(),
        "account_id": int(payload["account_id"]),
        "fraud_signals": fraud_check["fraud_signals"],
        "risk_score": fraud_check["risk_score"],
    }

    logger.info(f"VALIDATED Transaction {response_data['transaction_id']} | Risk score: {fraud_check['risk_score']}")
    return success_response(response_data, status_code=200)


@app.route("/docs", methods=["GET"])
def api_documentation():
    """
    Serve basic API documentation as HTML.
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Transaction Validator API - Docs</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                line-height: 1.6;
                color: #333;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 900px;
                margin: 0 auto;
                background: white;
                border-radius: 10px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.1);
                overflow: hidden;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 40px 20px;
                text-align: center;
            }
            .header h1 {
                font-size: 2.5em;
                margin-bottom: 10px;
            }
            .header p {
                font-size: 1.1em;
                opacity: 0.9;
            }
            .content {
                padding: 40px;
            }
            section {
                margin-bottom: 40px;
            }
            h2 {
                color: #667eea;
                border-bottom: 2px solid #667eea;
                padding-bottom: 10px;
                margin-bottom: 20px;
            }
            .endpoint {
                background: #f5f5f5;
                border-left: 4px solid #667eea;
                padding: 15px;
                margin: 15px 0;
                border-radius: 5px;
                font-family: 'Courier New', monospace;
            }
            .method {
                display: inline-block;
                padding: 4px 8px;
                border-radius: 3px;
                font-weight: bold;
                margin-right: 10px;
            }
            .method.post { background: #4CAF50; color: white; }
            .method.get { background: #2196F3; color: white; }
            code {
                background: #2c3e50;
                color: #ecf0f1;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
            }
            pre {
                background: #2c3e50;
                color: #ecf0f1;
                padding: 15px;
                border-radius: 5px;
                overflow-x: auto;
                margin: 10px 0;
                font-size: 0.9em;
                line-height: 1.4;
            }
            .field {
                margin: 10px 0;
                padding: 10px;
                background: white;
                border-left: 3px solid #764ba2;
            }
            .field strong { color: #667eea; }
            .field em { color: #666; }
            .example {
                background: #f9f9f9;
                border: 1px solid #ddd;
                padding: 15px;
                border-radius: 5px;
                margin: 15px 0;
            }
            .example h4 {
                color: #333;
                margin-bottom: 10px;
            }
            .status-code {
                display: inline-block;
                padding: 4px 10px;
                border-radius: 3px;
                font-weight: bold;
                margin-right: 10px;
            }
            .status-200 { background: #d4edda; color: #155724; }
            .status-400 { background: #f8d7da; color: #721c24; }
            .status-415 { background: #f8d7da; color: #721c24; }
            footer {
                background: #f5f5f5;
                padding: 20px;
                text-align: center;
                color: #666;
                border-top: 1px solid #ddd;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>💳 Transaction Validator API</h1>
                <p>Simple, fast financial transaction validation service</p>
            </div>

            <div class="content">
                <!-- Introduction -->
                <section>
                    <h2>Overview</h2>
                    <p>The Transaction Validator API validates financial transactions and detects fraud signals in real-time. It's designed for high-throughput payment processing pipelines.</p>
                    <p><strong>Base URL:</strong> <code>/api/v1</code> (or root if deployed)</p>
                </section>

                <!-- Endpoints -->
                <section>
                    <h2>Endpoints</h2>

                    <div class="endpoint">
                        <span class="method get">GET</span>
                        <code>/health</code>
                    </div>
                    <p>Health check for monitoring. Always returns 200 if the service is running.</p>
                    <div class="example">
                        <h4>Example:</h4>
                        <pre>curl https://your-api.com/health</pre>
                        <strong>Response:</strong>
                        <pre>{
  "status": "success",
  "data": {
    "status": "healthy",
    "service": "transaction-validator"
  }
}</pre>
                    </div>

                    <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">

                    <div class="endpoint">
                        <span class="method post">POST</span>
                        <code>/validate/transaction</code>
                    </div>
                    <p>Validate a transaction and check for fraud signals.</p>

                    <h3 style="margin-top: 20px; color: #333; font-size: 1.1em;">Request Body</h3>
                    <div class="field">
                        <strong>amount</strong> <em>number, required</em><br>
                        Transaction amount. Must be between $0.01 and $999,999,999.99
                    </div>
                    <div class="field">
                        <strong>transaction_type</strong> <em>string, required</em><br>
                        Type of transaction. Must be one of: TRANSFER, PAYMENT, DEPOSIT, WITHDRAWAL
                    </div>
                    <div class="field">
                        <strong>account_id</strong> <em>integer, required</em><br>
                        Account identifier. Must be between 1 and 99,999
                    </div>
                    <div class="field">
                        <strong>timestamp</strong> <em>string (ISO 8601), required</em><br>
                        Transaction timestamp. Format: <code>2024-05-18T14:30:00Z</code>. Must be within 90 days.
                    </div>
                    <div class="field">
                        <strong>description</strong> <em>string, optional</em><br>
                        Optional description. Max 500 characters.
                    </div>

                    <div class="example">
                        <h4>Example Request:</h4>
                        <pre>curl -X POST https://your-api.com/validate/transaction \\
  -H "Content-Type: application/json" \\
  -d '{
    "amount": 5430.50,
    "transaction_type": "TRANSFER",
    "account_id": 12345,
    "timestamp": "2024-05-18T14:30:00Z",
    "description": "Payment for services rendered"
  }'</pre>
                    </div>

                    <h3 style="margin-top: 20px; color: #333; font-size: 1.1em;">Response</h3>
                    <div class="status-code status-200">200 OK</div>
                    <p>Transaction is valid. May include fraud signals for manual review.</p>
                    <pre>{
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
        "message": "Transaction amount $50,000.00 exceeds $50,000 threshold"
      }
    ],
    "risk_score": 25
  },
  "timestamp": "2024-05-18T15:45:30.123456"
}</pre>

                    <div class="status-code status-400">400 Bad Request</div>
                    <p>Validation failed. Response includes detailed error messages.</p>
                    <pre>{
  "status": "error",
  "message": "Transaction validation failed",
  "errors": [
    "Amount must be >= $0.01",
    "Transaction type must be one of: TRANSFER, PAYMENT, DEPOSIT, WITHDRAWAL"
  ],
  "timestamp": "2024-05-18T15:45:30.123456"
}</pre>

                    <div class="status-code status-415">415 Unsupported Media Type</div>
                    <p>Request Content-Type is not application/json.</p>
                </section>

                <!-- Fraud Signals -->
                <section>
                    <h2>Fraud Signals</h2>
                    <p>The API checks for the following fraud indicators. These are heuristic flags, not hard blocks—high-value transactions can still be valid.</p>
                    <div class="field">
                        <strong>HIGH_VALUE</strong> [MEDIUM]<br>
                        Transaction amount exceeds $50,000
                    </div>
                    <div class="field">
                        <strong>EXCESSIVE_WITHDRAWAL</strong> [HIGH]<br>
                        Withdrawal exceeds daily limit of $100,000
                    </div>
                    <div class="field">
                        <strong>ROUND_AMOUNT</strong> [LOW]<br>
                        Round transaction amounts ($1000, $5000, etc.) occur less in real data
                    </div>
                </section>

                <!-- Error Codes -->
                <section>
                    <h2>Error Messages</h2>
                    <p>Common validation errors and their meanings:</p>
                    <div class="field">
                        <strong>"Missing required fields: ..."</strong><br>
                        One or more required fields are missing from the request.
                    </div>
                    <div class="field">
                        <strong>"Amount must be >= $0.01"</strong><br>
                        Amount is zero or negative.
                    </div>
                    <div class="field">
                        <strong>"Amount cannot exceed $999,999,999.99"</strong><br>
                        Amount is too large.
                    </div>
                    <div class="field">
                        <strong>"Transaction type must be one of: TRANSFER, PAYMENT, DEPOSIT, WITHDRAWAL"</strong><br>
                        Invalid transaction type. Check capitalization.
                    </div>
                    <div class="field">
                        <strong>"Account ID must be between 1 and 99,999"</strong><br>
                        Account ID is out of valid range.
                    </div>
                    <div class="field">
                        <strong>"Timestamp must be in ISO 8601 format"</strong><br>
                        Timestamp format is invalid. Use: <code>2024-05-18T14:30:00Z</code>
                    </div>
                </section>

                <!-- Best Practices -->
                <section>
                    <h2>Best Practices</h2>
                    <ul style="margin-left: 20px;">
                        <li><strong>Always use HTTPS</strong> when calling the API in production</li>
                        <li><strong>Validate timestamps</strong> on your client before sending—this API will reject transactions older than 90 days</li>
                        <li><strong>Handle fraud signals gracefully</strong>—don't auto-reject. Flag for manual review or require additional verification</li>
                        <li><strong>Retry on 5xx errors</strong> with exponential backoff, but not on 4xx errors</li>
                        <li><strong>Log transaction IDs</strong> for debugging and audit trails</li>
                    </ul>
                </section>
            </div>

            <footer>
                <p>Transaction Validator API v1.0 | Built with Flask | Deployed on Render</p>
            </footer>
        </div>
    </body>
    </html>
    """
    return html_content, 200, {"Content-Type": "text/html; charset=utf-8"}


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return error_response(
        "Endpoint not found. Try /docs for API documentation",
        status_code=404
    )


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors gracefully."""
    logger.error(f"Internal server error: {error}")
    return error_response(
        "Internal server error. Please try again later",
        status_code=500
    )


@app.before_request
def before_request():
    """Log all incoming requests."""
    logger.debug(f"Request: {request.method} {request.path}")


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s"
    )

    # Run app
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
