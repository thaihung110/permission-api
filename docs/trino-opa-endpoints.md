# Trino OPA Compatible Endpoints

## Overview

The permission-api now provides endpoints that are compatible with Trino's OPA access control plugin. This allows Trino to use our permission-api directly without requiring a separate OPA server.

## Configuration

### Trino Configuration

Update your Trino `access-control.properties`:

```properties
access-control.name=opa
opa.policy.uri=http://permission-api:8000/api/v1/allow
opa.policy.batched-uri=http://permission-api:8000/api/v1/batch
opa.log-requests=true
opa.log-responses=true
```

Replace `permission-api:8000` with your actual permission-api host and port.

## Endpoints

### Single Permission Check

**Endpoint:** `POST /api/v1/allow`

This endpoint handles individual permission checks from Trino.

**Request Format:**

```json
{
  "input": {
    "context": {
      "identity": {
        "user": "alice",
        "groups": ["analysts"]
      },
      "softwareStack": {
        "trinoVersion": "476"
      }
    },
    "action": {
      "operation": "SelectFromColumns",
      "resource": {
        "table": {
          "catalogName": "lakekeeper",
          "schemaName": "finance",
          "tableName": "user",
          "columns": ["id", "name", "email"]
        }
      }
    }
  }
}
```

**Response Format:**

```json
{
  "result": true
}
```

### Batch Permission Check

**Endpoint:** `POST /api/v1/batch`

This endpoint handles batch permission checks for filtering resources (catalogs, schemas, tables, columns).

**Request Format:**

```json
{
  "input": {
    "context": {
      "identity": {
        "user": "alice",
        "groups": []
      },
      "softwareStack": {
        "trinoVersion": "476"
      }
    },
    "action": {
      "operation": "FilterCatalogs",
      "filterResources": [
        { "resource": { "catalog": { "name": "lakekeeper" } } },
        { "resource": { "catalog": { "name": "system" } } },
        { "resource": { "catalog": { "name": "private_catalog" } } }
      ]
    }
  }
}
```

**Response Format:**

```json
{
  "result": [0, 1]
}
```

The `result` array contains the indices of resources that are allowed. In this example, indices 0 and 1 are allowed, while index 2 is denied.

## Supported Operations

### Always Allowed Operations

The following operations are always allowed (no permission check required):

- `ExecuteQuery`
- `ExecuteTableProcedure`
- `ReadSystemInformation`
- `WriteSystemInformation`
- `SetCatalogSessionProperty`
- `SetSystemSessionProperty`
- `ImpersonateUser`
- `ViewQueryOwnedBy`
- `KillQueryOwnedBy`
- `ExecuteFunction`

### Catalog Operations

| Operation        | Resource Type | Description             |
| ---------------- | ------------- | ----------------------- |
| `AccessCatalog`  | catalog       | Access a catalog        |
| `CreateCatalog`  | system        | Create a new catalog    |
| `DropCatalog`    | catalog       | Drop a catalog          |
| `FilterCatalogs` | catalog[]     | Filter visible catalogs |

### Schema Operations

| Operation       | Resource Type | Description                  |
| --------------- | ------------- | ---------------------------- |
| `ShowSchemas`   | catalog       | List schemas in a catalog    |
| `CreateSchema`  | catalog       | Create a schema in a catalog |
| `DropSchema`    | schema        | Drop a schema                |
| `RenameSchema`  | schema        | Rename a schema              |
| `FilterSchemas` | schema[]      | Filter visible schemas       |

### Table Operations

| Operation            | Resource Type | Description                |
| -------------------- | ------------- | -------------------------- |
| `ShowTables`         | schema        | List tables in a schema    |
| `CreateTable`        | schema        | Create a table in a schema |
| `DropTable`          | table         | Drop a table               |
| `RenameTable`        | table         | Rename a table             |
| `SelectFromColumns`  | table         | Read data from table       |
| `InsertIntoTable`    | table         | Insert data into table     |
| `DeleteFromTable`    | table         | Delete data from table     |
| `UpdateTableColumns` | table         | Update data in table       |
| `FilterTables`       | table[]       | Filter visible tables      |

### Column Operations

| Operation       | Resource Type | Description                |
| --------------- | ------------- | -------------------------- |
| `ShowColumns`   | table         | List columns in a table    |
| `AddColumn`     | table         | Add a column to a table    |
| `DropColumn`    | table         | Drop a column from a table |
| `RenameColumn`  | table         | Rename a column            |
| `FilterColumns` | column[]      | Filter visible columns     |

## Resource Format Mapping

The endpoint automatically converts between Trino's resource format and our internal format:

### Trino Format → Internal Format

| Trino Resource                                                         | Internal Resource                               |
| ---------------------------------------------------------------------- | ----------------------------------------------- |
| `{"catalog": {"name": "X"}}`                                           | `{"catalog": "X"}`                              |
| `{"schema": {"catalogName": "X", "schemaName": "Y"}}`                  | `{"catalog": "X", "schema": "Y"}`               |
| `{"table": {"catalogName": "X", "schemaName": "Y", "tableName": "Z"}}` | `{"catalog": "X", "schema": "Y", "table": "Z"}` |

## Internal to OpenFGA Mapping

The internal resource format is then mapped to OpenFGA v3 types:

| Internal Type | OpenFGA v3 Type          |
| ------------- | ------------------------ |
| `catalog:X`   | `warehouse:X`            |
| `schema:X.Y`  | `namespace:X.Y`          |
| `table:X.Y.Z` | `lakekeeper_table:X.Y.Z` |

## Error Handling

- If an error occurs during permission checking, the endpoint returns `{"result": false}` (fail closed)
- For batch operations, resources that cause errors are excluded from the allowed list
- All errors are logged for debugging

## Logging

Enable debug logging to see detailed permission check information:

```python
logging.getLogger("app.api.v1.endpoints.trino_opa").setLevel(logging.DEBUG)
```
