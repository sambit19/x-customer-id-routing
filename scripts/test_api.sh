#!/bin/bash
# Test script for X-Customer-ID routing

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get API endpoint from CloudFormation stack
STACK_NAME="${1:-x-customer-id-routing}"
REGION="${AWS_REGION:-us-east-1}"

echo -e "${YELLOW}Getting API endpoint from stack: ${STACK_NAME}${NC}"

API_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
    --output text)

if [ -z "$API_ENDPOINT" ]; then
    echo -e "${RED}Error: Could not get API endpoint. Is the stack deployed?${NC}"
    exit 1
fi

echo -e "${GREEN}API Endpoint: ${API_ENDPOINT}${NC}\n"

# Generate tokens for different customers
echo -e "${YELLOW}Generating test tokens...${NC}\n"

TOKEN_CUSTOMER1=$(python3 scripts/generate_token.py customer1 --name "Acme Corp" 2>/dev/null | grep -A1 "Token:" | tail -1)
TOKEN_CUSTOMER2=$(python3 scripts/generate_token.py customer2 --name "Beta Inc" 2>/dev/null | grep -A1 "Token:" | tail -1)

echo "=============================================="
echo -e "${YELLOW}Test 1: Request as customer1${NC}"
echo "=============================================="
echo ""
curl -s -H "Authorization: Bearer ${TOKEN_CUSTOMER1}" "${API_ENDPOINT}/test" | python3 -m json.tool
echo ""

echo "=============================================="
echo -e "${YELLOW}Test 2: Request as customer2${NC}"
echo "=============================================="
echo ""
curl -s -H "Authorization: Bearer ${TOKEN_CUSTOMER2}" "${API_ENDPOINT}/test" | python3 -m json.tool
echo ""

echo "=============================================="
echo -e "${YELLOW}Test 3: Request without token (should fail)${NC}"
echo "=============================================="
echo ""
curl -s "${API_ENDPOINT}/test" | python3 -m json.tool || echo '{"error": "Unauthorized"}'
echo ""

echo "=============================================="
echo -e "${GREEN}Tests completed!${NC}"
echo "=============================================="
