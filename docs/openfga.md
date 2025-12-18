# OpenFGA CLI Commands

## Cấu hình

```bash
# Set API URL
export FGA_API_URL=http://localhost:8085

# Hoặc set store_id cụ thể (nếu đã biết)
export FGA_STORE_ID=01K7JW3M6HNP3QR5HJRERDCAYR
```

## Xem Store ID

```bash
# Liệt kê tất cả stores
fga store list --api-url http://localhost:8085

# Xem thông tin store cụ thể
fga store get --store-id <STORE_ID> --api-url http://localhost:8085
```

## Xem Authorization Model

```bash
# Đọc model hiện tại trong store
fga model get --store-id <STORE_ID> --api-url http://localhost:8085

# Xem tất cả các version của model
fga model list --store-id <STORE_ID> --api-url http://localhost:8085

# Xem model version cụ thể
fga model get --store-id <STORE_ID> --api-url http://localhost:8085 --id <MODEL_ID>
```

## Submit Authorization Model

```bash
# Submit model từ file auth_model.fga vào store
fga model write --store-id <STORE_ID> --api-url http://localhost:8085 --file auth_model.fga

# Lấy MODEL_ID từ response, sau đó set làm default (dùng --id thay vì --store-id)
fga store update --id <STORE_ID> --api-url http://localhost:8085 --default-model-id <MODEL_ID>

# Hoặc nếu đã set FGA_STORE_ID và FGA_API_URL
fga model write --file auth_model.fga
# Lấy MODEL_ID từ output, rồi:
fga store update --id $FGA_STORE_ID --default-model-id <MODEL_ID>
```

## Lệnh nhanh (với store_id mặc định)

```bash
# Nếu đã set FGA_STORE_ID trong environment
fga store list
```

## Dựng OpenFGA server riêng (docker-compose-openfga.yaml)

```bash
# Start OpenFGA + Postgres riêng
docker compose -f docker-compose-openfga.yaml up -d

# API URL của server mới
export FGA_API_URL=http://localhost:8085
```

## Tạo store và apply auth_model.fga

```bash
# 1) Tạo store mới
fga store create --name lakehouse-permission --api-url $FGA_API_URL
# Lấy STORE_ID từ output

# 2) Ghi model từ file auth_model.fga
fga model write --store-id <STORE_ID> --api-url $FGA_API_URL --file auth_model.fga
# Lấy MODEL_ID (authorization_model_id) từ output

# 3) Set model đó làm default cho store
fga store update --id <STORE_ID> --api-url $FGA_API_URL --default-model-id <MODEL_ID>
```

## Check quyền

```bash
fga query check --store-id $STORE_ID user:admin select table:lakekeeper.finance.user
```

# OPA (Open Policy Agent)

OPA xử lý authorization cho Trino queries, gọi permission-api để kiểm tra quyền qua OpenFGA.

## Policy Structure

```
opa/policies/
├── rbac/
│   ├── authentication.rego  # HTTP client cho permission-api
│   └── check.rego            # RBAC check logic
├── trino/
│   ├── main.rego             # Entry point
│   ├── allow_schema.rego     # Schema-level rules
│   ├── allow_system.rego     # System catalog & information_schema
│   ├── column_mask.rego      # Column masking (batch GetColumnMask)
│   └── batch.rego             # Batch operations
└── configuration.rego         # Config (permission-api URL, timeout)
```

## Column Masking

Policy `column_mask.rego` xử lý batch column masking:

- Mặc định: unmask (không mask)
- Chỉ mask khi có tuple `mask` trong OpenFGA (checked qua permission-api)
- Operation: `GetColumnMask` với `filterResources[]`

# Permission API

Service quản lý quyền cho Trino resources qua OpenFGA.

## API Endpoints

- `POST /permissions/check` - Kiểm tra quyền (gọi bởi OPA)
- `POST /permissions/grant` - Cấp quyền
- `POST /permissions/revoke` - Thu hồi quyền
- `GET /health` - Health check

## Object Format

- Catalog: `catalog:<catalog_name>`
- Namespace: `namespace:<catalog>.<schema>`
- Table: `table:<catalog>.<schema>.<table>`
- Column: `column:<catalog>.<schema>.<table>.<column>`

## Example

```bash
# Grant select permission on table
POST /permissions/grant
{
  "user_id": "admin",
  "resource": {
    "catalog": "lakekeeper",
    "schema": "finance",
    "table": "user"
  },
  "relation": "select"
}

# Grant mask permission on column
POST /permissions/grant
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
```

Xem chi tiết: [permission-api/README.md](permission-api/README.md)

## Lưu ý

- OpenFGA API mặc định của stack chính chạy trên `http://localhost:8080`.
- OpenFGA API của server riêng trong `docker-compose-openfga.yaml` chạy trên `http://localhost:8085`.
