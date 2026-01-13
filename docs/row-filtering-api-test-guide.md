## Hướng dẫn test API row filter (ngắn gọn)

### 1. Chuẩn bị

- **Giả định**: OpenFGA, Permission API, OPA, Trino đã chạy đúng cấu hình.
- Có sẵn tuples OpenFGA cho user và policy (ví dụ `customers_region_filter`).

---

### 2. Test trực tiếp Permission API

**Request:**

```bash
curl -X POST http://localhost:8001/permissions/row-filter \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hung",
    "resource": {
      "catalog_name": "lakekeeper_bronze",
      "schema_name": "finance",
      "table_name": "users"
    }
  }'
```

**Kỳ vọng (user có quyền một region):**

```json
{
  "filter_expression": "region IN ('mien_bac')",
  "has_filter": true
}
```

**Các case cần thử nhanh:**

- User `sale_nam`: trả về `region IN (...)` (có filter).
- User `manager`: nhiều giá trị `region IN ('mien_bac', 'mien_trung', 'mien_nam')`.
- User `admin` (wildcard `*`): `filter_expression: null`, `has_filter: false`.
- User không có tuple: `filter_expression: "1=0"`, `has_filter: true`.

---

### 3. Test OPA rowFilters (bỏ qua Trino)

```bash
curl -X POST http://localhost:8181/v1/data/trino/rowFilters \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "action": {
        "operation": "SelectFromColumns"
      },
      "resource": {
        "table": {
          "catalogName": "prod",
          "schemaName": "public",
          "tableName": "customers"
        }
      },
      "context": {
        "identity": {
          "user": "sale_nam"
        }
      }
    }
  }'
```

**Kỳ vọng:**

```json
{
  "result": {
    "rowFilters": [
      {
        "expression": "region IN ('mien_bac')"
      }
    ]
  }
}
```

Các case tương tự mục 2 (wildcard, deny all) để đảm bảo format `rowFilters` đúng.

---

### 4. Test end-to-end trong Trino

Trong Trino CLI (hoặc client JDBC) login với user mapping tương ứng (`sale_nam`):

```sql
-- User sale_nam
SELECT * FROM prod.public.customers;
```

**Kỳ vọng nội bộ:**

- Trino rewrite: `SELECT * FROM prod.public.customers WHERE region IN ('mien_bac')`.
- Kết quả chỉ bao gồm rows có `region = 'mien_bac'`.

Có thể test thêm:

```sql
SELECT region, count(*)
FROM prod.public.customers
GROUP BY region;
```

**Kỳ vọng:** chỉ thấy các region user được phép.

---

### 5. Nhanh kiểm tra lỗi

- Nếu Permission API trả `1=0` → check tuples OpenFGA của user/policy.
- Nếu OPA không trả `rowFilters` → kiểm tra `policies/trino/row_filters.rego` và logs OPA.
- Nếu Trino không filter → kiểm tra `opa.policy.row-filters-uri` trong `trino/etc/access-control.properties`.
