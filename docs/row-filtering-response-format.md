# Row Filtering Response Format Verification

## 📋 Overview

This document verifies that the Permission API response format matches Trino's expected format through OPA.

---

## 🔄 Response Flow

### 1. Permission API Response

**Endpoint:** `POST /permissions/row-filter`

**Request:**

```json
{
  "user_id": "sale_nam",
  "resource": {
    "catalog_name": "prod",
    "schema_name": "public",
    "table_name": "customers"
  }
}
```

**Response:**

```json
{
  "filter_expression": "region IN ('mien_bac')",
  "has_filter": true
}
```

**Key Fields:**

- `filter_expression`: SQL WHERE clause (string or null)
- `has_filter`: Boolean indicating if filter exists

**Special Cases:**

- No filter (wildcard or no policies): `{"filter_expression": null, "has_filter": false}`
- Deny all (unauthorized): `{"filter_expression": "1=0", "has_filter": true}`

---

### 2. OPA Policy Processing

**OPA Policy extracts `filter_expression` from Permission API response:**

```rego
get_row_filter(input) := filter {
    response := http.send({
        "method": "POST",
        "url": "http://permission-api:8000/permissions/row-filter",
        ...
    })

    filter := response.body.filter_expression
}
```

**Then wraps in Trino format:**

```rego
rowFilters contains {"expression": filter} if {
    filter := get_row_filter(input)
    filter != null
}
```

---

### 3. OPA Response to Trino

**Format:** Array of objects with `"expression"` field

**Single Filter:**

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

**Multiple Filters (combined by Permission API):**

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

**No Filter (wildcard):**

```json
{
  "result": {
    "allow": true,
    "rowFilters": []
  }
}
```

**Deny All:**

```json
{
  "result": {
    "allow": false,
    "rowFilters": []
  }
}
```

---

## ✅ Format Verification

### Permission API → OPA

| Permission API Response                                        | OPA Processing              | Result                            |
| -------------------------------------------------------------- | --------------------------- | --------------------------------- |
| `{"filter_expression": "region IN (...)", "has_filter": true}` | Extract `filter_expression` | `filter = "region IN (...)"`      |
| `{"filter_expression": null, "has_filter": false}`             | `filter = null`             | `rowFilters = []` (empty)         |
| `{"filter_expression": "1=0", "has_filter": true}`             | Extract `filter_expression` | `filter = "1=0"`, `allow = false` |

### OPA → Trino

| OPA `rowFilters`                      | Trino Behavior                 |
| ------------------------------------- | ------------------------------ |
| `[{"expression": "region IN (...)"}]` | Applies WHERE clause           |
| `[]` (empty array)                    | No filter applied              |
| Multiple objects                      | All expressions combined (AND) |

---

## 🔍 Testing

### Test 1: Single Filter

**Permission API:**

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

**OPA Response to Trino:**

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

**Trino Query Rewrite:**

```sql
-- Original: SELECT * FROM prod.public.customers
-- Rewritten: SELECT * FROM prod.public.customers WHERE region IN ('mien_bac')
```

---

### Test 2: No Filter (Wildcard)

**Permission API Response:**

```json
{
  "filter_expression": null,
  "has_filter": false
}
```

**OPA Response:**

```json
{
  "result": {
    "allow": true,
    "rowFilters": []
  }
}
```

**Trino:** No WHERE clause added

---

### Test 3: Deny All (Unauthorized)

**Permission API Response:**

```json
{
  "filter_expression": "1=0",
  "has_filter": true
}
```

**OPA Response:**

```json
{
  "result": {
    "allow": false,
    "rowFilters": []
  }
}
```

**Trino:** Query denied

---

## 📝 Summary

**Format Chain:**

```
Permission API          OPA Policy           Trino
─────────────────────────────────────────────────────
filter_expression  →   expression field  →  WHERE clause
(string or null)       (in array)           (applied)
```

**Key Points:**

1. ✅ Permission API returns `filter_expression` (string or null)
2. ✅ OPA extracts and wraps in `{"expression": "..."}` format
3. ✅ OPA returns `rowFilters` as array of objects
4. ✅ Trino expects array format and applies expressions as WHERE clauses
5. ✅ Multiple filters combined by Permission API (AND logic)
6. ✅ Null filter = empty array = no WHERE clause

**All formats match correctly!** ✅
