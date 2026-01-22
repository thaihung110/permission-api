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
    "relation": "viewer",
    "condition": {
      "name": "has_attribute_access",
      "context": {
        "attribute_name": "region",
        "allowed_values": ["north", "central"]
      }
    }
  }'
```

### Expected Response

```json
{
  "success": true,
  "user_id": "data_analyst",
  "resource_type": "row_filter_policy",
  "resource_id": "lakekeeper_bronze.finance.transactions_region_filter",
  "object_id": "row_filter_policy:lakekeeper_bronze.finance.transactions_region_filter",
  "relation": "viewer"
}
```

### OpenFGA Tuples Created

```
user:data_analyst --viewer--> row_filter_policy:lakekeeper_bronze.finance.transactions_region_filter
  (with condition: has_attribute_access, context: {"attribute_name": "region", "allowed_values": ["north", "central"]})

table:lakekeeper_bronze.finance.transactions --applies_to--> row_filter_policy:lakekeeper_bronze.finance.transactions_region_filter
```

---

## Step 3: Grant Column Mask Permission (Account Number)

Mask the sensitive `account_number` column.

### Request

```bash
curl -X POST {{baseUrl}}/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "data_analyst",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "transactions",
      "column": "account_number"
    },
    "relation": "mask"
  }'
```

### Expected Response

```json
{
  "success": true,
  "user_id": "data_analyst",
  "resource_type": "column",
  "resource_id": "lakekeeper_bronze.finance.transactions.account_number",
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

### Request

```bash
curl -X POST {{baseUrl}}/permissions/row-filter \
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

## Step 9: Check User Without Permissions

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

| Permission Type | User           | Resource                                                | Relation/Policy          | Effect                                               |
| --------------- | -------------- | ------------------------------------------------------- | ------------------------ | ---------------------------------------------------- |
| Table Select    | `data_analyst` | `lakekeeper_bronze.finance.transactions`                | `select`                 | Can query the table                                  |
| Row Filter      | `data_analyst` | `lakekeeper_bronze.finance.transactions`                | `viewer` (region filter) | Only see rows where `region IN ('north', 'central')` |
| Column Mask     | `data_analyst` | `lakekeeper_bronze.finance.transactions.account_number` | `mask`                   | `account_number` column is masked                    |

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

2. user:data_analyst --viewer--> row_filter_policy:lakekeeper_bronze.finance.transactions_region_filter
   (condition: has_attribute_access, context: {"attribute_name": "region", "allowed_values": ["north", "central"]})

3. table:lakekeeper_bronze.finance.transactions --applies_to--> row_filter_policy:lakekeeper_bronze.finance.transactions_region_filter

4. user:data_analyst --mask--> column:lakekeeper_bronze.finance.transactions.account_number
```

---

## Cleanup: Revoke All Permissions

To revoke all permissions and return to initial state:

### Revoke Table Select Permission

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
    "relation": "viewer",
    "condition": {
      "name": "has_attribute_access",
      "context": {
        "attribute_name": "region",
        "allowed_values": []
      }
    }
  }'
```

### Revoke Column Mask Permission

```bash
curl -X POST {{baseUrl}}/permissions/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "data_analyst",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "transactions",
      "column": "account_number"
    },
    "relation": "mask"
  }'
```

---

## Testing Flow Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    GRANT PERMISSIONS                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
    Step 1: Grant SELECT on table → Allow data access
                            ↓
    Step 2: Grant ROW FILTER → Restrict to regions
                            ↓
    Step 3: Grant COLUMN MASK → Mask sensitive columns
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    CHECK PERMISSIONS                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
    Step 4: Check AccessCatalog → ✅ Allowed (hierarchical)
                            ↓
    Step 5: Check SelectFromColumns → ✅ Allowed
                            ↓
    Step 6: Check MaskColumn (account_number) → ✅ Should mask
                            ↓
    Step 7: Check MaskColumn (amount) → ❌ Should NOT mask
                            ↓
    Step 8: Get Row Filter SQL → "region IN ('north', 'central')"
                            ↓
    Step 9: Check Unauthorized User → ❌ Denied
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    CLEANUP (Optional)                        │
└─────────────────────────────────────────────────────────────┘
```
