# Hướng dẫn Grant Permission với Condition Context

## 📋 Tổng quan

Permission API đã hỗ trợ grant permission với **condition context** cho row filtering. Điều này cho phép bạn tạo tuples trong OpenFGA với condition context (như `has_attribute_access`) để áp dụng row filtering cho Trino.

---

## 🔧 API Endpoint

**Endpoint:** `POST /api/v1/permissions/grant`

**Request Body:**

```json
{
  "user_id": "sale_nam",
  "resource": {
    "catalog": "lakekeeper_bronze",
    "schema": "finance",
    "table": "customers"
  },
  "relation": "viewer",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "attribute_name": "region",
      "allowed_values": ["mien_bac"]
    }
  }
}
```

---

## 📝 Request Schema

### PermissionGrant

| Field       | Type          | Required | Description                                     |
| ----------- | ------------- | -------- | ----------------------------------------------- |
| `user_id`   | string        | ✅       | User identifier (e.g., "sale_nam", "hung")      |
| `resource`  | ResourceSpec  | ✅       | Resource specification (catalog, schema, table) |
| `relation`  | string        | ✅       | Relation/permission (e.g., "viewer", "select")  |
| `condition` | ConditionSpec | ❌       | Optional condition context for row filtering    |

### ConditionSpec

| Field     | Type             | Required | Description                                   |
| --------- | ---------------- | -------- | --------------------------------------------- |
| `name`    | string           | ✅       | Condition name (e.g., "has_attribute_access") |
| `context` | ConditionContext | ✅       | Condition context with attribute details      |

### ConditionContext

| Field            | Type     | Required | Description                                               |
| ---------------- | -------- | -------- | --------------------------------------------------------- |
| `attribute_name` | string   | ✅       | Attribute name (e.g., "region", "department")             |
| `allowed_values` | string[] | ✅       | List of allowed values (e.g., ["mien_bac", "mien_trung"]) |

---

## 🎯 Use Cases

### 1. Grant Row Filter Policy với Condition Context

**Scenario:** User `sale_nam` chỉ được xem customers có `region = 'mien_bac'`

**Request:**

```bash
curl -X POST http://localhost:8000/api/v1/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "sale_nam",
    "resource": {},
    "relation": "viewer",
    "condition": {
      "name": "has_attribute_access",
      "context": {
        "attribute_name": "region",
        "allowed_values": ["mien_bac"]
      }
    }
  }'
```

**Note:** Với row filter policy, `resource` có thể rỗng `{}` vì object_id sẽ là `row_filter_policy:customers_region_filter` (cần tạo policy trước).

**OpenFGA Tuple được tạo:**

```
user:sale_nam viewer row_filter_policy:customers_region_filter
Condition: has_attribute_access
Context: {
  "attribute_name": "region",
  "allowed_values": ["mien_bac"]
}
```

---

### 2. Grant với Multiple Allowed Values

**Scenario:** User `manager` được xem customers ở nhiều regions

**Request:**

```bash
curl -X POST http://localhost:8000/api/v1/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "manager",
    "resource": {},
    "relation": "viewer",
    "condition": {
      "name": "has_attribute_access",
      "context": {
        "attribute_name": "region",
        "allowed_values": ["mien_bac", "mien_trung", "mien_nam"]
      }
    }
  }'
```

**Result:** User `manager` có thể xem customers ở cả 3 regions.

---

### 3. Grant với Wildcard (Full Access)

**Scenario:** User `admin` có full access (không filter)

**Request:**

```bash
curl -X POST http://localhost:8000/api/v1/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "admin",
    "resource": {},
    "relation": "viewer",
    "condition": {
      "name": "has_attribute_access",
      "context": {
        "attribute_name": "region",
        "allowed_values": ["*"]
      }
    }
  }'
```

**Result:** Permission API sẽ detect wildcard `*` và không áp dụng filter (trả về `filter_expression: null`).

---

### 4. Grant Permission Thông Thường (Không có Condition)

**Scenario:** Grant permission bình thường không có row filtering

**Request:**

```bash
curl -X POST http://localhost:8000/api/v1/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "alice",
    "resource": {
      "catalog": "lakekeeper_bronze"
    },
    "relation": "select"
  }'
```

**Result:** Tạo tuple đơn giản không có condition context.

---

## 🔄 Complete Flow: Setup Row Filtering

### Step 1: Tạo Policy Link với Table

Trước tiên, cần tạo tuple link policy với table:

```bash
# Link policy với table
curl -X POST http://localhost:8000/api/v1/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user": "table:lakekeeper_bronze.finance.customers",
    "relation": "applies_to",
    "object": "row_filter_policy:customers_region_filter"
  }'
```

**Note:** Hiện tại endpoint `/permissions/grant` không hỗ trợ trực tiếp format này. Bạn cần dùng OpenFGA API trực tiếp hoặc implement admin endpoint.

**Alternative:** Dùng OpenFGA API trực tiếp:

```bash
curl -X POST http://localhost:8080/stores/{store_id}/write \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{
    "writes": {
      "tuple_keys": [
        {
          "user": "table:lakekeeper_bronze.finance.customers",
          "relation": "applies_to",
          "object": "row_filter_policy:customers_region_filter"
        }
      ]
    }
  }'
```

### Step 2: Grant User Access với Condition Context

Sau khi có policy link, grant user access với condition:

```bash
curl -X POST http://localhost:8000/api/v1/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "sale_nam",
    "resource": {},
    "relation": "viewer",
    "condition": {
      "name": "has_attribute_access",
      "context": {
        "attribute_name": "region",
        "allowed_values": ["mien_bac"]
      }
    }
  }'
```

**Note:** Với row filter policy, bạn cần build object_id là `row_filter_policy:customers_region_filter`. Hiện tại endpoint tự động build từ resource, nên bạn cần sửa logic hoặc dùng OpenFGA API trực tiếp.

---

## ⚠️ Limitations Hiện Tại

1. **Row Filter Policy Object ID:** Endpoint `/permissions/grant` tự động build object_id từ resource (catalog, schema, table). Với row filter policy, object_id cần là `row_filter_policy:{policy_id}`, không phải từ resource.

2. **Workaround:**
   - Dùng OpenFGA API trực tiếp để tạo tuple với object_id là `row_filter_policy:...`
   - Hoặc implement admin endpoint riêng cho row filter policies

---

## ✅ Response Format

**Success Response:**

```json
{
  "success": true,
  "user_id": "sale_nam",
  "resource_type": "row_filter_policy",
  "resource_id": "customers_region_filter",
  "object_id": "row_filter_policy:customers_region_filter",
  "relation": "viewer"
}
```

**Error Response:**

```json
{
  "detail": "Error message here"
}
```

---

## 🧪 Testing

### Test 1: Grant với Condition Context

```bash
# Grant permission với condition
curl -X POST http://localhost:8000/api/v1/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "resource": {
      "catalog": "test_catalog"
    },
    "relation": "select",
    "condition": {
      "name": "has_attribute_access",
      "context": {
        "attribute_name": "region",
        "allowed_values": ["mien_bac"]
      }
    }
  }'
```

### Test 2: Verify Tuple trong OpenFGA

```bash
# Read tuples để verify condition context
curl -X POST http://localhost:8080/stores/{store_id}/read \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{
    "tuple_key": {
      "user": "user:test_user",
      "relation": "select",
      "object": "catalog:test_catalog"
    }
  }'
```

**Expected:** Tuple có condition context với `attribute_name` và `allowed_values`.

### Test 3: Test Row Filter API

Sau khi grant, test row filter API:

```bash
curl -X POST http://localhost:8000/permissions/row-filter \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "resource": {
      "catalog_name": "test_catalog",
      "schema_name": "finance",
      "table_name": "customers"
    }
  }'
```

**Expected:** Trả về filter expression nếu có policy và condition context.

---

## 📚 Tài liệu liên quan

- `docs/row-filtering-final-design.md` - Design chi tiết về row filtering
- `docs/row-filtering-api-test-guide.md` - Hướng dẫn test row filter API
- `docs/trino-row-filtering-configuration.md` - Cấu hình Trino row filtering

---

## 🎯 Summary

✅ **Đã implement:**

- Condition context trong `/permissions/grant` endpoint
- Support `has_attribute_access` condition với `attribute_name` và `allowed_values`
- Backward compatible: condition là optional field

⚠️ **Cần lưu ý:**

- Với row filter policy, object_id cần là `row_filter_policy:{policy_id}`, không phải từ resource
- Hiện tại cần dùng OpenFGA API trực tiếp hoặc implement admin endpoint riêng

🚀 **Next Steps:**

- Implement admin endpoint cho row filter policies
- Hoặc mở rộng `/permissions/grant` để hỗ trợ row filter policy object_id
