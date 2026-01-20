# Permission API Testing Guide

## Quick Test Guide

### 1. Grant Table-Level Select Permission

```bash
curl -X POST http://localhost:8000/api/v1/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "user"
    },
    "relation": "select"
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "hung",
  "resource_type": "table",
  "resource_id": "lakekeeper_bronze.finance.user",
  "object_id": "table:lakekeeper_bronze.finance.user",
  "relation": "select"
}
```

---

### 2. Grant Row Filter Permission

```bash
curl -X POST http://localhost:8000/api/v1/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "user"
    },
    "relation": "viewer",
    "condition": {
      "name": "has_attribute_access",
      "context": {
        "attribute_name": "region",
        "allowed_values": ["north"]
      }
    }
  }'
```

**Creates 2 tuples in OpenFGA:**

1. `user:hung --viewer--> row_filter_policy:user_region_filter` (with condition)
2. `table:lakekeeper_bronze.finance.user --applies_to--> row_filter_policy:user_region_filter`

**Expected Response:**

```json
{
  "success": true,
  "user_id": "hung",
  "resource_type": "row_filter_policy",
  "resource_id": "user_region_filter",
  "object_id": "row_filter_policy:user_region_filter",
  "relation": "viewer"
}
```

---

### 3. Check Permission

```bash
curl -X POST http://localhost:8000/api/v1/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "operation": "SelectFromColumns",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "user"
    }
  }'
```

**Expected:** `{"allowed": true}`

---

### 4. Check AccessCatalog (Hierarchical)

```bash
curl -X POST http://localhost:8000/api/v1/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "operation": "AccessCatalog",
    "resource": {
      "catalog_name": "lakekeeper_bronze"
    }
  }'
```

**Expected:** `{"allowed": true}` (because user has table-level permission)

---

### 5. Get Row Filter

```bash
curl -X POST http://localhost:8000/api/v1/permissions/row-filter \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "catalog_name": "lakekeeper_bronze",
    "schema_name": "finance",
    "table_name": "user"
  }'
```

**Expected Response:**

```json
{
  "user_id": "hung",
  "table": "lakekeeper_bronze.finance.user",
  "filter": "region IN ('north')",
  "has_filter": true
}
```

---

### 6. Revoke Table Select Permission

```bash
curl -X POST http://localhost:8000/api/v1/permissions/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "user"
    },
    "relation": "select"
  }'
```

**Deletes 1 tuple:**

- `user:hung --select--> table:lakekeeper_bronze.finance.user`

---

### 7. Revoke Row Filter Permission ✅

**Solution:** Provide `condition` with `attribute_name` to identify the policy

```bash
curl -X POST http://localhost:8000/api/v1/permissions/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "user"
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

**Deletes 2 tuples:**

1. `user:hung --viewer--> row_filter_policy:user_region_filter`
2. `table:lakekeeper_bronze.finance.user --applies_to--> row_filter_policy:user_region_filter`

**Note:**

- `allowed_values` can be empty for revoke (not used)
- The system uses `attribute_name` to build policy*id: `{table}*{attribute}\_filter`

---

## Verify in Database

```sql
-- Check tuples after grant
SELECT _user, user_type, relation, object_type, object_id, condition_name
FROM tuple
WHERE _user = 'user:hung' OR object_id LIKE '%user_region%';

-- Expected after row filter grant:
-- user:hung | user | viewer | row_filter_policy | user_region_filter | has_attribute_access
-- table:lakekeeper_bronze.finance.user | user | applies_to | row_filter_policy | user_region_filter | NULL

-- Expected after row filter revoke:
-- (both rows deleted)
```

---

## Summary

### Grant Operations

| Type         | Tuples Created                   |
| ------------ | -------------------------------- |
| Table select | 1 (user->table)                  |
| Row filter   | 2 (user->policy + table->policy) |

### Revoke Operations

| Type         | Tuples Deleted                   | Extra Info Needed                  |
| ------------ | -------------------------------- | ---------------------------------- |
| Table select | 1 (user->table)                  | None                               |
| Row filter   | 2 (user->policy + table->policy) | `condition.context.attribute_name` |

---

## Next Steps

1. ✅ Test grant table permission
2. ✅ Test grant row filter
3. ✅ Test check permission (hierarchical)
4. ✅ Test get row filter
5. ⚠️ Fix revoke row filter logic (need to know attribute_name)
6. 🔄 Add condition field to PermissionRevoke schema
7. 🔄 Update revoke_permission to handle row filter with condition
