# Trino Row Filtering Configuration

## 📋 Overview

This document describes how to configure Trino to use row filtering with OPA and Permission API. Row filtering allows Trino to automatically apply WHERE clauses to queries based on user permissions stored in OpenFGA.

---

## 🔧 Trino Configuration

### 1. Access Control Configuration

Edit `etc/config.properties`:

```properties
# Enable OPA access control
access-control.name=opa

# OPA endpoint for authorization decisions
opa.policy.uri=http://opa:8181/v1/data/trino/authz

# Enable row filtering
opa.policy.row-filters-enabled=true

# Optional: Row filters endpoint (if different from main policy URI)
# opa.policy.row-filters-uri=http://opa:8181/v1/data/trino/authz
```

### 2. Authentication Configuration

```properties
# Example: OAuth2 authentication
http-server.authentication.type=OAUTH2
http-server.authentication.oauth2.issuer-url=https://keycloak/realms/master
http-server.authentication.oauth2.client-id=trino
http-server.authentication.oauth2.client-secret=your-secret

# Or use other authentication methods:
# http-server.authentication.type=PASSWORD
# http-server.authentication.type=KERBEROS
```

### 3. OPA Configuration

Create `etc/opa/config.yaml`:

```yaml
services:
  permission_api:
    url: http://permission-api:8000
    timeout: 5s

decision_logs:
  console: true

bundles:
  trino:
    resource: /bundles/trino/bundle.tar.gz
    polling:
      min_delay_seconds: 10
      max_delay_seconds: 60
```

### 4. OPA Policy File

Create `policies/trino/authz.rego`:

```rego
package trino.authz

import future.keywords.if
import future.keywords.in
import future.keywords.contains

default allow := false

# Allow select if has proper permissions
allow if {
    input.action.operation == "SelectFromColumns"
    rowFilter := get_row_filter(input)
}

# Get row filter from Permission API
get_row_filter(input) := filter {
    table_fqn := sprintf("%s.%s.%s", [
        input.resource.table.catalogName,
        input.resource.table.schemaName,
        input.resource.table.tableName
    ])

    response := http.send({
        "method": "POST",
        "url": "http://permission-api:8000/permissions/row-filter",
        "headers": {"Content-Type": "application/json"},
        "body": {
            "user_id": input.context.identity.user,
            "resource": {
                "catalog_name": input.resource.table.catalogName,
                "schema_name": input.resource.table.schemaName,
                "table_name": input.resource.table.tableName
            }
        }
    })

    # Permission API returns: {"filter_expression": "...", "has_filter": true}
    filter := response.body.filter_expression
    filter != null
}

# Return row filter in Trino's expected format
# Trino expects: array of objects with "expression" field
rowFilters contains {"expression": filter} if {
    input.action.operation == "SelectFromColumns"
    table_fqn := sprintf("%s.%s.%s", [
        input.resource.table.catalogName,
        input.resource.table.schemaName,
        input.resource.table.tableName
    ])
    filter := get_row_filter(input)
    filter != null
}
```

**Key Points:**

- Trino expects `rowFilters` as an **array** of objects
- Each object must have an `"expression"` field containing the SQL WHERE clause
- Multiple filters are combined with AND logic
- If `filter_expression` is `null`, no filter is applied

---

## 📊 Response Format

### Permission API Response

```json
{
  "filter_expression": "region IN ('mien_bac')",
  "has_filter": true
}
```

### OPA Response to Trino

```json
{
  "result": {
    "allow": true,
    "rowFilters": [
      {
        "expression": "region IN ('mien_bac')"
      }
    ]
  }
}
```

### Multiple Filters Example

If a table has multiple policies (e.g., region AND department):

**Permission API Response:**

```json
{
  "filter_expression": "region IN ('mien_bac') AND department IN ('sales')",
  "has_filter": true
}
```

**OPA Response:**

```json
{
  "result": {
    "allow": true,
    "rowFilters": [
      {
        "expression": "region IN ('mien_bac') AND department IN ('sales')"
      }
    ]
  }
}
```

**Note:** Permission API combines multiple filters with AND logic before returning. OPA returns a single expression in the array.

---

## 🚀 Docker Compose Example

```yaml
version: "3.8"

services:
  trino:
    image: trinodb/trino:latest
    ports:
      - "8080:8080"
    volumes:
      - ./etc:/etc/trino
      - ./policies:/policies
    environment:
      - TRINO_ENV=production
    depends_on:
      - opa
      - permission-api

  opa:
    image: openpolicyagent/opa:latest
    ports:
      - "8181:8181"
    command:
      - "run"
      - "--server"
      - "--config-file=/config/config.yaml"
      - "/policies"
    volumes:
      - ./opa/config.yaml:/config/config.yaml
      - ./policies:/policies

  permission-api:
    image: permission-api:latest
    ports:
      - "8000:8000"
    environment:
      - OPENFGA_API_URL=http://openfga:8080
      - OPENFGA_STORE_ID=${OPENFGA_STORE_ID}
    depends_on:
      - openfga

  openfga:
    image: openfga/openfga:latest
    ports:
      - "8080:8080"
    environment:
      - OPENFGA_DATASTORE_ENGINE=postgres
      - OPENFGA_DATASTORE_URI=postgres://user:pass@postgres:5432/openfga
    depends_on:
      - postgres

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=openfga
```

---

## ✅ Verification Steps

### 1. Test Permission API

```bash
curl -X POST http://localhost:8000/permissions/row-filter \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "sale_nam",
    "resource": {
      "catalog_name": "prod",
      "schema_name": "public",
      "table_name": "customers"
    }
  }'
```

**Expected Response:**

```json
{
  "filter_expression": "region IN ('mien_bac')",
  "has_filter": true
}
```

### 2. Test OPA Policy

```bash
curl -X POST http://localhost:8181/v1/data/trino/authz \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "action": {
        "operation": "SelectFromColumns"
      },
      "resource": {
        "table": {
          "catalogName": "prod",
          "schemaName": "public",
          "tableName": "customers"
        }
      },
      "context": {
        "identity": {
          "user": "sale_nam"
        }
      }
    }
  }'
```

**Expected Response:**

```json
{
  "result": {
    "allow": true,
    "rowFilters": [
      {
        "expression": "region IN ('mien_bac')"
      }
    ]
  }
}
```

### 3. Test in Trino

```sql
-- Connect as user sale_nam
SELECT * FROM prod.public.customers;

-- Trino automatically rewrites to:
-- SELECT * FROM prod.public.customers WHERE region IN ('mien_bac')
```

---

## 🔍 Troubleshooting

### Issue: Row filter not applied

**Check:**

1. Trino config: `opa.policy.row-filters-enabled=true`
2. OPA policy returns `rowFilters` array
3. Permission API returns valid `filter_expression`
4. OpenFGA tuples exist with correct condition context

**Debug:**

```bash
# Check Trino logs
docker logs trino | grep -i "row filter"

# Check OPA decision logs
docker logs opa | grep -i "rowFilter"

# Check Permission API logs
docker logs permission-api | grep -i "row filter"
```

### Issue: Wrong filter expression

**Check:**

1. OpenFGA condition context format:
   ```json
   {
     "attribute_name": "region",
     "allowed_values": ["mien_bac"]
   }
   ```
2. Policy ID naming convention: `{table}_{column}_filter`
3. Permission API correctly parses condition context from OpenFGA

### Issue: Multiple filters not working

**Note:** Permission API combines multiple filters with AND logic in a single expression. OPA returns one object in the array.

If you need separate filters, modify Permission API to return multiple expressions, then update OPA policy:

```rego
# Multiple separate filters
rowFilters contains {"expression": filter} if {
    input.action.operation == "SelectFromColumns"
    filters := get_all_filters(input)  # Returns array
    filter := filters[_]
}
```

---

## 📝 Configuration Checklist

- [ ] Trino `config.properties` configured with OPA access control
- [ ] `opa.policy.row-filters-enabled=true` set
- [ ] OPA policy file created with correct format
- [ ] Permission API endpoint accessible from OPA
- [ ] OpenFGA tuples created with condition context
- [ ] Test queries return filtered results
- [ ] Logs show row filters being applied

---

## 🎯 Summary

**Key Configuration Points:**

1. **Trino**: Enable OPA access control and row filtering
2. **OPA**: Policy must return `rowFilters` as array of objects with `"expression"` field
3. **Permission API**: Returns `filter_expression` (SQL WHERE clause)
4. **OpenFGA**: Stores condition context as bytea, deserialized by SDK

**Flow:**

```
Trino → OPA → Permission API → OpenFGA
         ↓
    rowFilters array
         ↓
    Trino applies WHERE clause
```

This configuration provides **transparent, automatic row-level security** for Trino! 🚀
