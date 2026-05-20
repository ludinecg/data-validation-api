#!/bin/bash

# Simple test script to validate the API locally
# Usage: bash test_api.sh
# or: chmod +x test_api.sh && ./test_api.sh

set -e

BASE_URL="http://localhost:5000"
PASSED=0
FAILED=0

echo "🧪 Testing Transaction Validator API..."
echo "Base URL: $BASE_URL"
echo ""

# Helper function to make requests and check responses
test_endpoint() {
    local method=$1
    local endpoint=$2
    local data=$3
    local expected_status=$4
    local test_name=$5

    echo -n "Testing: $test_name ... "

    if [ -z "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" -X $method "$BASE_URL$endpoint" \
            -H "Content-Type: application/json")
    else
        response=$(curl -s -w "\n%{http_code}" -X $method "$BASE_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi

    # Extract status code (last line) and body (everything else)
    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" = "$expected_status" ]; then
        echo "✅ PASSED (HTTP $http_code)"
        ((PASSED++))
    else
        echo "❌ FAILED (expected $expected_status, got $http_code)"
        echo "Response: $body"
        ((FAILED++))
    fi
}

# Test 1: Health check
test_endpoint "GET" "/health" "" "200" "GET /health"

# Test 2: Valid transaction
valid_txn='{
  "amount": 1234.56,
  "transaction_type": "TRANSFER",
  "account_id": 54321,
  "timestamp": "2024-05-18T14:30:00Z",
  "description": "Test transaction"
}'
test_endpoint "POST" "/validate/transaction" "$valid_txn" "200" "POST /validate/transaction (valid)"

# Test 3: Missing required field
missing_field='{
  "amount": 100.00,
  "transaction_type": "TRANSFER"
}'
test_endpoint "POST" "/validate/transaction" "$missing_field" "400" "POST /validate/transaction (missing field)"

# Test 4: Invalid amount (negative)
invalid_amount='{
  "amount": -50.00,
  "transaction_type": "TRANSFER",
  "account_id": 123,
  "timestamp": "2024-05-18T14:30:00Z"
}'
test_endpoint "POST" "/validate/transaction" "$invalid_amount" "400" "POST /validate/transaction (negative amount)"

# Test 5: Invalid transaction type
invalid_type='{
  "amount": 100.00,
  "transaction_type": "INVALID_TYPE",
  "account_id": 123,
  "timestamp": "2024-05-18T14:30:00Z"
}'
test_endpoint "POST" "/validate/transaction" "$invalid_type" "400" "POST /validate/transaction (invalid type)"

# Test 6: High-value transaction (should flag fraud signal)
high_value='{
  "amount": 75000.00,
  "transaction_type": "WITHDRAWAL",
  "account_id": 99999,
  "timestamp": "2024-05-18T14:30:00Z"
}'
test_endpoint "POST" "/validate/transaction" "$high_value" "200" "POST /validate/transaction (high-value, with fraud signal)"

# Test 7: Invalid timestamp format
invalid_ts='{
  "amount": 100.00,
  "transaction_type": "TRANSFER",
  "account_id": 123,
  "timestamp": "not-a-valid-timestamp"
}'
test_endpoint "POST" "/validate/transaction" "$invalid_ts" "400" "POST /validate/transaction (invalid timestamp)"

# Test 8: API docs
test_endpoint "GET" "/docs" "" "200" "GET /docs"

# Test 9: 404 error
test_endpoint "GET" "/nonexistent" "" "404" "GET /nonexistent (404 test)"

# Test 10: Wrong Content-Type (no header)
echo -n "Testing: POST without Content-Type ... "
response=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/validate/transaction" \
    -d '{"amount": 100}' 2>/dev/null | tail -n 1)
if [ "$response" = "415" ]; then
    echo "✅ PASSED (HTTP 415)"
    ((PASSED++))
else
    echo "❌ FAILED (expected 415, got $response)"
    ((FAILED++))
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test Results: $PASSED passed, $FAILED failed"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $FAILED -eq 0 ]; then
    echo "✅ All tests passed!"
    exit 0
else
    echo "❌ Some tests failed"
    exit 1
fi
