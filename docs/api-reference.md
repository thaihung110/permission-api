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

**Endpoint:** `GET /api/v1/lakekeeper/list-resources`

List all resources (warehouses, namespaces, tables) with user permissions, column masks, and row filters.

**Query Parameters:**

- `user_id`: User ID (e.g., "analyst")
- `catalog`: Trino catalog name (e.g., "lakekeeper_demo")

**Example:**

```
GET /api/v1/lakekeeper/list-resources?user_id=analyst&catalog=lakekeeper_demo
```

**Response:**

```json
{
  "name": "lakekeeper_demo",
  "permissions": ["select", "describe"],
  "namespaces": [
    {
      "name": "finance",
      "permissions": ["select", "modify"],
      "tables": [
        {
          "name": "user",
          "permissions": ["select"],
          "columns": [
            { "name": "id", "masked": false },
            { "name": "name", "masked": false },
            { "name": "phone_number", "masked": true },
            { "name": "email", "masked": true },
            { "name": "region", "masked": false }
          ],
          "row_filters": [
            {
              "attribute_name": "region",
              "filter_expression": "region IN ('north', 'south')"
            }
          ]
        }
      ]
    }
  ],
  "errors": null
}
```

**Response Structure:**

- **Warehouse level**: name + permissions + list of namespaces
- **Namespace level**: name + permissions + list of tables
- **Table level**: name (table name) + permissions + columns + row_filters
- **Column**: name + masked status
- **Row Filter**: attribute_name + filter_expression

---

## Tenant Management APIs

### 1. Add User to Tenant

**Endpoint:** `POST /api/v1/permissions/grant`

Add a user as member of a tenant. Once added, user inherits all permissions granted to `tenant#member`.

**Request:**

```json
{
  "user_id": "cfb55bf6-fcbb-4a1e-bfec-30c6649b52f8",
  "user_type": "user",
  "resource": {
    "tenant": "viettel"
  },
  "relation": "member"
}
```

**Response:**

```json
{
  "success": true,
  "message": "Permission granted successfully"
}
```

### 2. Remove User from Tenant

**Endpoint:** `POST /api/v1/permissions/revoke`

Remove a user from tenant membership.

**Request:**

```json
{
  "user_id": "cfb55bf6-fcbb-4a1e-bfec-30c6649b52f8",
  "user_type": "user",
  "resource": {
    "tenant": "viettel"
  },
  "relation": "member"
}
```

**Response:**

```json
{
  "success": true,
  "message": "Permission revoked successfully"
}
```

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
