# Row Filtering Implementation Summary

## 📋 Tổng quan

Đã implement row filtering cho Trino sử dụng OpenFGA, Permission API và OPA. Row filtering cho phép Trino tự động áp dụng WHERE clause dựa trên permissions của user được lưu trong OpenFGA.

---

## 🔧 Các thay đổi chính

### 1. Permission API

**Files mới:**

- `app/schemas/row_filter.py` - Schemas cho row filter request/response
- `app/services/row_filter_service.py` - Service xây dựng SQL filters từ OpenFGA
- `app/api/v1/endpoints/row_filter.py` - Endpoint `/permissions/row-filter`

**Files sửa:**

- `app/external/openfga_client.py` - Thêm method `read_tuples()` để đọc tuples với condition context
- `app/api/v1/api.py` - Register row filter router

**Chức năng:**

- Query OpenFGA để lấy policies áp dụng cho table
- Đọc condition context từ tuples (deserialized từ bytea)
- Parse column name từ policy*id naming convention: `{table}*{column}\_filter`
- Build SQL WHERE clause: `column IN ('value1', 'value2')`
- Hỗ trợ multiple policies (AND logic)
- Hỗ trợ wildcard (`*` = no filter)

### 2. OPA Policy

**File mới:**

- `policies/trino/row_filters.rego` - Policy trả về row filters cho Trino

**Chức năng:**

- Gọi Permission API để lấy filter expression
- Trả về format đúng theo Trino: `[{"expression": "clause"}]`
- Endpoint: `/v1/data/trino/rowFilters`

### 3. Trino Configuration

**File sửa:**

- `trino/etc/access-control.properties`

**Thay đổi:**

```properties
opa.policy.row-filters-uri=http://opa:8181/v1/data/trino/rowFilters
```

---

## 🔄 Flow

```
User Query (Trino)
    ↓
Trino → OPA: POST /v1/data/trino/rowFilters
    ↓
OPA → Permission API: POST /permissions/row-filter
    ↓
Permission API → OpenFGA: Read tuples with condition context
    ↓
Permission API builds SQL: "region IN ('mien_bac')"
    ↓
OPA → Trino: {"rowFilters": [{"expression": "..."}]}
    ↓
Trino applies WHERE clause automatically
```

---

## 📝 Key Points

1. **No Database**: Permission API chỉ sử dụng OpenFGA, không có database riêng
2. **Condition Context**: Lưu dạng bytea trong OpenFGA, SDK tự deserialize
3. **Column Mapping**: Parse từ policy_id: `customers_region_filter` → `region`
4. **Format**: OPA trả về array of objects với `"expression"` field
5. **Fail Closed**: Trả về `"1=0"` nếu có lỗi hoặc unauthorized

---

## ✅ Testing

**Test Permission API:**

```bash
curl -X POST http://localhost:8000/permissions/row-filter \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "sale_nam",
    "resource": {
      "catalog_name": "prod",
      "schema_name": "public",
      "table_name": "customers"
    }
  }'
```

**Expected Response:**

```json
{
  "filter_expression": "region IN ('mien_bac')",
  "has_filter": true
}
```

**Test OPA:**

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

**Expected Response:**

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

---

## 📚 Tài liệu liên quan

- `docs/row-filtering-trino-flow.md` - Chi tiết flow và examples
- `docs/row-filtering-final-design.md` - Design và OpenFGA model
- `docs/trino-row-filtering-configuration.md` - Hướng dẫn cấu hình
- `docs/row-filtering-response-format.md` - Format verification

---

**Status:** ✅ Hoàn thành - Sẵn sàng để test và deploy
