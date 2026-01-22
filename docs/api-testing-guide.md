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
5. [Row Filter Policy Operations](#5-row-filter-policy-operations)
6. [Column Mask Operations](#6-column-mask-operations)
7. [Permission Revoke Operations](#7-permission-revoke-operations)
8. [Advanced Test Scenarios](#8-advanced-test-scenarios)
9. [Database Verification](#9-database-verification)

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

### 2.12. Grant Row Filter Permission (DEPRECATED - Use Section 5.1)

**Note:** Row filter permissions should now be granted using the dedicated `/row-filter/grant` endpoint (see Section 5.1). The old `/permissions/grant` endpoint with `relation="viewer"` and condition is deprecated but still supported for backward compatibility.

---

### 2.15. Grant Column Mask Permission (DEPRECATED - Use Section 6.1)

**Note:** Column mask permissions should now be granted using the dedicated `/column-mask/grant` endpoint (see Section 6.1). The old `/permissions/grant` endpoint with `relation="mask"` is deprecated but still supported for backward compatibility.

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

### 4.1. Get Row Filter SQL (Single Region)

**Note:** This endpoint has been moved from `/permissions/row-filter` to `/row-filter/query`. The old endpoint is deprecated but still supported for backward compatibility.

```bash
curl -X POST {{baseUrl}}/row-filter/query \
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

### 4.2. Get Row Filter SQL (Multiple Regions)

```bash
curl -X POST {{baseUrl}}/row-filter/query \
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

### 4.3. Get Row Filter SQL (Multiple Attributes)

```bash
curl -X POST {{baseUrl}}/row-filter/query \
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

### 4.4. Get Row Filter SQL (No Filter Applied)

```bash
curl -X POST {{baseUrl}}/row-filter/query \
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

### 4.5. Get Row Filter SQL (Invalid Resource)

```bash
curl -X POST {{baseUrl}}/row-filter/query \
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

### 4.6. Get Row Filter SQL (Error Handling)

```bash
curl -X POST {{baseUrl}}/row-filter/query \
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

## 5. Row Filter Policy Operations

This section covers dedicated endpoints for managing row filter policies. These endpoints provide a cleaner API specifically designed for row filtering operations.

### 5.1. Grant Row Filter Policy (Single Region)

**Prerequisites:** None

**Note:** This is the recommended way to grant row filter policies. The old `/permissions/grant` endpoint with `relation="viewer"` is deprecated.

```bash
curl -X POST {{baseUrl}}/row-filter/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "user"
    },
    "attribute_name": "region",
    "allowed_values": ["north"]
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "hung",
  "policy_id": "user_region_filter",
  "object_id": "row_filter_policy:user_region_filter",
  "table_fqn": "lakekeeper_bronze.finance.user",
  "attribute_name": "region",
  "relation": "viewer"
}
```

**OpenFGA Tuples Created:**

1. `user:hung --viewer--> row_filter_policy:user_region_filter` (with condition: `has_attribute_access`, context: `{"attribute_name": "region", "allowed_values": ["north"]}`)
2. `table:lakekeeper_bronze.finance.user --applies_to--> row_filter_policy:user_region_filter`

---

### 5.2. Grant Row Filter Policy (Multiple Regions)

```bash
curl -X POST {{baseUrl}}/row-filter/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "sale_nam",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "customer"
    },
    "attribute_name": "region",
    "allowed_values": ["north", "central"]
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "sale_nam",
  "policy_id": "customer_region_filter",
  "object_id": "row_filter_policy:customer_region_filter",
  "table_fqn": "lakekeeper_bronze.finance.customer",
  "attribute_name": "region",
  "relation": "viewer"
}
```

---

### 5.3. Grant Row Filter Policy (Department-Based)

```bash
curl -X POST {{baseUrl}}/row-filter/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "manager_finance",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "hr",
      "table": "employee"
    },
    "attribute_name": "department",
    "allowed_values": ["finance", "accounting"]
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "manager_finance",
  "policy_id": "employee_department_filter",
  "object_id": "row_filter_policy:employee_department_filter",
  "table_fqn": "lakekeeper_bronze.hr.employee",
  "attribute_name": "department",
  "relation": "viewer"
}
```

---

### 5.4. Revoke Row Filter Policy

**Prerequisites:** User must have been granted a row filter policy in section 5.1, 5.2, or 5.3.

**Note:** This is the recommended way to revoke row filter policies. The old `/permissions/revoke` endpoint with `relation="viewer"` is deprecated.

```bash
curl -X POST {{baseUrl}}/row-filter/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "user"
    },
    "attribute_name": "region",
    "allowed_values": []
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "hung",
  "policy_id": "user_region_filter",
  "object_id": "row_filter_policy:user_region_filter",
  "table_fqn": "lakekeeper_bronze.finance.user",
  "attribute_name": "region",
  "relation": "viewer"
}
```

**OpenFGA Tuples Deleted:**

1. `user:hung --viewer--> row_filter_policy:user_region_filter`
2. `table:lakekeeper_bronze.finance.user --applies_to--> row_filter_policy:user_region_filter`

**Note:** `allowed_values` can be empty for revoke (not used in deletion). The system uses `attribute_name` to build policy_id: `{table}_{attribute}_filter`.

---

### 5.5. List Row Filter Policies for User on Table

**Prerequisites:** User must have been granted row filter policies on the table.

**Note:** This endpoint returns all row filter policies that the user has access to on a specific table.

```bash
curl -X POST {{baseUrl}}/row-filter/list \
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
  "user_id": "hung",
  "table_fqn": "lakekeeper_bronze.finance.user",
  "policies": [
    {
      "policy_id": "user_region_filter",
      "attribute_name": "region",
      "allowed_values": ["north"]
    }
  ],
  "count": 1
}
```

**Explanation:**

- Queries OpenFGA for all row filter policies linked to the table
- Checks which policies the user has `viewer` access to
- Returns policy details including `attribute_name` and `allowed_values`

---

## 6. Column Mask Operations

This section covers dedicated endpoints for managing column mask permissions. These endpoints provide a cleaner API specifically designed for column masking operations.

### 6.1. Grant Column Mask Permission

**Prerequisites:** None

**Note:** This is the recommended way to grant column mask permissions. The old `/permissions/grant` endpoint with `relation="mask"` is deprecated.

```bash
curl -X POST {{baseUrl}}/column-mask/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "analyst",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "user",
      "column": "email"
    }
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "analyst",
  "column_id": "lakekeeper_bronze.finance.user.email",
  "object_id": "column:lakekeeper_bronze.finance.user.email",
  "relation": "mask"
}
```

**OpenFGA Tuple Created:**

- `user:analyst --mask--> column:lakekeeper_bronze.finance.user.email`

**Usage:** This marks the `email` column for masking when user `analyst` queries the table. The actual masking logic is handled by the policy engine.

---

### 6.2. Revoke Column Mask Permission

**Prerequisites:** User must have been granted column mask permission in section 6.1.

**Note:** This is the recommended way to revoke column mask permissions. The old `/permissions/revoke` endpoint with `relation="mask"` is deprecated.

```bash
curl -X POST {{baseUrl}}/column-mask/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "analyst",
    "resource": {
      "catalog": "lakekeeper_bronze",
      "schema": "finance",
      "table": "user",
      "column": "email"
    }
  }'
```

**Expected Response:**

```json
{
  "success": true,
  "user_id": "analyst",
  "column_id": "lakekeeper_bronze.finance.user.email",
  "object_id": "column:lakekeeper_bronze.finance.user.email",
  "relation": "mask"
}
```

**OpenFGA Tuple Deleted:**

- `user:analyst --mask--> column:lakekeeper_bronze.finance.user.email`

---

### 6.3. List Masked Columns for User on Table

**Prerequisites:** User must have been granted column mask permissions on columns in the table.

**Note:** This endpoint returns all columns that are masked for the user on a specific table.

```bash
curl -X POST {{baseUrl}}/column-mask/list \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "analyst",
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
  "user_id": "analyst",
  "table_fqn": "lakekeeper_bronze.finance.user",
  "masked_columns": ["email", "phone_number"],
  "count": 2
}
```

**Explanation:**

- Queries OpenFGA for all `mask` relation tuples for the user
- Filters columns that belong to the specified table
- Returns list of column names that are masked

---

## 7. Permission Revoke Operations

### 7.1. Revoke Catalog-Level Select Permission

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

### 7.2. Revoke CreateCatalog Permission (System-Level)

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

### 7.3. Revoke Schema-Level Select Permission

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

### 7.4. Revoke CreateSchema Permission (Catalog-Level)

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

### 7.5. Revoke CreateTable Permission (Schema-Level)

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

### 7.6. Revoke Table-Level Select Permission

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

### 7.7. Revoke Table-Level Modify Permission

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

### 7.8. Revoke Table-Level Describe Permission

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

### 7.9. Revoke Row Filter Permission (DEPRECATED - Use Section 5.4)

**Note:** Row filter permissions should now be revoked using the dedicated `/row-filter/revoke` endpoint (see Section 5.4). The old `/permissions/revoke` endpoint with `relation="viewer"` is deprecated but still supported for backward compatibility.

---

### 7.10. Revoke Manage Grants Permission

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

### 7.11. Revoke Column Mask Permission (DEPRECATED - Use Section 6.2)

**Note:** Column mask permissions should now be revoked using the dedicated `/column-mask/revoke` endpoint (see Section 6.2). The old `/permissions/revoke` endpoint with `relation="mask"` is deprecated but still supported for backward compatibility.

---

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

## 9. Database Verification

### 9.1. Check Tuples After Grant

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

### 9.2. Check Row Filter Policy Tuples

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

### 9.3. Check Tuples After Revoke

```sql
-- Verify tuples are deleted after revoke
SELECT _user, user_type, relation, object_type, object_id, condition_name
FROM tuple
WHERE _user = 'user:hung' OR object_id LIKE '%user_region%';

-- Expected after row filter revoke: (both rows deleted)
-- (empty result set)
```

---

### 9.4. Count Tuples by User

```sql
-- Count total tuples per user
SELECT _user, COUNT(*) as tuple_count
FROM tuple
WHERE user_type = 'user'
GROUP BY _user
ORDER BY tuple_count DESC;
```

---

### 9.5. Count Tuples by Resource Type

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
| Row filter      | 2 (user→policy + table→policy) | `catalog`, `schema`, `table`, `attribute_name`, `allowed_values` (use `/row-filter/grant`) |
| Column mask     | 1 (user→column)                | `catalog`, `schema`, `table`, `column` (use `/column-mask/grant`) |

### Revoke Operations

| Permission Type | Tuples Deleted                 | Extra Info Required                |
| --------------- | ------------------------------ | ---------------------------------- |
| Catalog-level   | 1 (user→catalog)               | None                               |
| Schema-level    | 1 (user→schema)                | None                               |
| Table-level     | 1 (user→table)                 | None                               |
| Row filter      | 2 (user→policy + table→policy) | `attribute_name` (use `/row-filter/revoke`) |
| Column mask     | 1 (user→column)                | None (use `/column-mask/revoke`) |

### Supported Relations

- **select**: Read-only access to data (`SELECT` queries)
- **modify**: Write/update access to data (`INSERT`, `UPDATE`, `DELETE`, `DROP`, etc.)
- **create**: Create new resources (`CREATE TABLE`, `CREATE SCHEMA`, etc.)
- **describe**: View metadata (`SHOW TABLES`, `SHOW COLUMNS`, etc.)
- **manage_grants**: Manage permissions on resources
- **viewer**: Row filter policy viewer (with condition context) - use `/row-filter/grant` endpoint
- **mask**: Column masking - use `/column-mask/grant` endpoint

### Key Features

1. **Hierarchical Permissions**: Schema-level permissions apply to all tables in the schema; catalog-level permissions apply to all schemas and tables.
2. **Row Filter Policies**: Support for attribute-based row filtering with condition contexts.
3. **Multiple Filters**: Multiple row filter policies are combined with AND logic.
4. **Fail-Closed**: Row filter endpoint fails closed (deny all) on errors or invalid input.
5. **Idempotent Operations**: Revoke operations are idempotent - revoking non-existent permissions succeeds.

---

## Quick Reference

### All Endpoints

| Method | Endpoint                  | Purpose                                    |
| ------ | ------------------------- | ------------------------------------------ |
| GET    | `/health`                 | Health check                               |
| POST   | `/permissions/grant`      | Grant permission to user (regular)         |
| POST   | `/permissions/revoke`     | Revoke permission from user (regular)      |
| POST   | `/permissions/check`      | Check if user has permission               |
| POST   | `/row-filter/query`       | Get row filter SQL for user on table       |
| POST   | `/row-filter/grant`       | Grant row filter policy to user            |
| POST   | `/row-filter/revoke`      | Revoke row filter policy from user         |
| POST   | `/row-filter/list`        | List row filter policies for user on table |
| POST   | `/column-mask/grant`      | Grant column mask permission to user       |
| POST   | `/column-mask/revoke`     | Revoke column mask permission from user    |
| POST   | `/column-mask/list`       | List masked columns for user on table      |

### Common Test Flow

1. **Grant permission** → `/permissions/grant` (regular permissions) or `/row-filter/grant` (row filters) or `/column-mask/grant` (column masks)
2. **Check permission** → `/permissions/check` (verify granted)
3. **Get row filter SQL** → `/row-filter/query` (if applicable)
4. **List policies/masks** → `/row-filter/list` or `/column-mask/list` (if applicable)
5. **Revoke permission** → `/permissions/revoke` (regular) or `/row-filter/revoke` (row filters) or `/column-mask/revoke` (column masks)
6. **Check permission again** → `/permissions/check` (verify revoked)
7. **Verify in database** → Query `tuple` table

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
