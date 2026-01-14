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

// User hung chỉ được xem region mien_bac
{
  "user": "user:hung",
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
# Request: Read all tuples where table is user and relation is "applies_to"
tuples = await openfga.read_tuples(
    user="table:prod.public.customers",
    relation="applies_to"
)
# OpenFGA SDK sẽ tự động thêm pattern "row_filter_policy:" vào object filter

# Parse policy IDs from response
policy_ids = []
for tuple_item in tuples:
    object_id = tuple_item.key.object  # e.g., "row_filter_policy:customers_region_filter"
    if object_id.startswith("row_filter_policy:"):
        policy_id = object_id.replace("row_filter_policy:", "")
        policy_ids.append(policy_id)

# Result: policy_ids = ["customers_region_filter"]
```

**OpenFGA Request/Response:**

```http
# Request to OpenFGA (via SDK)
POST /stores/{store_id}/read
{
  "tuple_key": {
    "user": "table:prod.public.customers",
    "relation": "applies_to",
    "object": "row_filter_policy:"  # Pattern matching
  }
}

# Response from OpenFGA
{
  "tuples": [
    {
      "key": {
        "user": "table:prod.public.customers",
        "relation": "applies_to",
        "object": "row_filter_policy:customers_region_filter"
      }
    }
  ]
}
```

**4.2. Get User's Allowed Values (Loop per Policy)**

```python
# Loop qua từng policy để lấy allowed values của user
filters = []

for policy_id in policy_ids:  # ["customers_region_filter"]
    # Query OpenFGA: Lấy tuple của user cho từng policy
    tuples = await openfga.read_tuples(
        user="user:sale_nam",
        relation="viewer",
        object_id=f"row_filter_policy:{policy_id}"
    )

    if not tuples:
        # User không có access đến policy này
        # Permission API sẽ fail closed - deny all
        continue

    # Extract condition context từ tuple
    tuple_item = tuples[0]
    condition = tuple_item.key.condition
    ctx = condition.context  # SDK tự động deserialize từ bytea

    # Parse context (có thể là dict hoặc object)
    if isinstance(ctx, dict):
        attribute_name = ctx["attribute_name"]  # "region"
        allowed_values = ctx["allowed_values"]  # ["mien_bac"]
    else:
        # Access as object attributes
        attribute_name = ctx.attribute_name
        allowed_values = ctx.allowed_values

    # Parse column name from policy_id
    column_name = parse_column_from_policy_id(policy_id)  # "region"

    filters.append({
        "policy_id": policy_id,
        "attribute_name": attribute_name,
        "column_name": column_name,
        "allowed_values": allowed_values
    })

# Result: filters = [
#   {
#     "policy_id": "customers_region_filter",
#     "attribute_name": "region",
#     "column_name": "region",
#     "allowed_values": ["mien_bac"]
#   }
# ]
```

**OpenFGA Request/Response:**

```http
# Request to OpenFGA (via SDK)
POST /stores/{store_id}/read
{
  "tuple_key": {
    "user": "user:sale_nam",
    "relation": "viewer",
    "object": "row_filter_policy:customers_region_filter"
  }
}

# Response from OpenFGA
{
  "tuples": [
    {
      "key": {
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
    }
  ]
}
```

**Note:** Condition context được OpenFGA lưu dưới dạng bytea (serialized), nhưng khi đọc qua SDK sẽ được deserialize về dạng JSON gốc.

**4.3. Extract Column Name from Policy ID**

```python
# Function to parse column name from policy_id using naming convention
# Format: {table_name}_{column_name}_filter
def parse_column_from_policy_id(policy_id: str) -> str:
    # Remove "_filter" suffix and get last part
    parts = policy_id.replace("_filter", "").split("_")
    return parts[-1]  # Last part is column name

# Example:
policy_id = "customers_region_filter"
column_name = parse_column_from_policy_id(policy_id)
# Result: column_name = "region"
```

**4.4. Build SQL Filter**

```python
# Security check: User phải có access đến TẤT CẢ policies
if len(filters) < len(policy_ids):
    # User missing access to some required policies - DENY ALL
    logger.warning(
        f"User {user_id} missing access to some policies. "
        f"Required: {len(policy_ids)}, Found: {len(filters)}"
    )
    return "1=0"  # Deny all rows

# Build SQL WHERE clauses from filters
clauses = []

for f in filters:
    # Check for wildcard
    if "*" in f["allowed_values"]:
        # Skip filter - user has access to all values for this column
        logger.debug(f"Wildcard detected for policy {f['policy_id']}, skipping filter")
        continue

    # Escape SQL values to prevent injection
    values = [escape_sql_value(v) for v in f["allowed_values"]]
    values_str = "', '".join(values)

    # Build IN clause
    clauses.append(f"{f['column_name']} IN ('{values_str}')")

# Combine multiple clauses with AND
if not clauses:
    # All wildcards - no filter needed
    sql_filter = None
elif len(clauses) == 1:
    sql_filter = clauses[0]
else:
    # Multiple policies - combine with AND
    sql_filter = " AND ".join(clauses)

# Result for this example: "region IN ('mien_bac')"
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
┌─────────┐   ┌───────┐   ┌──────────────┐   ┌─────────┐   ┌─────────┐
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
     │            │               │                │ 1. Get table│
     │            │               │                │    policies │
     │            │               │                │────────────▶│
     │            │               │                │             │
     │            │               │                │ Return      │
     │            │               │                │ policy IDs  │
     │            │               │                │◀────────────│
     │            │               │                │             │
     │            │               │                │ 2. Get user │
     │            │               │                │  permissions│
     │            │               │                │  (per policy)│
     │            │               │                │────────────▶│
     │            │               │                │             │
     │            │               │                │ Return      │
     │            │               │                │ allowed vals│
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

1. Trino → OPA: Request authorization
2. OPA → Permission API: `{"user_id": "sale_nam", "resource": {...}}`
3. Permission API → OpenFGA (Query 1): Get policies for table `prod.public.customers`
   - Returns: `["customers_region_filter"]`
4. Permission API → OpenFGA (Query 2): Get user's allowed values for policy `customers_region_filter`
   - Returns: `allowed_values: ["mien_bac"]`, `attribute_name: "region"`
5. Permission API builds SQL filter: `region IN ('mien_bac')`
6. Permission API → OPA: `{"filter_expression": "region IN ('mien_bac')", "has_filter": true}`
7. OPA → Trino: `{"allow": true, "rowFilters": [{"expression": "region IN ('mien_bac')"}]}`
8. Trino executes with filter: `SELECT ... WHERE region IN ('mien_bac')`

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

1. Permission API → OpenFGA (Query 1): Get policies for table
   - Returns: `["customers_region_filter"]`
2. Permission API → OpenFGA (Query 2): Get user's allowed values
   - Returns: `allowed_values: ["mien_bac", "mien_trung", "mien_nam"]`
3. Permission API builds: `region IN ('mien_bac', 'mien_trung', 'mien_nam')`
4. OPA → Trino: `{"allow": true, "rowFilters": [{"expression": "region IN ('mien_bac', 'mien_trung', 'mien_nam')"}]}`
5. Trino executes: `SELECT COUNT(*) WHERE region IN ('mien_bac', 'mien_trung', 'mien_nam')`

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

1. Permission API → OpenFGA (Query 1): Get policies for table
   - Returns: `["customers_region_filter"]`
2. Permission API → OpenFGA (Query 2): Get user's allowed values
   - Returns: `allowed_values: ["*"]`
3. Permission API detects wildcard: `"*" in allowed_values`
4. Permission API skips this filter clause (wildcard = all access)
5. Permission API → OPA: `{"filter_expression": null, "has_filter": false}`
6. OPA → Trino: `{"allow": true, "rowFilters": []}`
7. Trino executes: `SELECT * FROM customers` (without WHERE clause)

**Result:** Admin sees ALL customers

---

### Example 4: Unauthorized User

**User `hacker` không có tuple nào**

**Flow:**

1. Permission API → OpenFGA (Query 1): Get policies for table
   - Returns: `["customers_region_filter"]`
2. Permission API → OpenFGA (Query 2): Get user's allowed values for policy
   - Returns: Empty list (no tuples found)
3. Permission API security check: `len(filters) < len(policy_ids)` → `0 < 1` → FAIL
4. Permission API → OPA: `{"filter_expression": "1=0", "has_filter": true}`
5. OPA → Trino: `{"allow": true, "rowFilters": [{"expression": "1=0"}]}`
6. Trino executes: `SELECT * WHERE 1=0`

**Result:** Empty result set (denied)

---

### Example 5: Multiple Policies (AND Logic)

**Scenario:** Table has 2 policies: `customers_region_filter` and `customers_status_filter`

**Setup:**

```json
// Policy 1: Filter by region
{
  "user": "table:prod.public.customers",
  "relation": "applies_to",
  "object": "row_filter_policy:customers_region_filter"
}

// Policy 2: Filter by status
{
  "user": "table:prod.public.customers",
  "relation": "applies_to",
  "object": "row_filter_policy:customers_status_filter"
}

// User access to policy 1
{
  "user": "user:analyst",
  "relation": "viewer",
  "object": "row_filter_policy:customers_region_filter",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "attribute_name": "region",
      "allowed_values": ["mien_bac", "mien_nam"]
    }
  }
}

// User access to policy 2
{
  "user": "user:analyst",
  "relation": "viewer",
  "object": "row_filter_policy:customers_status_filter",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "attribute_name": "status",
      "allowed_values": ["active"]
    }
  }
}
```

**Flow:**

1. Permission API → OpenFGA (Query 1): Get policies for table
   - Returns: `["customers_region_filter", "customers_status_filter"]`
2. Permission API loops through policies:
   - Query 2a: Get allowed values for `customers_region_filter`
     - Returns: `allowed_values: ["mien_bac", "mien_nam"]`
   - Query 2b: Get allowed values for `customers_status_filter`
     - Returns: `allowed_values: ["active"]`
3. Permission API builds SQL: `region IN ('mien_bac', 'mien_nam') AND status IN ('active')`
4. OPA → Trino: `{"allow": true, "rowFilters": [{"expression": "region IN ('mien_bac', 'mien_nam') AND status IN ('active')"}]}`
5. Trino executes: `SELECT * WHERE region IN ('mien_bac', 'mien_nam') AND status IN ('active')`

**Result:** User only sees active customers from North and South regions

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
INFO: [ENDPOINT] Received row filter request: user=sale_nam, resource={'catalog_name': 'prod', 'schema_name': 'public', 'table_name': 'customers'}
DEBUG: Found 1 policies for table prod.public.customers: ['customers_region_filter']
DEBUG: User sale_nam has access to policy customers_region_filter
INFO: Built row filter for user=sale_nam, table=prod.public.customers: region IN ('mien_bac')
INFO: [ENDPOINT] Returning row filter: user=sale_nam, table=prod.public.customers, filter=region IN ('mien_bac'), has_filter=True
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
4. Permission API → OpenFGA (Query 1): Get table policies
5. Permission API → OpenFGA (Query 2): Get user's allowed values per policy
6. Permission API builds SQL filter from allowed values (with AND logic for multiple policies)
7. Permission API → OPA: Returns filter expression
8. OPA → Trino: Returns authorization decision with row filters
9. Trino rewrites and executes query with filter

**Key Points:**

- ✅ **Automatic filtering**: Filter applied automatically by Trino, transparent to users
- ✅ **Fail-closed security**: Users must have access to ALL policies, missing any → deny all (1=0)
- ✅ **Wildcard support**: Use `["*"]` in allowed_values for unrestricted access
- ✅ **Multiple policies**: Combine filters with AND logic for fine-grained control
- ✅ **No application changes**: No code changes needed in data applications
- ✅ **Centralized management**: All permissions stored in OpenFGA
- ✅ **Dynamic updates**: Permission changes take effect immediately, no code deploy needed
- ✅ **Performance**: Row filter evaluated once per query, not per row

This architecture provides **transparent, scalable row-level security** for Trino! 🚀
