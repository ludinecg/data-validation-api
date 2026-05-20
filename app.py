"""
Transaction Validator API - Financial transaction validation service.
Validates transaction structure, detects fraud signals, returns risk scores.
"""

from flask import Flask, request
from flask_restx import Api, Resource, fields, Namespace
from datetime import datetime, timedelta
import logging
import os

app = Flask(__name__)

# Flask-RESTX Configuration (Swagger)
app.config['RESTX_MASK_SWAGGER'] = False
api = Api(
    app,
    version='1.0.0',
    title='Transaction Validator API',
    description='Real-time financial transaction validation with fraud detection.',
    doc='/docs',
    prefix=''
)

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
# Response Models for Swagger Documentation
# ============================================================================

fraud_signal_model = api.model('FraudSignal', {
    'type': fields.String(required=True, description='Signal type (HIGH_VALUE, EXCESSIVE_WITHDRAWAL, ROUND_AMOUNT)'),
    'severity': fields.String(required=True, description='LOW, MEDIUM, or HIGH'),
    'message': fields.String(required=True, description='Human-readable signal description')
})

transaction_request_model = api.model('TransactionRequest', {
    'amount': fields.Float(required=True, description='Transaction amount ($0.01 - $999,999,999.99)'),
    'transaction_type': fields.String(required=True, description='TRANSFER, PAYMENT, DEPOSIT, or WITHDRAWAL'),
    'account_id': fields.Integer(required=True, description='Account ID (1 - 99,999)'),
    'timestamp': fields.String(required=True, description='ISO 8601 timestamp (e.g., 2024-05-20T14:30:00)'),
    'description': fields.String(required=False, description='Optional transaction description (max 500 chars)')
})

transaction_response_model = api.model('TransactionResponse', {
    'transaction_id': fields.String(required=True, description='Unique transaction ID'),
    'is_valid': fields.Boolean(required=True, description='Transaction passed validation'),
    'amount': fields.Float(required=True, description='Transaction amount'),
    'transaction_type': fields.String(required=True, description='Transaction type'),
    'account_id': fields.Integer(required=True, description='Account ID'),
    'fraud_signals': fields.List(fields.Nested(fraud_signal_model), required=True, description='Array of fraud signals'),
    'risk_score': fields.Integer(required=True, description='Risk score (0 = clean, 100+ = very suspicious)')
})

error_response_model = api.model('ErrorResponse', {
    'status': fields.String(required=True, description='error'),
    'message': fields.String(required=True, description='Error message'),
    'errors': fields.List(fields.String(), required=False, description='List of validation errors'),
    'timestamp': fields.String(required=True, description='Response timestamp')
})

health_response_model = api.model('HealthResponse', {
    'service': fields.String(required=True, description='Service name'),
    'status': fields.String(required=True, description='healthy')
})


# ============================================================================
# Validation Functions
# ============================================================================

def validate_transaction_payload(payload: dict) -> tuple:
    """
    Validate the transaction payload structure and values.

    Returns:
        Tuple of (is_valid: bool, errors: list)
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
        errors.append("Timestamp must be in ISO 8601 format (e.g., 2024-05-20T14:30:00)")

    # Validate optional fields if present
    if "description" in payload:
        desc = payload.get("description", "")
        if not isinstance(desc, str):
            errors.append("Description must be a string")
        elif len(desc) > 500:
            errors.append("Description cannot exceed 500 characters")

    return len(errors) == 0, errors


def check_fraud_signals(payload: dict) -> dict:
    """
    Check for potential fraud signals. These are heuristic flags, not hard blocks.

    Returns:
        Dict with fraud signals detected and risk score
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

    # Signal 2: Excessive withdrawal beyond daily limit
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
# API Namespaces
# ============================================================================

health_ns = api.namespace('', description='Service health')
validate_ns = api.namespace('', description='Transaction validation')


@health_ns.route('/health')
class HealthCheck(Resource):
    """Service health check endpoint"""

    @api.marshal_with(health_response_model)
    def get(self):
        """Check if service is running"""
        return {
            "service": "transaction-validator",
            "status": "healthy"
        }, 200


@validate_ns.route('/validate/transaction')
class ValidateTransaction(Resource):
    """Transaction validation endpoint"""

    @api.expect(transaction_request_model)
    @api.marshal_with(transaction_response_model)
    @api.response(400, 'Validation failed', error_response_model)
    @api.response(415, 'Invalid Content-Type', error_response_model)
    def post(self):
        """Validate a financial transaction and detect fraud signals"""

        # Check content type
        if not request.is_json:
            api.abort(415, 'Content-Type must be application/json')

        payload = request.get_json()

        # Log incoming request
        logger.info(f"POST /validate/transaction | Client: {request.remote_addr} | Body: {payload}")

        # Validate payload structure & values
        is_valid, validation_errors = validate_transaction_payload(payload)
        if not is_valid:
            logger.warning(f"Validation failed: {validation_errors}")
            api.abort(400, 'Transaction validation failed', errors=validation_errors)

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
        return response_data, 200


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(400)
def bad_request(error):
    """Handle 400 Bad Request errors"""
    return {
        "status": "error",
        "message": "Bad request",
        "timestamp": datetime.utcnow().isoformat()
    }, 400


@app.errorhandler(404)
def not_found(error):
    """Handle 404 Not Found errors"""
    return {
        "status": "error",
        "message": "Endpoint not found",
        "timestamp": datetime.utcnow().isoformat()
    }, 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 Internal Server errors"""
    logger.error(f"Internal server error: {error}")
    return {
        "status": "error",
        "message": "Internal server error",
        "timestamp": datetime.utcnow().isoformat()
    }, 500


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
