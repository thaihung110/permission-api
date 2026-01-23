#!/bin/sh
set -e

OPENFGA_URL="http://openfga-2:8080"

# Create store
STORE_RESPONSE=$(curl -s -X POST "${OPENFGA_URL}/stores" \
  -H "Content-Type: application/json" \
  -d '{"name": "permission-store"}')

STORE_ID=$(echo $STORE_RESPONSE | jq -r '.id')
echo "Created store: $STORE_ID"

# Write authorization model
curl -s -X POST "${OPENFGA_URL}/stores/${STORE_ID}/authorization-models" \
  -H "Content-Type: application/json" \
  -d @/model.json

echo "Model loaded successfully!"