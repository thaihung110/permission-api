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

**Note:** Với row filter policy, `resource` phải có đầy đủ catalog, schema, table. Hệ thống sẽ tự động build policy ID và tạo policy-to-table link.

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

### Step 1: Grant User Access với Condition Context (Tự động tạo Policy Link)

Grant user access với condition. Hệ thống sẽ tự động tạo policy-to-table link nếu chưa có:

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

**Note:** Hệ thống tự động build policy ID `user_region_filter` từ table name và attribute name, và tự động tạo policy-to-table link.

---

## ✅ Tự động hóa

Hệ thống tự động xử lý row filtering khi detect:

- `relation = "viewer"`
- `condition.name = "has_attribute_access"`
- Resource có đầy đủ catalog, schema, table

**Tự động:**

1. Build policy ID: `{table_name}_{attribute_name}_filter`
2. Tạo policy-to-table link (nếu chưa có)
3. Grant user permission với condition context

**Không cần:**

- Tạo policy-to-table link thủ công
- Specify policy_id trong request
- Dùng OpenFGA API trực tiếp

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

✅ **Đã hoàn thiện:**

- Tự động detect row filtering khi có condition context với relation "viewer"
- Tự động build policy ID từ table name và attribute name
- Tự động tạo policy-to-table link
- Backward compatible: không ảnh hưởng đến grant permission thông thường

📚 **Tài liệu liên quan:**

- `docs/row-filtering-grant-fix.md` - Chi tiết về fix và cách sử dụng
