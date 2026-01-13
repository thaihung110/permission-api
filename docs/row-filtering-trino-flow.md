# Row Filtering Flow - Trino + OPA + Permission API + OpenFGA

## 🏗️ Architecture Overview

```
┌──────────┐      ┌─────────┐      ┌──────────────┐      ┌─────────┐
│  Trino   │ ───▶ │   OPA   │ ───▶ │ Permission   │ ───▶ │ OpenFGA │
│          │ ◀─── │         │ ◀─── │     API      │ ◀─── │         │
└──────────┘      └─────────┘      └──────────────┘      └─────────┘
     │                  │                   │                   │
     │                  │                   │                   │
  Query             Policy            Row Filter          Tuples with
Execution          Decision            Generator         User Attributes
```

---

## 📊 Complete Flow - Example với `customers.region`

### Setup (One-time Configuration)

**1. OpenFGA Tuples:**

```json
// Policy áp dụng cho table customers
{
  "user": "table:prod.public.customers",
  "relation": "applies_to",
  "object": "row_filter_policy:customers_region_filter"
}

// User sale_nam chỉ được xem region mien_bac
{
  "user": "user:sale_nam",
  "relation": "viewer",
  "object": "row_filter_policy:customers_region_filter",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "attribute_name": "region",
      "allowed_values": ["mien_bac"]
    }
  }
}

// User manager được xem nhiều regions
{
  "user": "user:manager",
  "relation": "viewer",
  "object": "row_filter_policy:customers_region_filter",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "attribute_name": "region",
      "allowed_values": ["mien_bac", "mien_trung", "mien_nam"]
    }
  }
}
```

**2. Column Mapping:**

Column name được infer từ policy_id theo naming convention:

- Policy ID: `customers_region_filter` → Column: `region`
- Format: `{table_name}_{column_name}_filter`

**Note:** Permission API không có database riêng, chỉ sử dụng OpenFGA để lưu trữ tất cả thông tin.

---

### Runtime Flow (User Query)

#### **Step 1: User Query in Trino**

User `sale_nam` executes query:

```sql
SELECT * FROM prod.public.customers;
```

#### **Step 2: Trino → OPA Request**

Trino's System Access Control gọi OPA để check permissions:

**Request to OPA:**

```json
{
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
}
```

#### **Step 3: OPA → Permission API Request**

OPA policy thực thi và gọi Permission API để lấy row filter:

**OPA Policy (Rego):**

```rego
package trino.authz

import future.keywords.if
import future.keywords.in

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

    filter := response.body.filter_expression
}

# Return row filter in response (Trino expects array of objects with "expression" field)
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

**Request to Permission API:**

```http
POST http://permission-api:8000/permissions/row-filter
Content-Type: application/json

{
  "user_id": "sale_nam",
  "resource": {
    "catalog_name": "prod",
    "schema_name": "public",
    "table_name": "customers"
  }
}
```

#### **Step 4: Permission API Processing**

Permission API thực hiện các bước sau:

**4.1. Get Policies for Table**

```python
# Query OpenFGA: Tìm policies áp dụng cho table
policies = await client.read_tuples(
    user="table:prod.public.customers",
    relation="applies_to"
)
# Result: ["customers_region_filter"]
```

**4.2. Get User's Allowed Values**

```python
# Query OpenFGA: Lấy allowed values của user cho policy
tuples = await client.read_tuples(
    user="user:sale_nam",
    relation="viewer",
    object="row_filter_policy:customers_region_filter"
)

# Extract from condition context
allowed_values = tuples[0].condition.context["allowed_values"]
# Result: ["mien_bac"]

attribute_name = tuples[0].condition.context["attribute_name"]
# Result: "region"
```

**4.3. Extract Column Name from Policy ID**

```python
# Parse column name from policy_id using naming convention
# Format: {table_name}_{column_name}_filter
policy_id = "customers_region_filter"
column_name = policy_id.replace("_filter", "").split("_")[-1]
# Result: column_name = "region"
```

**Note:** Condition context được OpenFGA lưu dưới dạng bytea (serialized), nhưng khi đọc qua SDK sẽ được deserialize về dạng JSON gốc.

**4.4. Build SQL Filter**

```python
# Build SQL WHERE clause
sql_filter = f"{config.column_name} IN ('{', '.join(allowed_values)}')"
# Result: "region IN ('mien_bac')"
```

**Response to OPA:**

```json
{
  "filter_expression": "region IN ('mien_bac')",
  "has_filter": true
}
```

#### **Step 5: OPA → Trino Response**

OPA trả về policy decision cho Trino:

**OPA Response:**

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

**Note:** Trino expects `rowFilters` as an array of objects, each with an `"expression"` field containing the SQL WHERE clause.

#### **Step 6: Trino Query Rewrite**

Trino nhận row filter và rewrite query:

**Original Query:**

```sql
SELECT * FROM prod.public.customers;
```

**Rewritten Query (Internal):**

```sql
SELECT * FROM prod.public.customers
WHERE region IN ('mien_bac');
```

**Result:** User chỉ thấy customers từ `mien_bac`

---

## 🔄 Sequence Diagram

```
┌─────────┐   ┌───────┐   ┌──────────────┐   ┌─────────┐
│  User   │   │ Trino │   │     OPA      │   │ Perm API│   │ OpenFGA │
└────┬────┘   └───┬───┘   └──────┬───────┘   └────┬────┘   └────┬────┘
     │            │               │                │             │
     │ SELECT *   │               │                │             │
     │───────────▶│               │                │             │
     │            │               │                │             │
     │            │ Authorize?    │                │             │
     │            │──────────────▶│                │             │
     │            │               │                │             │
     │            │               │ Get row filter │             │
     │            │               │───────────────▶│             │
     │            │               │                │             │
     │            │               │                │ Query tuples│
     │            │               │                │────────────▶│
     │            │               │                │             │
     │            │               │                │ Return tuples
     │            │               │                │◀────────────│
     │            │               │                │             │
     │            │               │  Build SQL     │             │
     │            │               │  filter        │             │
     │            │               │                │             │
     │            │               │ region IN (...)│             │
     │            │               │◀───────────────│             │
     │            │               │                │             │
     │            │ Allow + Filter│                │             │
     │            │◀──────────────│                │             │
     │            │               │                │             │
     │  Execute   │               │                │             │
     │  with      │               │                │             │
     │  filter    │               │                │             │
     │            │               │                │             │
     │  Results   │               │                │             │
     │◀───────────│               │                │             │
     │            │               │                │             │
```

---

## 📝 Detailed Examples

### Example 1: User `sale_nam` (Single Region)

**Query:**

```sql
SELECT customer_id, name, region FROM prod.public.customers;
```

**Flow:**

1. Trino → OPA
2. OPA → Permission API: `{"user_id": "sale_nam", "resource": {...}}`
3. Permission API → OpenFGA: Query tuples
4. OpenFGA returns: `allowed_values: ["mien_bac"]`
5. Permission API builds: `region IN ('mien_bac')`
6. OPA → Trino: `{"rowFilters": [{"expression": "region IN ('mien_bac')"}]}`
7. Trino executes: `SELECT ... WHERE region IN ('mien_bac')`

**Result:**

```
customer_id | name      | region
------------|-----------|----------
1           | Nguyen A  | mien_bac
2           | Tran B    | mien_bac
```

---

### Example 2: User `manager` (Multiple Regions)

**Query:**

```sql
SELECT COUNT(*) FROM prod.public.customers;
```

**Flow:**

1. Permission API queries OpenFGA
2. Returns: `allowed_values: ["mien_bac", "mien_trung", "mien_nam"]`
3. Builds: `region IN ('mien_bac', 'mien_trung', 'mien_nam')`
4. Trino executes: `SELECT COUNT(*) WHERE region IN ('mien_bac', 'mien_trung', 'mien_nam')`

**Result:**

```
count
-----
150   (all customers from 3 regions)
```

---

### Example 3: User `admin` (Wildcard)

**Setup:**

```json
{
  "user": "user:admin",
  "relation": "viewer",
  "object": "row_filter_policy:customers_region_filter",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "attribute_name": "region",
      "allowed_values": ["*"] // Wildcard
    }
  }
}
```

**Flow:**

1. Permission API detects wildcard: `"*" in allowed_values`
2. Returns: `{"filter_expression": null}`
3. OPA → Trino: No row filter
4. Trino executes: `SELECT * FROM customers` (without WHERE clause)

**Result:** Admin sees ALL customers

---

### Example 4: Unauthorized User

**User `hacker` không có tuple nào**

**Flow:**

1. Permission API queries OpenFGA
2. No tuples found for user `hacker`
3. Returns: `{"filter_expression": "1=0"}`
4. Trino executes: `SELECT * WHERE 1=0`

**Result:** Empty result set (denied)

---

## 🔧 Implementation Details

### 1. Trino Configuration

**`config.properties`:**

```properties
http-server.authentication.type=OAUTH2
http-server.authentication.oauth2.issuer-url=https://keycloak/realms/master
access-control.name=opa
opa.policy.uri=http://opa:8181/v1/data/trino/authz
opa.policy.row-filters-enabled=true
```

### 2. OPA Configuration

**`config.yaml`:**

```yaml
services:
  permission_api:
    url: http://permission-api:8000

decision_logs:
  console: true
```

**Policy file:** `trino_authz.rego` (as shown above)

### 3. Permission API Configuration

**Environment Variables:**

```bash
OPENFGA_API_URL=http://openfga:8080
OPENFGA_STORE_ID=01ARZ3NDEKTSV4RRFFQ69G5FAV
OPENFGA_MODEL_ID=01ARZ3NDEKTSV4RRFFQ69G5FAV
```

**Note:** Permission API không có database riêng, chỉ sử dụng OpenFGA để lưu trữ và query tất cả thông tin về permissions và row filter policies.

---

## 🚀 Performance Considerations

### Caching Strategy

**1. Cache Row Filters in OPA**

```rego
# Cache for 5 minutes
filter := get_row_filter(input) with {
    "cache": {
        "ttl": 300
    }
}
```

**2. Cache Policy Queries in Permission API**

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
async def get_table_policies(table_fqn: str):
    # Cache policy queries from OpenFGA in memory
    ...
```

**3. OpenFGA Performance**

- Use proper indexes on tuples
- Enable OpenFGA caching
- Consider read replicas for high load

### Expected Performance

| Component                | Latency  | Notes         |
| ------------------------ | -------- | ------------- |
| Trino → OPA              | ~5ms     | Local network |
| OPA → Permission API     | ~10ms    | HTTP call     |
| Permission API → OpenFGA | ~15-30ms | Tuple queries |
| Total overhead           | ~30-45ms | Per query     |

**Optimization:** Row filter is applied ONCE per query, not per row.

---

## 🧪 Testing

### Manual Test

**1. Setup tuples:**

```bash
# Using OpenFGA CLI
fga tuple write \
  --user "table:prod.public.customers" \
  --relation "applies_to" \
  --object "row_filter_policy:customers_region_filter"

fga tuple write \
  --user "user:sale_nam" \
  --relation "viewer" \
  --object "row_filter_policy:customers_region_filter" \
  --condition '{"name": "has_attribute_access", "context": {"attribute_name": "region", "allowed_values": ["mien_bac"]}}'
```

**2. Test Permission API:**

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

# Expected response:
# {
#   "filter_expression": "region IN ('mien_bac')",
#   "has_filter": true
# }
```

**3. Test in Trino:**

```sql
-- As user sale_nam
SELECT region, COUNT(*)
FROM prod.public.customers
GROUP BY region;

-- Expected: Only mien_bac
region    | count
----------|------
mien_bac  | 50
```

---

## 📊 Monitoring & Debugging

### Logs to Check

**1. Trino Logs:**

```
INFO: Applying row filter for prod.public.customers: region IN ('mien_bac')
```

**2. OPA Logs:**

```json
{
  "level": "info",
  "msg": "Row filter decision",
  "user": "sale_nam",
  "table": "prod.public.customers",
  "filter": "region IN ('mien_bac')"
}
```

**3. Permission API Logs:**

```
INFO: Building row filter for user=sale_nam, table=prod.public.customers
INFO: Found policy: customers_region_filter
INFO: User allowed values: ['mien_bac']
INFO: Generated filter: region IN ('mien_bac')
```

### Debugging Steps

**Issue: Filter not applied**

1. Check OPA policy is loaded: `curl http://opa:8181/v1/data/trino/authz`
2. Check Permission API reachable: `curl http://permission-api:8000/health`
3. Verify OpenFGA tuples exist: `fga tuple read ...`
4. Check Trino config: `access-control.name=opa` and `opa.policy.row-filters-enabled=true`

**Issue: Wrong filter**

1. Check tuple condition context in OpenFGA (condition_context được deserialize từ bytea)
2. Verify column mapping from policy_id naming convention
3. Test Permission API endpoint directly
4. Review OPA decision logs
5. Verify condition context format: `{"attribute_name": "...", "allowed_values": [...]}`

---

## ✅ Summary

**Complete Flow:**

1. User queries Trino
2. Trino asks OPA for authorization
3. OPA calls Permission API for row filter
4. Permission API queries OpenFGA tuples
5. Permission API builds SQL filter from user's allowed values
6. OPA returns filter to Trino
7. Trino rewrites and executes query with filter

**Key Points:**

- ✅ Filter applied automatically by Trino
- ✅ User sees only authorized rows
- ✅ No application code changes needed
- ✅ Centralized permission management in OpenFGA
- ✅ Dynamic - no code deploy for permission updates

This architecture provides **transparent, scalable row-level security** for Trino! 🚀
