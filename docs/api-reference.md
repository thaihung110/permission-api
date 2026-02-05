# Permission API Reference

API endpoints for row filtering, column masking, and resource listing.

---

## Row Filter APIs

### 1. Query Row Filters (Trino Integration)

**Endpoint:** `POST /api/v1/row-filter/query`

Query row filter policies for a table. Returns SQL WHERE clause expressions.

**Request:**

```json
{
  "input": {
    "context": {
      "identity": {
        "user": "cfb55bf6-fcbb-4a1e-bfec-30c6649b52f8",
        "groups": ["viettel"]
      },
      "softwareStack": { "trinoVersion": "467" }
    },
    "action": {
      "operation": "GetRowFilters",
      "resource": {
        "table": {
          "catalogName": "lakekeeper_demo",
          "schemaName": "finance",
          "tableName": "user"
        }
      }
    }
  }
}
```

**Response:**

```json
{
  "result": [{ "expression": "region IN ('north', 'south')" }]
}
```

### 2. Grant Row Filter Policy

**Endpoint:** `POST /api/v1/row-filter/grant`

Grant row filter policy to user/role/tenant on a table.

**Request:**

```json
{
  "user_id": "cfb55bf6-fcbb-4a1e-bfec-30c6649b52f8",
  "user_type": "user",
  "resource": {
    "catalog": "lakekeeper_demo",
    "schema": "finance",
    "table": "user"
  },
  "attribute_name": "region",
  "allowed_values": ["north", "south"]
}
```

**Response:**

```json
{
  "success": true,
  "user_id": "cfb55bf6-fcbb-4a1e-bfec-30c6649b52f8",
  "policy_id": "lakekeeper_demo.finance.user.region",
  "attribute_name": "region"
}
```

### 3. Revoke Row Filter Policy

**Endpoint:** `POST /api/v1/row-filter/revoke`

Revoke row filter policy from user.

**Request/Response:** Same format as grant endpoint.

### 4. List Row Filter Policies

**Endpoint:** `POST /api/v1/row-filter/list`

List all row filter policies user has access to on a table.

**Request:**

```json
{
  "user_id": "cfb55bf6-fcbb-4a1e-bfec-30c6649b52f8",
  "resource": {
    "catalog_name": "lakekeeper_demo",
    "schema_name": "finance",
    "table_name": "user"
  }
}
```

**Response:**

```json
{
  "user_id": "cfb55bf6-fcbb-4a1e-bfec-30c6649b52f8",
  "table_fqn": "lakekeeper_demo.finance.user",
  "policies": [
    {
      "policy_id": "lakekeeper_demo.finance.user.region",
      "attribute_name": "region",
      "allowed_values": ["north", "south"]
    }
  ],
  "count": 1
}
```

---

## Column Mask APIs

### 1. Query Column Masks (Trino Integration)

**Endpoint:** `POST /api/v1/column-mask/query`

Batch check which columns need masking. Returns mask expressions for masked columns.

**Request:**

```json
{
  "input": {
    "context": {
      "identity": {
        "user": "cfb55bf6-fcbb-4a1e-bfec-30c6649b52f8",
        "groups": ["viettel"]
      },
      "softwareStack": { "trinoVersion": "467" }
    },
    "action": {
      "operation": "GetColumnMask",
      "filterResources": [
        {
          "column": {
            "catalogName": "lakekeeper_demo",
            "schemaName": "finance",
            "tableName": "user",
            "columnName": "phone_number",
            "columnType": "varchar"
          }
        },
        {
          "column": {
            "catalogName": "lakekeeper_demo",
            "schemaName": "finance",
            "tableName": "user",
            "columnName": "email",
            "columnType": "varchar"
          }
        }
      ]
    }
  }
}
```

**Response:**

```json
{
  "result": [
    {
      "index": 0,
      "viewExpression": { "expression": "******" }
    },
    {
      "index": 1,
      "viewExpression": { "expression": "******" }
    }
  ]
}
```

### 2. Grant Column Mask

**Endpoint:** `POST /api/v1/column-mask/grant`

Grant column mask permission to user/role/tenant on a column.

**Request:**

```json
{
  "user_id": "cfb55bf6-fcbb-4a1e-bfec-30c6649b52f8",
  "user_type": "user",
  "resource": {
    "catalog": "lakekeeper_demo",
    "schema": "finance",
    "table": "user",
    "column": "phone_number"
  }
}
```

**Response:**

```json
{
  "success": true,
  "user_id": "analyst",
  "column_id": "lakekeeper_demo.finance.user.phone_number",
  "relation": "mask"
}
```

### 3. Revoke Column Mask

**Endpoint:** `POST /api/v1/column-mask/revoke`

Revoke column mask permission from user.

**Request/Response:** Same format as grant endpoint.

### 4. List Masked Columns

**Endpoint:** `POST /api/v1/column-mask/list`

List all columns that are masked for a user on a table.

**Request:**

```json
{
  "user_id": "cfb55bf6-fcbb-4a1e-bfec-30c6649b52f8",
  "resource": {
    "catalog_name": "lakekeeper_demo",
    "schema_name": "finance",
    "table_name": "user"
  }
}
```

**Response:**

```json
{
  "user_id": "cfb55bf6-fcbb-4a1e-bfec-30c6649b52f8",
  "table_fqn": "lakekeeper_demo.finance.user",
  "masked_columns": ["phone_number", "email"],
  "count": 2
}
```

---

## List Resources API

### List Resources with Permissions

**Endpoint:** `POST /api/v1/lakekeeper/list-resources`

List all resources (warehouses, namespaces, tables, columns) in flat list format with permissions, column masks, and row filters.

**Request:**

```json
{
  "user_id": "cfb55bf6-fcbb-4a1e-bfec-30c6649b52f8",
  "catalog": "lakekeeper_demo"
}
```

**Response:**

```json
{
  "resources": [
    {
      "name": "lakekeeper_demo",
      "permissions": ["select", "describe"]
    },
    {
      "name": "lakekeeper_demo.finance",
      "permissions": ["select", "modify"]
    },
    {
      "name": "lakekeeper_demo.finance.user",
      "permissions": ["select"],
      "row_filters": [
        {
          "attribute_name": "region",
          "filter_expression": "region IN ('north', 'south')"
        }
      ]
    },
    {
      "name": "lakekeeper_demo.finance.user.id",
      "permissions": []
    },
    {
      "name": "lakekeeper_demo.finance.user.name",
      "permissions": []
    },
    {
      "name": "lakekeeper_demo.finance.user.phone_number",
      "permissions": ["mask"]
    },
    {
      "name": "lakekeeper_demo.finance.user.email",
      "permissions": ["mask"]
    },
    {
      "name": "lakekeeper_demo.finance.user.region",
      "permissions": []
    }
  ]
}
```

**Response Structure (Flat List):**

- Each resource: `name` (path) + `permissions` (array)
- **Resource naming:**
  - Warehouse: `catalog_name`
  - Namespace: `catalog_name.namespace_name`
  - Table: `catalog_name.namespace_name.table_name`
  - Column: `catalog_name.namespace_name.table_name.column_name`
- **Permissions:**
  - Warehouses/Namespaces/Tables: `["create", "modify", "select", "describe"]`
  - Columns: `["mask"]` if masked, `[]` if not masked
- **Row Filters:**
  - Field `row_filters` only appears on table items (when user has row filter policies)
  - Array of filter policies with `attribute_name` and `filter_expression`
- **Errors:**
  - Field `errors` only appears when there are errors during resource fetching

---

## Notes

### User Types

- `user`: Regular user (e.g., "alice")
- `userset`: Role or tenant (e.g., "role:Sales#assignee", "tenant:viettel#member")

### Tenant Support

- `groups` field in request maps to tenant IDs
- User must be verified member of tenant via OpenFGA
- Empty `groups` list = request rejected

### Permissions

Available permissions: `create`, `modify`, `select`, `describe`

### Wildcard Support

- Row filters: Use `["*"]` in `allowed_values` for no filtering
- Wildcard means user can see all rows (no filter applied)
