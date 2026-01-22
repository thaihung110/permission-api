# Complete Permission Flow Example

This document demonstrates a complete end-to-end flow for granting and checking permissions, including table-level select, row filtering, and column masking.

## Scenario

We want to grant user `data_analyst` access to the `lakekeeper_bronze.finance.transactions` table with the following restrictions:

- ✅ Can SELECT from the table
- ✅ Can only see rows where `region IN ('north', 'central')`
- ✅ Must mask the `account_number` column (sensitive data)

## Environment Setup

```bash
{{baseUrl}} = http://localhost:8000/api/v1
```

## Table Information

- **Catalog**: `lakekeeper_bronze`
- **Schema**: `finance`
- **Table**: `transactions`
- **Columns**: `id`, `account_number`, `amount`, `region`, `transaction_date`
- **User**: `data_analyst`

---

## Step 1: Grant Table-Level Select Permission

First, grant basic SELECT permission on the table.

**Note:** Regular permissions (select, modify, create, describe, manage_grants) use the `/permissions/grant` endpoint. Row filter policies and column masks use dedicated endpoints (see Steps 2 and 3).

### Request

```bash
curl -X POST {{baseUrl}}/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "data_analyst",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "transactions"
    },
    "relation": "select"
  }'
```

### Expected Response

```json
{
  "success": true,
  "user_id": "data_analyst",
  "resource_type": "table",
  "resource_id": "lakekeeper_bronze.finance.transactions",
  "object_id": "table:lakekeeper_bronze.finance.transactions",
  "relation": "select"
}
```

### OpenFGA Tuple Created

```
user:data_analyst --select--> table:lakekeeper_bronze.finance.transactions
```

---

## Step 2: Grant Row Filter Permission (Region-Based)

Grant row filter to restrict data access to specific regions.

**Note:** This example uses the dedicated `/row-filter/grant` endpoint, which is the recommended way to grant row filter policies.

### Request

```bash
curl -X POST {{baseUrl}}/row-filter/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "data_analyst",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "transactions"
    },
    "attribute_name": "region",
    "allowed_values": ["north", "central"]
  }'
```

### Expected Response

```json
{
  "success": true,
  "user_id": "data_analyst",
  "policy_id": "transactions_region_filter",
  "object_id": "row_filter_policy:transactions_region_filter",
  "table_fqn": "lakekeeper_bronze.finance.transactions",
  "attribute_name": "region",
  "relation": "viewer"
}
```

### OpenFGA Tuples Created

```
user:data_analyst --viewer--> row_filter_policy:transactions_region_filter
  (with condition: has_attribute_access, context: {"attribute_name": "region", "allowed_values": ["north", "central"]})

table:lakekeeper_bronze.finance.transactions --applies_to--> row_filter_policy:transactions_region_filter
```

---

## Step 3: Grant Column Mask Permission (Account Number)

Mask the sensitive `account_number` column.

**Note:** This example uses the dedicated `/column-mask/grant` endpoint, which is the recommended way to grant column mask permissions.

### Request

```bash
curl -X POST {{baseUrl}}/column-mask/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "data_analyst",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "transactions",
      "column": "account_number"
    }
  }'
```

### Expected Response

```json
{
  "success": true,
  "user_id": "data_analyst",
  "column_id": "lakekeeper_bronze.finance.transactions.account_number",
  "object_id": "column:lakekeeper_bronze.finance.transactions.account_number",
  "relation": "mask"
}
```

### OpenFGA Tuple Created

```
user:data_analyst --mask--> column:lakekeeper_bronze.finance.transactions.account_number
```

---

## Step 4: Verify Permissions - Check AccessCatalog

Check if the user can access the catalog (should be allowed due to table-level permission).

### Request

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "data_analyst",
    "operation": "AccessCatalog",
    "resource": {
      "catalog_name": "lakekeeper_bronze"
    }
  }'
```

### Expected Response

```json
{
  "allowed": true
}
```

### Explanation

The `AccessCatalog` operation performs hierarchical checking:

1. First checks for direct catalog-level permissions → **Not found**
2. Then checks for schema-level permissions in this catalog → **Not found**
3. Finally checks for table-level permissions in this catalog → **Found!** (`select` on `transactions` table)
4. Returns `true` because user has permissions on a table within the catalog

---

## Step 5: Verify Permissions - Check SelectFromColumns

Check if the user can select data from the table.

### Request

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "data_analyst",
    "operation": "SelectFromColumns",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "transactions"
    }
  }'
```

### Expected Response

```json
{
  "allowed": true
}
```

### Explanation

- Operation `SelectFromColumns` maps to `select` relation
- Checks `select` permission on `table:lakekeeper_bronze.finance.transactions`
- User has this permission (granted in Step 1)
- Returns `true`

---

## Step 6: Verify Permissions - Check MaskColumn

Check if the `account_number` column should be masked.

### Request

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "data_analyst",
    "operation": "MaskColumn",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "transactions",
      "column_name": "account_number"
    }
  }'
```

### Expected Response

```json
{
  "allowed": true
}
```

### Explanation

- Operation `MaskColumn` maps to `mask` relation
- Checks `mask` permission on `column:lakekeeper_bronze.finance.transactions.account_number`
- User has this permission (granted in Step 3)
- Returns `true` → The column should be masked for this user

---

## Step 7: Verify Permissions - Check Other Columns (No Mask)

Check if other columns like `amount` should be masked.

### Request

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "data_analyst",
    "operation": "MaskColumn",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "transactions",
      "column_name": "amount"
    }
  }'
```

### Expected Response

```json
{
  "allowed": false
}
```

### Explanation

- Checks `mask` permission on `column:lakekeeper_bronze.finance.transactions.amount`
- User does NOT have this permission
- Returns `false` → The column should NOT be masked

---

## Step 8: Get Row Filter SQL

Retrieve the row filter SQL expression for the user.

**Note:** This endpoint has been moved from `/permissions/row-filter` to `/row-filter/query`.

### Request

```bash
curl -X POST {{baseUrl}}/row-filter/query \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "data_analyst",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "transactions"
    }
  }'
```

### Expected Response

```json
{
  "filter_expression": "region IN ('north', 'central')",
  "has_filter": true
}
```

### Explanation

- The system queries OpenFGA for row filter policies linked to this table
- Finds the policy `transactions_region_filter` with condition context
- Extracts allowed values: `["north", "central"]`
- Builds SQL filter: `region IN ('north', 'central')`
- Returns the filter expression to be applied by OPA/Trino

---

## Step 9: List Row Filter Policies

List all row filter policies that the user has access to on the table.

### Request

```bash
curl -X POST {{baseUrl}}/row-filter/list \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "data_analyst",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "transactions"
    }
  }'
```

### Expected Response

```json
{
  "user_id": "data_analyst",
  "table_fqn": "lakekeeper_bronze.finance.transactions",
  "policies": [
    {
      "policy_id": "transactions_region_filter",
      "attribute_name": "region",
      "allowed_values": ["north", "central"]
    }
  ],
  "count": 1
}
```

### Explanation

- Queries OpenFGA for all row filter policies linked to the table
- Checks which policies the user has `viewer` access to
- Returns policy details including `attribute_name` and `allowed_values`

---

## Step 10: List Masked Columns

List all columns that are masked for the user on the table.

### Request

```bash
curl -X POST {{baseUrl}}/column-mask/list \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "data_analyst",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "transactions"
    }
  }'
```

### Expected Response

```json
{
  "user_id": "data_analyst",
  "table_fqn": "lakekeeper_bronze.finance.transactions",
  "masked_columns": ["account_number"],
  "count": 1
}
```

### Explanation

- Queries OpenFGA for all `mask` relation tuples for the user
- Filters columns that belong to the specified table
- Returns list of column names that are masked

---

## Step 11: Check User Without Permissions

Verify that an unauthorized user cannot access the table.

### Request

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "unauthorized_user",
    "operation": "SelectFromColumns",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "transactions"
    }
  }'
```

### Expected Response

```json
{
  "allowed": false
}
```

### Explanation

- User `unauthorized_user` has no permissions granted
- Returns `false` → Access denied

---

## Summary of Permissions Granted

| Permission Type | User           | Resource                                                | Endpoint Used            | Effect                                               |
| --------------- | -------------- | ------------------------------------------------------- | ------------------------ | ---------------------------------------------------- |
| Table Select    | `data_analyst` | `lakekeeper_bronze.finance.transactions`                | `/permissions/grant`     | Can query the table                                  |
| Row Filter      | `data_analyst` | `lakekeeper_bronze.finance.transactions`                | `/row-filter/grant`      | Only see rows where `region IN ('north', 'central')` |
| Column Mask     | `data_analyst` | `lakekeeper_bronze.finance.transactions.account_number` | `/column-mask/grant`     | `account_number` column is masked                    |

**Note:** 
- Regular permissions (select, modify, create, describe, manage_grants) use `/permissions/grant` and `/permissions/revoke`
- Row filter policies use `/row-filter/grant` and `/row-filter/revoke`
- Column mask permissions use `/column-mask/grant` and `/column-mask/revoke`

---

## Expected Query Behavior

When user `data_analyst` executes a query like:

```sql
SELECT * FROM lakekeeper_bronze.finance.transactions;
```

The effective query (after OPA applies policies) becomes:

```sql
SELECT
  id,
  MASK(account_number) AS account_number,  -- Masked column
  amount,
  region,
  transaction_date
FROM lakekeeper_bronze.finance.transactions
WHERE region IN ('north', 'central');      -- Row filter applied
```

---

## OpenFGA Tuples Summary

After all grants, the following tuples exist in OpenFGA:

```
1. user:data_analyst --select--> table:lakekeeper_bronze.finance.transactions

2. user:data_analyst --viewer--> row_filter_policy:transactions_region_filter
   (condition: has_attribute_access, context: {"attribute_name": "region", "allowed_values": ["north", "central"]})

3. table:lakekeeper_bronze.finance.transactions --applies_to--> row_filter_policy:transactions_region_filter

4. user:data_analyst --mask--> column:lakekeeper_bronze.finance.transactions.account_number
```

**Note:** Policy ID format is `{table_name}_{attribute_name}_filter` (e.g., `transactions_region_filter`).

---

## Cleanup: Revoke All Permissions

To revoke all permissions and return to initial state:

### Revoke Table Select Permission

**Note:** Regular permissions use the `/permissions/revoke` endpoint.

```bash
curl -X POST {{baseUrl}}/permissions/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "data_analyst",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "transactions"
    },
    "relation": "select"
  }'
```

### Revoke Row Filter Permission

**Note:** Use the dedicated `/row-filter/revoke` endpoint for revoking row filter policies. The old `/permissions/revoke` endpoint with `relation="viewer"` is deprecated.

```bash
curl -X POST {{baseUrl}}/row-filter/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "data_analyst",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "transactions"
    },
    "attribute_name": "region",
    "allowed_values": []
  }'
```

**Note:** `allowed_values` can be empty for revoke (not used in deletion). The system uses `attribute_name` to build policy_id: `{table}_{attribute}_filter`.

### Revoke Column Mask Permission

**Note:** Use the dedicated `/column-mask/revoke` endpoint for revoking column mask permissions. The old `/permissions/revoke` endpoint with `relation="mask"` is deprecated.

```bash
curl -X POST {{baseUrl}}/column-mask/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "data_analyst",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "transactions",
      "column": "account_number"
    }
  }'
```

---

## Testing Flow Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    GRANT PERMISSIONS                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
    Step 1: Grant SELECT on table
            Endpoint: POST /permissions/grant
            → Allow data access
                            ↓
    Step 2: Grant ROW FILTER
            Endpoint: POST /row-filter/grant
            → Restrict to regions (region IN ('north', 'central'))
                            ↓
    Step 3: Grant COLUMN MASK
            Endpoint: POST /column-mask/grant
            → Mask sensitive columns (account_number)
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    CHECK PERMISSIONS                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
    Step 4: Check AccessCatalog
            Endpoint: POST /permissions/check
            → ✅ Allowed (hierarchical)
                            ↓
    Step 5: Check SelectFromColumns
            Endpoint: POST /permissions/check
            → ✅ Allowed
                            ↓
    Step 6: Check MaskColumn (account_number)
            Endpoint: POST /permissions/check
            → ✅ Should mask
                            ↓
    Step 7: Check MaskColumn (amount)
            Endpoint: POST /permissions/check
            → ❌ Should NOT mask
                            ↓
    Step 8: Get Row Filter SQL
            Endpoint: POST /row-filter/query
            → "region IN ('north', 'central')"
                            ↓
    Step 9: List Row Filter Policies
            Endpoint: POST /row-filter/list
            → Show policies for user
                            ↓
    Step 10: List Masked Columns
             Endpoint: POST /column-mask/list
             → Show masked columns for user
                            ↓
    Step 11: Check Unauthorized User
             Endpoint: POST /permissions/check
             → ❌ Denied
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    CLEANUP (Optional)                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
    Revoke SELECT: POST /permissions/revoke
                            ↓
    Revoke ROW FILTER: POST /row-filter/revoke
                            ↓
    Revoke COLUMN MASK: POST /column-mask/revoke
```

## Endpoint Summary

| Operation              | Endpoint                    | Purpose                                    |
| ---------------------- | --------------------------- | ------------------------------------------ |
| Grant regular permission | `/permissions/grant`      | Grant select, modify, create, describe, etc |
| Grant row filter       | `/row-filter/grant`        | Grant row filter policy                    |
| Grant column mask      | `/column-mask/grant`        | Grant column mask permission               |
| Check permission       | `/permissions/check`       | Check if user has permission               |
| Get row filter SQL     | `/row-filter/query`        | Get SQL filter expression                  |
| List row filter policies | `/row-filter/list`        | List policies for user on table            |
| List masked columns    | `/column-mask/list`         | List masked columns for user on table      |
| Revoke regular permission | `/permissions/revoke`    | Revoke regular permissions                 |
| Revoke row filter      | `/row-filter/revoke`       | Revoke row filter policy                   |
| Revoke column mask     | `/column-mask/revoke`       | Revoke column mask permission              |

**Important Notes:**

- **Regular permissions** (select, modify, create, describe, manage_grants) use `/permissions/grant` and `/permissions/revoke`
- **Row filter policies** use `/row-filter/grant` and `/row-filter/revoke` (deprecated: `/permissions/grant` with `relation="viewer"`)
- **Column mask permissions** use `/column-mask/grant` and `/column-mask/revoke` (deprecated: `/permissions/grant` with `relation="mask"`)
- **Row filter SQL query** uses `/row-filter/query` (deprecated: `/permissions/row-filter`)
