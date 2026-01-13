# Permission Management API

Authorization service for Lakekeeper resources using OpenFGA.

## Architecture

```
Trino → OPA → Permission API → OpenFGA
```

## Features

- **Permission Check** (`POST /api/v1/permissions/check`) - Validate user permissions (called by OPA)
- **Grant Permission** (`POST /api/v1/permissions/grant`) - Grant permissions to users
- **Revoke Permission** (`POST /api/v1/permissions/revoke`) - Revoke permissions from users
- **Column Masking** - Support mask/unmask permissions on columns
- **Auto Setup** - Automatically creates OpenFGA store and authorization model on startup

## Architecture

This project follows a **layered architecture** pattern with clear separation of concerns:

```
permission-api/
├── app/
│   ├── main.py                      # Application entry point
│   ├── api/                         # API routes layer
│   │   └── v1/
│   │       ├── api.py               # Router aggregator
│   │       └── endpoints/           # API endpoints
│   │           ├── health.py        # Health check
│   │           └── permissions.py   # Permission management
│   ├── core/                        # Core configuration
│   │   ├── config.py                # Settings
│   │   └── logging.py               # Logging setup
│   ├── schemas/                     # Pydantic models (DTOs)
│   │   ├── permission.py
│   │   └── health.py
│   ├── services/                    # Business logic
│   │   └── permission_service.py
│   ├── external/                    # External services
│   │   └── openfga_client.py        # OpenFGA client
│   ├── utils/                       # Utilities
│   │   ├── operation_mapper.py      # Trino → OpenFGA mapping
│   │   └── resource_builder.py     # Object ID builder
│   └── dependencies.py              # Shared dependencies
├── openfga/
│   └── auth_model.fga               # OpenFGA authorization model
├── requirements.txt
└── docker-compose-rbac-api.yaml
```

### Layers:

- **API Layer**: Handles HTTP requests/responses, validation
- **Service Layer**: Contains business logic
- **External Layer**: Integration with external services (OpenFGA)
- **Core Layer**: Configuration and shared utilities

## Configuration

Configuration is managed through environment variables. You can set them directly or use a `.env` file.

### Environment Variables

| Variable           | Default               | Description                    |
| ------------------ | --------------------- | ------------------------------ |
| `OPENFGA_API_URL`  | http://openfga-2:8080 | OpenFGA API endpoint           |
| `OPENFGA_STORE_ID` | Auto-discovered       | OpenFGA store ID               |
| `OPENFGA_TIMEOUT`  | 5s                    | OpenFGA request timeout        |
| `HOST`             | 0.0.0.0               | Service host                   |
| `PORT`             | 8000                  | Service port                   |
| `LOG_LEVEL`        | INFO                  | Logging level (DEBUG/INFO/etc) |

### Setup .env file

Copy the example file and customize:

```bash
cp .env.example .env
# Edit .env with your configuration
```

Example `.env`:

```bash
# OpenFGA Configuration
OPENFGA_API_URL=http://openfga-2:8080
OPENFGA_STORE_ID=

# Server Configuration
HOST=0.0.0.0
PORT=8000

# API Configuration
OPENFGA_TIMEOUT=5s

# Logging
LOG_LEVEL=INFO
```

## API Endpoints

All endpoints are prefixed with `/api/v1`.

### Health

```bash
GET /api/v1/health
```

### Permissions

```bash
# Check permission (called by OPA)
POST /api/v1/permissions/check
{
  "user_id": "admin",
  "resource": {
    "catalog": "lakekeeper",
    "schema": "finance",
    "table": "user"
  },
  "operation": "SelectFromColumns"
}

# Grant permission
POST /api/v1/permissions/grant
{
  "user_id": "admin",
  "resource": {
    "catalog": "lakekeeper",
    "schema": "finance",
    "table": "user"
  },
  "relation": "select"
}

# Grant column mask permission
POST /api/v1/permissions/grant
{
  "user_id": "admin",
  "resource": {
    "catalog": "lakekeeper",
    "schema": "finance",
    "table": "user",
    "column": "phone_number"
  },
  "relation": "mask"
}

# Revoke permission
POST /api/v1/permissions/revoke
{
  "user_id": "admin",
  "resource": {
    "catalog": "lakekeeper",
    "schema": "finance",
    "table": "user"
  },
  "relation": "select"
}
```

## Object Format

OpenFGA object IDs:

- **Catalog**: `catalog:<catalog_name>`
- **Namespace**: `namespace:<catalog>.<schema>`
- **Table**: `table:<catalog>.<schema>.<table>`
- **Column**: `column:<catalog>.<schema>.<table>.<column>`

## Operation Mapping

Trino operations map to OpenFGA relations:

| Trino Operation    | OpenFGA Relation |
| ------------------ | ---------------- |
| SelectFromColumns  | select           |
| InsertIntoTable    | modify           |
| UpdateTableColumns | modify           |
| DeleteFromTable    | modify           |
| CreateTable        | create           |
| DropTable          | modify           |
| FilterTables       | describe         |
| FilterSchemas      | describe         |
| MaskColumn         | mask             |

See `operation_mapper.py` for complete mapping.

## Development

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your configuration
```

### Run Locally

```bash
# Run with Python
python -m app.main

# Or with uvicorn (with auto-reload)
uvicorn app.main:app --reload
```

### Run with Docker Compose

```bash
# Start all services (OpenFGA + Permission API)
docker-compose -f docker-compose-rbac-api.yaml up -d

# View logs
docker-compose -f docker-compose-rbac-api.yaml logs -f permission-api

# Stop services
docker-compose -f docker-compose-rbac-api.yaml down
```

### Automatic Initialization

On startup, the application automatically:

1. **Checks for OpenFGA store** - Creates one if it doesn't exist
2. **Loads authorization model** - Applies the model from `openfga/auth_model.fga` if not already present
3. **Initializes client** - Connects to OpenFGA for permission operations

No manual setup required! Just start the application and it will configure everything automatically.

## Integration with OPA

OPA calls `/api/v1/permissions/check` via `rbac.call_permission_check()`:

```rego
# opa/policies/rbac/authentication.rego
call_permission_check(user_id, resource, operation) := response if {
    response := http.send({
        "method": "POST",
        "url": sprintf("%s/api/v1/permissions/check", [configuration.permission_api_url]),
        "body": {
            "user_id": user_id,
            "resource": resource,
            "operation": operation
        }
    })
}
```

Column masking: OPA calls check với `operation="MaskColumn"` để xác định cột nào cần mask.
