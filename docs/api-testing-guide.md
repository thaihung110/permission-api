# Permission API Testing Guide

## Setup

**Base URL:**

```
{{baseUrl}} = http://localhost:8000/api/v1
```

## Table of Contents

1. [Health Check](#1-health-check)
2. [Permission Grant Operations](#2-permission-grant-operations)
3. [Permission Check Operations](#3-permission-check-operations)
4. [Row Filter Operations](#4-row-filter-operations)
5. [Permission Revoke Operations](#5-permission-revoke-operations)
6. [Advanced Test Scenarios](#6-advanced-test-scenarios)
7. [Database Verification](#7-database-verification)

---

## 1. Health Check

### Test Health Endpoint

```bash
curl -X GET {{baseUrl}}/health
```

**Expected Response (Healthy):**

```json
{
  "status": "healthy",
  "openfga_connected": true
}
```

**Expected Response (Unhealthy):**

```json
{
  "status": "unhealthy",
  "openfga_connected": false,
  "error": "Connection failed"
}
```

---

## 2. Permission Grant Operations

### 2.1. Grant Catalog-Level Select Permission

```bash
curl -X POST {{baseUrl}}/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "alice",
    "resource": {
      "catalog": "lakekeeper_bronze"
    },
    "relation": "select"
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "alice",
  "resource_type": "catalog",
  "resource_id": "lakekeeper_bronze",
  "object_id": "catalog:lakekeeper_bronze",
  "relation": "select"
}
```

**OpenFGA Tuple Created:**

- `user:alice --select--> catalog:lakekeeper_bronze`

---

### 2.2. Grant CreateCatalog Permission (System-Level)

**Note:** To grant permission to create new catalogs, you must grant `create` permission on the **system catalog** (`catalog:system`). This is done by providing an **empty resource** `{}`.

```bash
curl -X POST {{baseUrl}}/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "alice",
    "resource": {},
    "relation": "create"
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "alice",
  "resource_type": "catalog",
  "resource_id": "system",
  "object_id": "catalog:system",
  "relation": "create"
}
```

**OpenFGA Tuple Created:**

- `user:alice --create--> catalog:system`

**Usage:** This allows user `alice` to create new catalogs in the system.

---

### 2.3. Grant Catalog-Level Describe Permission

```bash
curl -X POST {{baseUrl}}/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "alice",
    "resource": {
      "catalog": "lakekeeper_bronze"
    },
    "relation": "describe"
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "alice",
  "resource_type": "catalog",
  "resource_id": "lakekeeper_bronze",
  "object_id": "catalog:lakekeeper_bronze",
  "relation": "describe"
}
```

---

### 2.4. Grant CreateSchema Permission (Catalog-Level)

**Note:** To allow a user to create new schemas in a catalog, grant `create` permission on the **catalog**. When the `CreateSchema` operation is checked, it will check for `create` permission on the catalog object.

```bash
curl -X POST {{baseUrl}}/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "bob",
    "resource": {
      "catalog": "lakekeeper_bronze"
    },
    "relation": "create"
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "bob",
  "resource_type": "catalog",
  "resource_id": "lakekeeper_bronze",
  "object_id": "catalog:lakekeeper_bronze",
  "relation": "create"
}
```

**OpenFGA Tuple Created:**

- `user:bob --create--> catalog:lakekeeper_bronze`

**Usage:** This allows user `bob` to create new schemas within the `lakekeeper_bronze` catalog.

---

### 2.5. Grant Schema-Level Select Permission

```bash
curl -X POST {{baseUrl}}/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "bob",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance"
    },
    "relation": "select"
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "bob",
  "resource_type": "schema",
  "resource_id": "lakekeeper_bronze.finance",
  "object_id": "schema:lakekeeper_bronze.finance",
  "relation": "select"
}
```

**OpenFGA Tuple Created:**

- `user:bob --select--> schema:lakekeeper_bronze.finance`

---

---

### 2.6. Grant CreateTable Permission (Schema-Level)

**Note:** To allow a user to create tables in a schema, grant `create` permission on the **schema**. This permission is checked when executing the `CreateTable` operation.

```bash
curl -X POST {{baseUrl}}/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "bob",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance"
    },
    "relation": "create"
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "bob",
  "resource_type": "schema",
  "resource_id": "lakekeeper_bronze.finance",
  "object_id": "schema:lakekeeper_bronze.finance",
  "relation": "create"
}
```

**OpenFGA Tuple Created:**

- `user:bob --create--> schema:lakekeeper_bronze.finance`

**Usage:** This allows user `bob` to create new tables within the `lakekeeper_bronze.finance` schema.

---

### 2.7. Grant Schema-Level Modify Permission

```bash
curl -X POST {{baseUrl}}/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "bob",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance"
    },
    "relation": "modify"
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "bob",
  "resource_type": "schema",
  "resource_id": "lakekeeper_bronze.finance",
  "object_id": "schema:lakekeeper_bronze.finance",
  "relation": "modify"
}
```

---

### 2.8. Grant Table-Level Select Permission

```bash
curl -X POST {{baseUrl}}/permissions/grant \
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

**OpenFGA Tuple Created:**

- `user:hung --select--> table:lakekeeper_bronze.finance.user`

---

### 2.9. Grant Table-Level Modify Permission

```bash
curl -X POST {{baseUrl}}/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "user"
    },
    "relation": "modify"
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
  "relation": "modify"
}
```

---

### 2.10. Grant Table-Level Describe Permission

```bash
curl -X POST {{baseUrl}}/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "user"
    },
    "relation": "describe"
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
  "relation": "describe"
}
```

---

### 2.11. Grant Table-Level Manage Grants Permission

```bash
curl -X POST {{baseUrl}}/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "admin",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "user"
    },
    "relation": "manage_grants"
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "admin",
  "resource_type": "table",
  "resource_id": "lakekeeper_bronze.finance.user",
  "object_id": "table:lakekeeper_bronze.finance.user",
  "relation": "manage_grants"
}
```

---

### 2.12. Grant Row Filter Permission (Single Region)

```bash
curl -X POST {{baseUrl}}/permissions/grant \
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

**Expected Response:**

```json
{
  "success": true,
  "user_id": "hung",
  "resource_type": "row_filter_policy",
  "resource_id": "lakekeeper_bronze.finance.user_region_filter",
  "object_id": "row_filter_policy:lakekeeper_bronze.finance.user_region_filter",
  "relation": "viewer"
}
```

**OpenFGA Tuples Created:**

1. `user:hung --viewer--> row_filter_policy:lakekeeper_bronze.finance.user_region_filter` (with condition: `has_attribute_access`)
2. `table:lakekeeper_bronze.finance.user --applies_to--> row_filter_policy:lakekeeper_bronze.finance.user_region_filter`

---

### 2.13. Grant Row Filter Permission (Multiple Regions)

```bash
curl -X POST {{baseUrl}}/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "sale_nam",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "customer"
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

**Expected Response:**

```json
{
  "success": true,
  "user_id": "sale_nam",
  "resource_type": "row_filter_policy",
  "resource_id": "lakekeeper_bronze.finance.customer_region_filter",
  "object_id": "row_filter_policy:lakekeeper_bronze.finance.customer_region_filter",
  "relation": "viewer"
}
```

---

### 2.14. Grant Row Filter Permission (Department-Based)

```bash
curl -X POST {{baseUrl}}/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "manager_finance",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "hr",
      "table": "employee"
    },
    "relation": "viewer",
    "condition": {
      "name": "has_attribute_access",
      "context": {
        "attribute_name": "department",
        "allowed_values": ["finance", "accounting"]
      }
    }
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "manager_finance",
  "resource_type": "row_filter_policy",
  "resource_id": "lakekeeper_bronze.hr.employee_department_filter",
  "object_id": "row_filter_policy:lakekeeper_bronze.hr.employee_department_filter",
  "relation": "viewer"
}
```

---

### 2.15. Grant Column Mask Permission

**Note:** To mask a specific column, grant `mask` permission on the **column** resource. This is used for column-level data masking.

```bash
curl -X POST {{baseUrl}}/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "analyst",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "user",
      "column": "email"
    },
    "relation": "mask"
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "analyst",
  "resource_type": "column",
  "resource_id": "lakekeeper_bronze.finance.user.email",
  "object_id": "column:lakekeeper_bronze.finance.user.email",
  "relation": "mask"
}
```

**OpenFGA Tuple Created:**

- `user:analyst --mask--> column:lakekeeper_bronze.finance.user.email`

**Usage:** This marks the `email` column for masking when user `analyst` queries the table. The actual masking logic is handled by the policy engine.

---

## 3. Permission Check Operations

### 3.1. Check AccessCatalog Permission

**Note:** `AccessCatalog` checks if the user has **any permission** on the catalog or its child resources (schemas, tables). First, it checks for direct catalog-level permissions (select, describe, modify, create). If none found, it checks if the user has permissions on any schema or table within that catalog.

**Prerequisites:** User must have been granted permissions in sections 2.1, 2.3, 2.4, or 2.5 onwards.

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "alice",
    "operation": "AccessCatalog",
    "resource": {
      "catalog_name": "lakekeeper_bronze"
    }
  }'
```

**Expected Response:**

```json
{ "allowed": true }
```

**Operation Mapping:** `AccessCatalog` → `select` relation (but also checks `describe`, `modify`, `create`)

**Explanation:** Returns `true` if user `alice` has:

- Direct permission on `catalog:lakekeeper_bronze` (granted in section 2.1 or 2.3), OR
- Permission on any schema in this catalog (granted in section 2.5), OR
- Permission on any table in this catalog (granted in section 2.8+)

---

### 3.2. Check ShowCatalogs Permission

**Prerequisites:** User must have been granted `describe` permission on the catalog in section 2.3.

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "alice",
    "operation": "ShowCatalogs",
    "resource": {
      "catalog_name": "lakekeeper_bronze"
    }
  }'
```

**Expected Response:**

```json
{ "allowed": true }
```

**Operation Mapping:** `ShowCatalogs` → `describe` relation on `catalog:lakekeeper_bronze`

**Explanation:** Checks if user `alice` has `describe` permission on `catalog:lakekeeper_bronze` (granted in section 2.3).

---

### 3.3. Check CreateCatalog Permission

**Prerequisites:** User must have been granted `create` permission on `catalog:system` in section 2.2.

**Note:** The `CreateCatalog` operation always checks permission on `catalog:system`, regardless of what catalog name is in the resource. The `catalog_name` in the request is the catalog being created, but the permission check happens on the system catalog.

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "alice",
    "operation": "CreateCatalog",
    "resource": {
      "catalog_name": "new_catalog"
    }
  }'
```

**Expected Response:**

```json
{ "allowed": true }
```

**Operation Mapping:** `CreateCatalog` → `create` relation on `catalog:system`

**Explanation:** This checks if user `alice` has `create` permission on `catalog:system`, which was granted in section 2.2.

---

### 3.4. Check DropCatalog Permission

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "alice",
    "operation": "DropCatalog",
    "resource": {
      "catalog_name": "lakekeeper_bronze"
    }
  }'
```

**Expected Response:**

```json
{ "allowed": false }
```

**Operation Mapping:** `DropCatalog` → `modify` relation

---

### 3.5. Check ShowSchemas Permission

**Note:** When checking `ShowSchemas` for a specific schema, the resource contains both `catalog_name` and `schema_name`, and the check is performed on the **schema** object.

**Prerequisites:** User must have been granted `describe` permission on the schema in section 2.5.

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "bob",
    "operation": "ShowSchemas",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance"
    }
  }'
```

**Expected Response:**

```json
{ "allowed": true }
```

**Operation Mapping:** `ShowSchemas` → `describe` relation on `schema:lakekeeper_bronze.finance`

**Explanation:** Checks if user `bob` has `describe` permission on `schema:lakekeeper_bronze.finance` (granted in section 2.5).

---

### 3.6. Check CreateSchema Permission

**Prerequisites:** User must have been granted `create` permission on the catalog in section 2.4.

**IMPORTANT:** The `CreateSchema` operation has **special handling** in the code. Even though the resource contains both `catalog_name` and `schema_name`, the permission check is performed on the **catalog** object (not the schema), because the schema doesn't exist yet.

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "bob",
    "operation": "CreateSchema",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "new_schema"
    }
  }'
```

**Expected Response:**

```json
{ "allowed": true }
```

**Operation Mapping:** `CreateSchema` → `create` relation on `catalog:lakekeeper_bronze`

**Explanation:** Despite having `schema_name` in the resource, this checks if user `bob` has `create` permission on `catalog:lakekeeper_bronze` (granted in section 2.4). The `schema_name` is the name of the schema being created.

---

### 3.7. Check DropSchema Permission

**Prerequisites:** User must have been granted `modify` permission on the schema in section 2.7.

**Note:** The `DropSchema` operation checks `modify` permission on the **schema** object (the existing schema being dropped).

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "bob",
    "operation": "DropSchema",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance"
    }
  }'
```

**Expected Response:**

```json
{ "allowed": true }
```

**Operation Mapping:** `DropSchema` → `modify` relation on `schema:lakekeeper_bronze.finance`

**Explanation:** Checks if user `bob` has `modify` permission on `schema:lakekeeper_bronze.finance` (granted in section 2.7).

---

### 3.8. Check CreateTable Permission

**Note:** The `CreateTable` operation checks `create` permission on the **schema** (not the table), because the table doesn't exist yet.

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "bob",
    "operation": "CreateTable",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance"
    }
  }'
```

**Expected Response:**

```json
{ "allowed": true }
```

**Operation Mapping:** `CreateTable` → `create` relation on `schema:lakekeeper_bronze.finance`

**Explanation:** This checks if user `bob` has `create` permission on `schema:lakekeeper_bronze.finance`, which was granted in section 2.6.

---

### 3.9. Check SelectFromColumns Permission

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "operation": "SelectFromColumns",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "user"
    }
  }'
```

**Expected Response:**

```json
{ "allowed": true }
```

**Operation Mapping:** `SelectFromColumns` → `select` relation

---

### 3.10. Check InsertIntoTable Permission

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "operation": "InsertIntoTable",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "user"
    }
  }'
```

**Expected Response:**

```json
{ "allowed": true }
```

**Operation Mapping:** `InsertIntoTable` → `modify` relation

---

### 3.11. Check UpdateTableColumns Permission

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "operation": "UpdateTableColumns",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "user"
    }
  }'
```

**Expected Response:**

```json
{ "allowed": true }
```

**Operation Mapping:** `UpdateTableColumns` → `modify` relation

---

### 3.12. Check DeleteFromTable Permission

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "operation": "DeleteFromTable",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "user"
    }
  }'
```

**Expected Response:**

```json
{ "allowed": true }
```

**Operation Mapping:** `DeleteFromTable` → `modify` relation

---

### 3.13. Check DropTable Permission

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "operation": "DropTable",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "user"
    }
  }'
```

**Expected Response:**

```json
{ "allowed": true }
```

**Operation Mapping:** `DropTable` → `modify` relation

---

### 3.14. Check ShowTables Permission

**Prerequisites:** User must have been granted `describe` permission on the table in section 2.10.

**Note:** The `ShowTables` operation checks `describe` permission on the **table** object.

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "operation": "ShowTables",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "user"
    }
  }'
```

**Expected Response:**

```json
{ "allowed": true }
```

**Operation Mapping:** `ShowTables` → `describe` relation on `table:lakekeeper_bronze.finance.user`

**Explanation:** Checks if user `hung` has `describe` permission on `table:lakekeeper_bronze.finance.user` (granted in section 2.10).

---

### 3.15. Check ShowColumns Permission

**Prerequisites:** User must have been granted `describe` permission on the table in section 2.10.

**Note:** The `ShowColumns` operation checks `describe` permission on the **table** (not column), because column-level `describe` permission inherits from table-level in the FGA model.

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "operation": "ShowColumns",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "user"
    }
  }'
```

**Expected Response:**

```json
{ "allowed": true }
```

**Operation Mapping:** `ShowColumns` → `describe` relation on `table:lakekeeper_bronze.finance.user`

**Explanation:** Checks if user `hung` has `describe` permission on `table:lakekeeper_bronze.finance.user` (granted in section 2.10). The check is at table level because column permissions inherit from the table.

---

### 3.16. Check AddColumn Permission

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "operation": "AddColumn",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "user"
    }
  }'
```

**Expected Response:**

```json
{ "allowed": true }
```

**Operation Mapping:** `AddColumn` → `modify` relation

---

### 3.17. Check SetTableAuthorization Permission

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "admin",
    "operation": "SetTableAuthorization",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "user"
    }
  }'
```

**Expected Response:**

```json
{ "allowed": true }
```

**Operation Mapping:** `SetTableAuthorization` → `manage_grants` relation

---

### 3.18. Check Permission (User Without Access)

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "unauthorized_user",
    "operation": "SelectFromColumns",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "user"
    }
  }'
```

**Expected Response:**

```json
{ "allowed": false }
```

---

### 3.19. Check MaskColumn Permission

**Prerequisites:** User must have been granted `mask` permission on the specific column in section 2.15.

**Note:** The `MaskColumn` operation checks `mask` permission on the specific **column**. Unlike other column operations, `mask` is column-specific and does not inherit from table-level permissions.

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "analyst",
    "operation": "MaskColumn",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "user",
      "column_name": "email"
    }
  }'
```

**Expected Response:**

```json
{ "allowed": true }
```

**Operation Mapping:** `MaskColumn` → `mask` relation on `column:lakekeeper_bronze.finance.user.email`

**Explanation:** Checks if user `analyst` has `mask` permission on the specific column (granted in section 2.15).

---

## 4. Row Filter Operations

### 4.1. Get Row Filter (Single Region)

```bash
curl -X POST {{baseUrl}}/permissions/row-filter \
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

---

### 4.2. Get Row Filter (Multiple Regions)

```bash
curl -X POST {{baseUrl}}/permissions/row-filter \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "sale_nam",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "customer"
    }
  }'
```

**Expected Response:**

```json
{
  "filter_expression": "region IN ('north', 'central')",
  "has_filter": true
}
```

---

### 4.3. Get Row Filter (Multiple Attributes)

```bash
curl -X POST {{baseUrl}}/permissions/row-filter \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "manager_finance",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "hr",
      "table_name": "employee"
    }
  }'
```

**Expected Response:**

```json
{
  "filter_expression": "department IN ('finance', 'accounting')",
  "has_filter": true
}
```

---

### 4.4. Get Row Filter (No Filter Applied)

```bash
curl -X POST {{baseUrl}}/permissions/row-filter \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "alice",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "user"
    }
  }'
```

**Expected Response (No Row Filter):**

```json
{
  "filter_expression": null,
  "has_filter": false
}
```

---

### 4.5. Get Row Filter (Invalid Resource)

```bash
curl -X POST {{baseUrl}}/permissions/row-filter \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "resource": {
      "catalog_name": "lakekeeper_bronze"
    }
  }'
```

**Expected Response (Fail Closed):**

```json
{
  "filter_expression": "1=0",
  "has_filter": true
}
```

**Note:** Missing `schema_name` or `table_name` triggers fail-closed behavior (deny all access).

---

### 4.6. Get Row Filter (Error Handling)

```bash
curl -X POST {{baseUrl}}/permissions/row-filter \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "resource": {
      "catalog_name": "invalid_catalog",
      "schema_name": "invalid_schema",
      "table_name": "invalid_table"
    }
  }'
```

**Expected Response (Fail Closed on Error):**

```json
{
  "filter_expression": "1=0",
  "has_filter": true
}
```

**Note:** Any error in processing triggers fail-closed behavior for security.

---

## 5. Permission Revoke Operations

### 5.1. Revoke Catalog-Level Select Permission

```bash
curl -X POST {{baseUrl}}/permissions/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "alice",
    "resource": {
      "catalog": "lakekeeper_bronze"
    },
    "relation": "select"
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "alice",
  "resource_type": "catalog",
  "resource_id": "lakekeeper_bronze",
  "object_id": "catalog:lakekeeper_bronze",
  "relation": "select"
}
```

**OpenFGA Tuple Deleted:**

- `user:alice --select--> catalog:lakekeeper_bronze`

---

### 5.2. Revoke CreateCatalog Permission (System-Level)

**Note:** To revoke the CreateCatalog permission, you must revoke `create` permission from `catalog:system` using an **empty resource** `{}`.

```bash
curl -X POST {{baseUrl}}/permissions/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "alice",
    "resource": {},
    "relation": "create"
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "alice",
  "resource_type": "catalog",
  "resource_id": "system",
  "object_id": "catalog:system",
  "relation": "create"
}
```

**OpenFGA Tuple Deleted:**

- `user:alice --create--> catalog:system`

---

### 5.3. Revoke Schema-Level Select Permission

```bash
curl -X POST {{baseUrl}}/permissions/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "bob",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance"
    },
    "relation": "select"
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "bob",
  "resource_type": "schema",
  "resource_id": "lakekeeper_bronze.finance",
  "object_id": "schema:lakekeeper_bronze.finance",
  "relation": "select"
}
```

**OpenFGA Tuple Deleted:**

- `user:bob --select--> schema:lakekeeper_bronze.finance`

---

### 5.4. Revoke CreateSchema Permission (Catalog-Level)

**Note:** To revoke the permission to create new schemas in a catalog, revoke `create` permission from the **catalog** (not schema). This corresponds to the grant in section 2.4.

```bash
curl -X POST {{baseUrl}}/permissions/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "bob",
    "resource": {
      "catalog": "lakekeeper_bronze"
    },
    "relation": "create"
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "bob",
  "resource_type": "catalog",
  "resource_id": "lakekeeper_bronze",
  "object_id": "catalog:lakekeeper_bronze",
  "relation": "create"
}
```

**OpenFGA Tuple Deleted:**

- `user:bob --create--> catalog:lakekeeper_bronze`

---

### 5.5. Revoke CreateTable Permission (Schema-Level)

**Note:** This revokes the permission to create tables in a schema. The resource contains both catalog and schema, and revokes `create` permission from the **schema** object. This corresponds to the grant in section 2.6.

```bash
curl -X POST {{baseUrl}}/permissions/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "bob",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance"
    },
    "relation": "create"
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "bob",
  "resource_type": "schema",
  "resource_id": "lakekeeper_bronze.finance",
  "object_id": "schema:lakekeeper_bronze.finance",
  "relation": "create"
}
```

**OpenFGA Tuple Deleted:**

- `user:bob --create--> schema:lakekeeper_bronze.finance`

---

### 5.6. Revoke Table-Level Select Permission

```bash
curl -X POST {{baseUrl}}/permissions/revoke \
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

**OpenFGA Tuple Deleted:**

- `user:hung --select--> table:lakekeeper_bronze.finance.user`

---

### 5.7. Revoke Table-Level Modify Permission

```bash
curl -X POST {{baseUrl}}/permissions/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "user"
    },
    "relation": "modify"
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
  "relation": "modify"
}
```

---

### 5.8. Revoke Table-Level Describe Permission

```bash
curl -X POST {{baseUrl}}/permissions/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "user"
    },
    "relation": "describe"
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
  "relation": "describe"
}
```

---

### 5.9. Revoke Row Filter Permission (Region-Based)

```bash
curl -X POST {{baseUrl}}/permissions/revoke \
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

**Expected Response:**

```json
{
  "success": true,
  "user_id": "hung",
  "resource_type": "row_filter_policy",
  "resource_id": "lakekeeper_bronze.finance.user_region_filter",
  "object_id": "row_filter_policy:lakekeeper_bronze.finance.user_region_filter",
  "relation": "viewer"
}
```

**OpenFGA Tuples Deleted:**

1. `user:hung --viewer--> row_filter_policy:lakekeeper_bronze.finance.user_region_filter`
2. `table:lakekeeper_bronze.finance.user --applies_to--> row_filter_policy:lakekeeper_bronze.finance.user_region_filter`

**Note:**

- `allowed_values` can be empty for revoke (not used in deletion)
- The system uses `attribute_name` to build policy*id: `{table}*{attribute}\_filter`

---

### 5.10. Revoke Row Filter Permission (Department-Based)

```bash
curl -X POST {{baseUrl}}/permissions/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "manager_finance",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "hr",
      "table": "employee"
    },
    "relation": "viewer",
    "condition": {
      "name": "has_attribute_access",
      "context": {
        "attribute_name": "department",
        "allowed_values": []
      }
    }
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "manager_finance",
  "resource_type": "row_filter_policy",
  "resource_id": "lakekeeper_bronze.hr.employee_department_filter",
  "object_id": "row_filter_policy:lakekeeper_bronze.hr.employee_department_filter",
  "relation": "viewer"
}
```

---

### 5.11. Revoke Manage Grants Permission

```bash
curl -X POST {{baseUrl}}/permissions/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "admin",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "user"
    },
    "relation": "manage_grants"
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "admin",
  "resource_type": "table",
  "resource_id": "lakekeeper_bronze.finance.user",
  "object_id": "table:lakekeeper_bronze.finance.user",
  "relation": "manage_grants"
}
```

---

### 5.12. Revoke Column Mask Permission

```bash
curl -X POST {{baseUrl}}/permissions/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "analyst",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "user",
      "column": "email"
    },
    "relation": "mask"
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "analyst",
  "resource_type": "column",
  "resource_id": "lakekeeper_bronze.finance.user.email",
  "object_id": "column:lakekeeper_bronze.finance.user.email",
  "relation": "mask"
}
```

**OpenFGA Tuple Deleted:**

- `user:analyst --mask--> column:lakekeeper_bronze.finance.user.email`

---

## 6. Advanced Test Scenarios

### 6.1. Test Hierarchical Permission Check

**Setup:** Grant schema-level select permission

```bash
curl -X POST {{baseUrl}}/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "charlie",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance"
    },
    "relation": "select"
  }'
```

**Test 1:** Check catalog access (should inherit from schema permission)

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "charlie",
    "operation": "AccessCatalog",
    "resource": {
      "catalog_name": "lakekeeper_bronze"
    }
  }'
```

**Expected:** `{"allowed": true}` (hierarchical inheritance)

**Test 2:** Check table select in same schema

```bash
curl -X POST {{baseUrl}}/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "charlie",
    "operation": "SelectFromColumns",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "user"
    }
  }'
```

**Expected:** `{"allowed": true}` (inherits from schema permission)

---

### 6.2. Test Multiple Row Filters

**Setup:** Grant multiple row filter policies for same user/table

```bash
# Filter 1: Region-based
curl -X POST {{baseUrl}}/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "data_analyst",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "sales",
      "table": "orders"
    },
    "relation": "viewer",
    "condition": {
      "name": "has_attribute_access",
      "context": {
        "attribute_name": "region",
        "allowed_values": ["north", "south"]
      }
    }
  }'

# Filter 2: Status-based
curl -X POST {{baseUrl}}/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "data_analyst",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "sales",
      "table": "orders"
    },
    "relation": "viewer",
    "condition": {
      "name": "has_attribute_access",
      "context": {
        "attribute_name": "status",
        "allowed_values": ["completed", "pending"]
      }
    }
  }'
```

**Test:** Get combined row filter

```bash
curl -X POST {{baseUrl}}/permissions/row-filter \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "data_analyst",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "sales",
      "table_name": "orders"
    }
  }'
```

**Expected Response:**

```json
{
  "filter_expression": "(region IN ('north', 'south')) AND (status IN ('completed', 'pending'))",
  "has_filter": true
}
```

**Note:** Multiple filters are combined with AND logic.

---

### 6.3. Test Permission with Missing Resource Fields

**Test 1:** Grant permission without required fields (should fail)

```bash
curl -X POST {{baseUrl}}/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "resource": {
      "table": "user"
    },
    "relation": "select"
  }'
```

**Expected:** HTTP 400 Bad Request

---

### 6.4. Test Revoke Non-Existent Permission

```bash
curl -X POST {{baseUrl}}/permissions/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "non_existent_user",
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
  "user_id": "non_existent_user",
  "resource_type": "table",
  "resource_id": "lakekeeper_bronze.finance.user",
  "object_id": "table:lakekeeper_bronze.finance.user",
  "relation": "select"
}
```

**Note:** Revoke operations are idempotent - revoking a non-existent permission is considered successful.

---

### 6.5. Test All Supported Trino Operations

**Operation Mapping Summary:**

| Trino Operation         | OpenFGA Relation | Resource Level | Notes                                      |
| ----------------------- | ---------------- | -------------- | ------------------------------------------ |
| AccessCatalog           | select           | catalog        |                                            |
| ShowCatalogs            | describe         | catalog        |                                            |
| CreateCatalog           | create           | system         | Checks `catalog:system`                    |
| DropCatalog             | modify           | catalog        |                                            |
| FilterCatalogs          | describe         | catalog        |                                            |
| ShowSchemas             | describe         | schema         |                                            |
| CreateSchema            | create           | catalog        | Checks catalog, not schema (doesn't exist) |
| DropSchema              | modify           | schema         |                                            |
| RenameSchema            | modify           | schema         |                                            |
| SetSchemaAuthorization  | manage_grants    | schema         |                                            |
| FilterSchemas           | describe         | schema         |                                            |
| CreateTable             | create           | schema         | Checks schema, not table (doesn't exist)   |
| CreateView              | create           | schema         |                                            |
| ShowTables              | describe         | table          |
| DropTable               | modify           | table          |
| RenameTable             | modify           | table          |
| SetTableComment         | describe         | table          |
| SetTableAuthorization   | manage_grants    | table          |
| FilterTables            | describe         | table          |
| SelectFromColumns       | select           | table          |
| InsertIntoTable         | modify           | table          |
| UpdateTableColumns      | modify           | table          |
| DeleteFromTable         | modify           | table          |
| TruncateTable           | modify           | table          |
| ShowColumns             | describe         | table          |
| FilterColumns           | describe         | table          |
| AddColumn               | modify           | table          |
| DropColumn              | modify           | table          |
| RenameColumn            | modify           | table          |
| SetColumnComment        | describe         | table          |
| MaskColumn              | mask             | column         |
| DropView                | modify           | table          |
| RenameView              | modify           | table          |
| SetViewComment          | describe         | table          |
| RefreshMaterializedView | modify           | table          |
| ExecuteQuery            | describe         | system         |

---

## 7. Database Verification

### 7.1. Check Tuples After Grant

```sql
-- Check all tuples for a specific user
SELECT _user, user_type, relation, object_type, object_id, condition_name
FROM tuple
WHERE _user = 'user:hung'
ORDER BY object_type, object_id;

-- Example output after table-level grant:
-- _user      | user_type | relation | object_type | object_id                              | condition_name
-- user:hung  | user      | select   | table       | lakekeeper_bronze.finance.user         | NULL
```

---

### 7.2. Check Row Filter Policy Tuples

```sql
-- Check row filter policy tuples
SELECT _user, user_type, relation, object_type, object_id, condition_name, condition_context
FROM tuple
WHERE object_type = 'row_filter_policy' OR _user LIKE '%row_filter_policy%'
ORDER BY object_id;

-- Example output after row filter grant:
-- _user                                                  | user_type | relation   | object_type        | object_id                                          | condition_name         | condition_context
-- user:hung                                              | user      | viewer     | row_filter_policy  | lakekeeper_bronze.finance.user_region_filter       | has_attribute_access   | {"attribute_name":"region","allowed_values":["north"]}
-- table:lakekeeper_bronze.finance.user                   | table     | applies_to | row_filter_policy  | lakekeeper_bronze.finance.user_region_filter       | NULL                   | NULL
```

---

### 7.3. Check Tuples After Revoke

```sql
-- Verify tuples are deleted after revoke
SELECT _user, user_type, relation, object_type, object_id, condition_name
FROM tuple
WHERE _user = 'user:hung' OR object_id LIKE '%user_region%';

-- Expected after row filter revoke: (both rows deleted)
-- (empty result set)
```

---

### 7.4. Count Tuples by User

```sql
-- Count total tuples per user
SELECT _user, COUNT(*) as tuple_count
FROM tuple
WHERE user_type = 'user'
GROUP BY _user
ORDER BY tuple_count DESC;
```

---

### 7.5. Count Tuples by Resource Type

```sql
-- Count tuples by object type
SELECT object_type, COUNT(*) as tuple_count
FROM tuple
GROUP BY object_type
ORDER BY tuple_count DESC;
```

---

## Summary

### Grant Operations

| Permission Type | Tuples Created                 | Required Fields                           |
| --------------- | ------------------------------ | ----------------------------------------- |
| Catalog-level   | 1 (user→catalog)               | `catalog`                                 |
| Schema-level    | 1 (user→schema)                | `catalog`, `schema`                       |
| Table-level     | 1 (user→table)                 | `catalog`, `schema`, `table`              |
| Row filter      | 2 (user→policy + table→policy) | `catalog`, `schema`, `table`, `condition` |

### Revoke Operations

| Permission Type | Tuples Deleted                 | Extra Info Required                |
| --------------- | ------------------------------ | ---------------------------------- |
| Catalog-level   | 1 (user→catalog)               | None                               |
| Schema-level    | 1 (user→schema)                | None                               |
| Table-level     | 1 (user→table)                 | None                               |
| Row filter      | 2 (user→policy + table→policy) | `condition.context.attribute_name` |

### Supported Relations

- **select**: Read-only access to data (`SELECT` queries)
- **modify**: Write/update access to data (`INSERT`, `UPDATE`, `DELETE`, `DROP`, etc.)
- **create**: Create new resources (`CREATE TABLE`, `CREATE SCHEMA`, etc.)
- **describe**: View metadata (`SHOW TABLES`, `SHOW COLUMNS`, etc.)
- **manage_grants**: Manage permissions on resources
- **viewer**: Row filter policy viewer (with condition context)
- **mask**: Column masking (future implementation)

### Key Features

1. **Hierarchical Permissions**: Schema-level permissions apply to all tables in the schema; catalog-level permissions apply to all schemas and tables.
2. **Row Filter Policies**: Support for attribute-based row filtering with condition contexts.
3. **Multiple Filters**: Multiple row filter policies are combined with AND logic.
4. **Fail-Closed**: Row filter endpoint fails closed (deny all) on errors or invalid input.
5. **Idempotent Operations**: Revoke operations are idempotent - revoking non-existent permissions succeeds.

---

## Quick Reference

### All Endpoints

| Method | Endpoint                  | Purpose                              |
| ------ | ------------------------- | ------------------------------------ |
| GET    | `/health`                 | Health check                         |
| POST   | `/permissions/grant`      | Grant permission to user             |
| POST   | `/permissions/revoke`     | Revoke permission from user          |
| POST   | `/permissions/check`      | Check if user has permission         |
| POST   | `/permissions/row-filter` | Get row filter SQL for user on table |

### Common Test Flow

1. **Grant permission** → `/permissions/grant`
2. **Check permission** → `/permissions/check` (verify granted)
3. **Get row filter** → `/permissions/row-filter` (if applicable)
4. **Revoke permission** → `/permissions/revoke`
5. **Check permission again** → `/permissions/check` (verify revoked)
6. **Verify in database** → Query `tuple` table

---

## Environment Variables

```bash
# OpenFGA Configuration
OPENFGA_SCHEME=http
OPENFGA_HOST=localhost
OPENFGA_PORT=8080
OPENFGA_STORE_ID=<your-store-id>
OPENFGA_AUTH_MODEL_ID=<your-model-id>

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Base URL for testing
{{baseUrl}}=http://localhost:8000/api/v1
```

---

## Testing Tools

### cURL

All examples in this guide use cURL for simplicity.

### Postman

Import the requests by:

1. Create a new environment variable: `baseUrl = http://localhost:8000/api/v1`
2. Copy-paste the request bodies
3. Use `{{baseUrl}}` in all URLs

### HTTPie

Alternative syntax for HTTPie users:

```bash
# Grant permission
http POST {{baseUrl}}/permissions/grant \
  user_id=hung \
  resource:='{"catalog":"lakekeeper_bronze","schema":"finance","table":"user"}' \
  relation=select

# Check permission
http POST {{baseUrl}}/permissions/check \
  user_id=hung \
  operation=SelectFromColumns \
  resource:='{"catalog_name":"lakekeeper_bronze","schema_name":"finance","table_name":"user"}'
```
