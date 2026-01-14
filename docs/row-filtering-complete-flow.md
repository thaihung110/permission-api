# Row Filtering - Complete Flow với Request/Response Format

## 📋 Tổng quan

Tài liệu này mô tả chi tiết flow row filtering từ khi user query Trino đến khi nhận kết quả, bao gồm format request/response ở từng bước.

---

## 🔄 Complete Flow Diagram

```
┌─────────────┐
│ User Query  │ SELECT * FROM lakekeeper_bronze.finance.user
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Trino → OPA                                         │
│ POST /v1/data/trino/allow                                  │
│ Request: Authorization check                                │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: OPA Policy Execution                                │
│ - Check permission                                           │
│ - Call Permission API for row filter                        │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: OPA → Permission API                                │
│ POST /permissions/row-filter                                 │
│ Request: Get row filter for user and table                   │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 4: Permission API → OpenFGA                            │
│ Read tuples: Get policies and user permissions              │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 5: Permission API Processing                           │
│ - Parse policies                                             │
│ - Extract allowed values from condition context              │
│ - Build SQL filter expression                                │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 6: Permission API → OPA Response                        │
│ Response: filter_expression                                  │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 7: OPA → Trino Response                                │
│ Response: allow + rowFilters                                 │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 8: Trino Query Execution                               │
│ Rewrite query with WHERE clause                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📝 Chi tiết từng bước

### Step 1: Trino → OPA Request

**Khi user query:**

```sql
SELECT name, phone_number, id, region
FROM lakekeeper_bronze.finance.user;
```

**Trino gửi request đến OPA:**

**Endpoint:** `POST /v1/data/trino/allow`

**Request Body:**

```json
{
  "input": {
    "context": {
      "identity": {
        "user": "hung",
        "groups": []
      },
      "softwareStack": {
        "trinoVersion": "467"
      }
    },
    "action": {
      "operation": "SelectFromColumns",
      "resource": {
        "table": {
          "catalogName": "lakekeeper_bronze",
          "schemaName": "finance",
          "tableName": "user",
          "columns": ["name", "phone_number", "id", "region"]
        }
      }
    }
  }
}
```

**Key Fields:**

- `context.identity.user`: User ID từ Trino authentication
- `action.operation`: Operation type (`SelectFromColumns` cho SELECT queries)
- `action.resource.table`: Table information (catalog, schema, table, columns)

---

### Step 2: OPA Policy Execution

**OPA Policy (Rego) thực thi:**

```rego
package trino.authz

import future.keywords.if
import future.keywords.in

default allow := false

# Allow select if has proper permissions
allow if {
    input.action.operation == "SelectFromColumns"
    # Check permission via Permission API
    permission_check := check_permission(input)
    permission_check.allowed == true
    # Get row filter
    rowFilter := get_row_filter(input)
}

# Check permission via Permission API
check_permission(input) := response {
    response := http.send({
        "method": "POST",
        "url": "http://permission-api:8000/api/v1/permissions/check",
        "headers": {"Content-Type": "application/json"},
        "body": {
            "user_id": input.context.identity.user,
            "operation": input.action.operation,
            "resource": {
                "catalog": input.action.resource.table.catalogName,
                "schema": input.action.resource.table.schemaName,
                "table": input.action.resource.table.tableName,
                "columns": input.action.resource.table.columns
            }
        }
    })
}

# Get row filter from Permission API
get_row_filter(input) := filter {
    response := http.send({
        "method": "POST",
        "url": "http://permission-api:8000/permissions/row-filter",
        "headers": {"Content-Type": "application/json"},
        "body": {
            "user_id": input.context.identity.user,
            "resource": {
                "catalog_name": input.action.resource.table.catalogName,
                "schema_name": input.action.resource.table.schemaName,
                "table_name": input.action.resource.table.tableName
            }
        }
    })

    # Permission API returns: {"filter_expression": "...", "has_filter": true}
    filter := response.body.filter_expression
    filter != null
}

# Return row filter in Trino's expected format
rowFilters contains {"expression": filter} if {
    input.action.operation == "SelectFromColumns"
    filter := get_row_filter(input)
    filter != null
}
```

**OPA thực hiện 2 HTTP calls:**

1. `POST /api/v1/permissions/check` - Check permission
2. `POST /permissions/row-filter` - Get row filter

---

### Step 3: OPA → Permission API (Row Filter Request)

**Endpoint:** `POST /permissions/row-filter`

**Request Body:**

```json
{
  "user_id": "hung",
  "resource": {
    "catalog_name": "lakekeeper_bronze",
    "schema_name": "finance",
    "table_name": "user"
  }
}
```

**Request Headers:**

```
Content-Type: application/json
```

**Log trong Permission API:**

```
[INFO] [ENDPOINT] Received row filter request:
  user=hung, resource={'catalog_name': 'lakekeeper_bronze', 'schema_name': 'finance', 'table_name': 'user'}
```

---

### Step 4: Permission API → OpenFGA (Query Tuples)

**Permission API thực hiện 2 queries đến OpenFGA:**

#### 4.1. Get Policies for Table

**Query:**

```python
tuples = await openfga.read_tuples(
    user="table:lakekeeper_bronze.finance.user",
    relation="applies_to"
)
```

**OpenFGA Response:**

```json
{
  "tuples": [
    {
      "key": {
        "user": "table:lakekeeper_bronze.finance.user",
        "relation": "applies_to",
        "object": "row_filter_policy:user_region_filter"
      },
      "timestamp": "2024-01-15T10:30:00Z"
    }
  ]
}
```

**Extract Policy IDs:**

```python
policy_ids = ["user_region_filter"]
```

#### 4.2. Get User's Permissions on Policies

**Query:**

```python
tuples = await openfga.read_tuples(
    user="user:hung",
    relation="viewer",
    object_id="row_filter_policy:user_region_filter"
)
```

**OpenFGA Response:**

```json
{
  "tuples": [
    {
      "key": {
        "user": "user:hung",
        "relation": "viewer",
        "object": "row_filter_policy:user_region_filter"
      },
      "condition": {
        "name": "has_attribute_access",
        "context": {
          "attribute_name": "region",
          "allowed_values": ["north"]
        }
      },
      "timestamp": "2024-01-15T10:30:00Z"
    }
  ]
}
```

**Note:** Condition context được OpenFGA lưu dưới dạng bytea (serialized), nhưng SDK tự động deserialize về JSON khi đọc.

---

### Step 5: Permission API Processing

**Permission API xử lý:**

#### 5.1. Parse Column Name from Policy ID

```python
# Policy ID: user_region_filter
# Format: {table_name}_{column_name}_filter
policy_id = "user_region_filter"
parts = policy_id.replace("_filter", "").split("_")
column_name = parts[-1]  # "region"
```

#### 5.2. Extract Allowed Values from Condition Context

```python
# From OpenFGA tuple condition context
condition_context = {
    "attribute_name": "region",
    "allowed_values": ["north"]
}

attribute_name = condition_context["attribute_name"]  # "region"
allowed_values = condition_context["allowed_values"]  # ["north"]
```

#### 5.3. Build SQL Filter Expression

```python
# Check for wildcard
if "*" in allowed_values:
    filter_sql = None  # No filter
else:
    # Escape SQL values
    escaped_values = [escape_sql_value(v) for v in allowed_values]
    values_str = "', '".join(escaped_values)
    filter_sql = f"{column_name} IN ('{values_str}')"
    # Result: "region IN ('north')"
```

**Special Cases:**

- **Wildcard (`*`)**: Return `null` (no filter)
- **No permission**: Return `"1=0"` (deny all)
- **Multiple policies**: Combine with `AND` logic

---

### Step 6: Permission API → OPA Response

**Endpoint Response:** `POST /permissions/row-filter`

**Response Body:**

```json
{
  "filter_expression": "region IN ('north')",
  "has_filter": true
}
```

**Response Headers:**

```
Content-Type: application/json
```

**Log trong Permission API:**

```
[INFO] [ENDPOINT] Returning row filter:
  user=hung, table=lakekeeper_bronze.finance.user,
  filter=region IN ('north'), has_filter=True
```

**Response Format Details:**

| Field               | Type             | Description                                                             |
| ------------------- | ---------------- | ----------------------------------------------------------------------- |
| `filter_expression` | `string \| null` | SQL WHERE clause (e.g., `"region IN ('north')"`) or `null` if no filter |
| `has_filter`        | `boolean`        | `true` if filter exists, `false` if no filter needed                    |

**Special Response Cases:**

1. **No Filter (Wildcard or No Policies):**

```json
{
  "filter_expression": null,
  "has_filter": false
}
```

2. **Deny All (Unauthorized):**

```json
{
  "filter_expression": "1=0",
  "has_filter": true
}
```

3. **Multiple Filters (AND logic):**

```json
{
  "filter_expression": "region IN ('north') AND department IN ('sales')",
  "has_filter": true
}
```

---

### Step 7: OPA → Trino Response

**OPA trả về policy decision cho Trino:**

**Response Body:**

```json
{
  "result": {
    "allow": true,
    "rowFilters": [
      {
        "expression": "region IN ('north')"
      }
    ]
  }
}
```

**Response Format Details:**

| Field                            | Type      | Description                            |
| -------------------------------- | --------- | -------------------------------------- |
| `result.allow`                   | `boolean` | `true` if query is allowed             |
| `result.rowFilters`              | `array`   | Array of filter objects (can be empty) |
| `result.rowFilters[].expression` | `string`  | SQL WHERE clause                       |

**Special Response Cases:**

1. **No Filter:**

```json
{
  "result": {
    "allow": true,
    "rowFilters": []
  }
}
```

2. **Denied:**

```json
{
  "result": {
    "allow": false
  }
}
```

3. **Multiple Filters (combined by Permission API):**

```json
{
  "result": {
    "allow": true,
    "rowFilters": [
      {
        "expression": "region IN ('north') AND department IN ('sales')"
      }
    ]
  }
}
```

**Note:** Trino expects `rowFilters` as an **array** of objects, each with an `"expression"` field. Multiple filters are combined into a single expression by Permission API.

---

### Step 8: Trino Query Execution

**Trino nhận response từ OPA và rewrite query:**

**Original Query:**

```sql
SELECT name, phone_number, id, region
FROM lakekeeper_bronze.finance.user;
```

**Rewritten Query (Internal):**

```sql
SELECT name, phone_number, id, region
FROM lakekeeper_bronze.finance.user
WHERE region IN ('north');
```

**Trino Log:**

```
[INFO] Applying row filter for lakekeeper_bronze.finance.user: region IN ('north')
```

**Result Set:**

```
name      | phone_number | id | region
----------|--------------|----|-------
Nguyen A  | 0912345678   | 1  | north
Tran B    | 0987654321   | 2  | north
```

**User chỉ thấy rows có `region = 'north'`**

---

## 🔍 Complete Example với Request/Response

### Scenario: User `hung` query table `user` với row filter `region = 'north'`

#### 1. User Query

```sql
SELECT * FROM lakekeeper_bronze.finance.user;
```

#### 2. Trino → OPA Request

```http
POST /v1/data/trino/allow
Content-Type: application/json

{
  "input": {
    "context": {
      "identity": {
        "user": "hung",
        "groups": []
      },
      "softwareStack": {
        "trinoVersion": "467"
      }
    },
    "action": {
      "operation": "SelectFromColumns",
      "resource": {
        "table": {
          "catalogName": "lakekeeper_bronze",
          "schemaName": "finance",
          "tableName": "user",
          "columns": ["name", "phone_number", "id", "region"]
        }
      }
    }
  }
}
```

#### 3. OPA → Permission API Request (Row Filter)

```http
POST /permissions/row-filter
Content-Type: application/json

{
  "user_id": "hung",
  "resource": {
    "catalog_name": "lakekeeper_bronze",
    "schema_name": "finance",
    "table_name": "user"
  }
}
```

#### 4. Permission API → OpenFGA Query

```python
# Query 1: Get policies
read_tuples(
    user="table:lakekeeper_bronze.finance.user",
    relation="applies_to"
)
# Returns: [{"object": "row_filter_policy:user_region_filter"}]

# Query 2: Get user permissions
read_tuples(
    user="user:hung",
    relation="viewer",
    object_id="row_filter_policy:user_region_filter"
)
# Returns: [{
#   "condition": {
#     "name": "has_attribute_access",
#     "context": {
#       "attribute_name": "region",
#       "allowed_values": ["north"]
#     }
#   }
# }]
```

#### 5. Permission API → OPA Response

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "filter_expression": "region IN ('north')",
  "has_filter": true
}
```

#### 6. OPA → Trino Response

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "result": {
    "allow": true,
    "rowFilters": [
      {
        "expression": "region IN ('north')"
      }
    ]
  }
}
```

#### 7. Trino Query Execution

```sql
-- Rewritten query
SELECT * FROM lakekeeper_bronze.finance.user
WHERE region IN ('north');
```

#### 8. Result

```
name      | phone_number | id | region
----------|--------------|----|-------
Nguyen A  | 0912345678   | 1  | north
Tran B    | 0987654321   | 2  | north
```

---

## 🧪 Testing Flow

### Test 1: Direct Permission API Call

```bash
curl -X POST http://localhost:8000/permissions/row-filter \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "user"
    }
  }'
```

**Expected Response:**

```json
{
  "filter_expression": "region IN ('north')",
  "has_filter": true
}
```

### Test 2: Check OPA Policy

```bash
curl -X POST http://localhost:8181/v1/data/trino/allow \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "context": {
        "identity": {
          "user": "hung",
          "groups": []
        }
      },
      "action": {
        "operation": "SelectFromColumns",
        "resource": {
          "table": {
            "catalogName": "lakekeeper_bronze",
            "schemaName": "finance",
            "tableName": "user",
            "columns": ["name", "phone_number", "id", "region"]
          }
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
        "expression": "region IN ('north')"
      }
    ]
  }
}
```

### Test 3: Query in Trino

```sql
-- As user 'hung'
SELECT * FROM lakekeeper_bronze.finance.user;

-- Expected: Only rows with region = 'north'
```

---

## 📊 Flow Summary Table

| Step | From           | To             | Endpoint/Method                | Key Data                     |
| ---- | -------------- | -------------- | ------------------------------ | ---------------------------- |
| 1    | User           | Trino          | SQL Query                      | `SELECT * FROM ...`          |
| 2    | Trino          | OPA            | `POST /v1/data/trino/allow`    | Authorization request        |
| 3    | OPA            | Permission API | `POST /permissions/row-filter` | Row filter request           |
| 4    | Permission API | OpenFGA        | `read_tuples()`                | Query policies & permissions |
| 5    | Permission API | -              | Processing                     | Build SQL filter             |
| 6    | Permission API | OPA            | Response                       | `filter_expression`          |
| 7    | OPA            | Trino          | Response                       | `allow` + `rowFilters`       |
| 8    | Trino          | User           | Query Result                   | Filtered rows                |

---

## ✅ Key Points

1. **Row filtering là transparent**: User không biết filter được áp dụng
2. **Filter được build từ OpenFGA tuples**: Condition context chứa `allowed_values`
3. **Trino tự động rewrite query**: Thêm WHERE clause từ `rowFilters`
4. **Multiple policies**: Combined với AND logic
5. **Wildcard support**: `["*"]` = no filter (full access)
6. **Fail closed**: No permission → `"1=0"` (deny all)

---

## 📚 Related Documentation

- `docs/row-filtering-trino-flow.md` - Flow tổng quan
- `docs/row-filtering-grant-fix.md` - Cách grant với condition context
- `docs/condition-context-grant-guide.md` - Hướng dẫn grant
- `docs/row-filtering-final-design.md` - Design chi tiết
