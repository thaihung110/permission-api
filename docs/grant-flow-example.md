# Grant Permission Flow - Row Filtering với Context

## 📋 Tổng quan

Document này mô tả chi tiết flow khi grant permission với condition context cho row filtering, bao gồm cả request, response và logic xử lý từng bước.

---

## 🎯 Ví dụ cụ thể: User `hung` chỉ được select cột `region` = `north`

### **Request Grant Permission**

```http
POST /permissions/grant
Content-Type: application/json

{
  "user_id": "hung",
  "resource": {
    "catalog": "prod",
    "schema": "public",
    "table": "customers"
  },
  "relation": "viewer",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "attribute_name": "region",
      "allowed_values": ["north"]
    }
  }
}
```

---

## 🔄 Flow chi tiết - Step by Step

### **Step 1: API Endpoint nhận request**

**File:** `app/api/v1/endpoints/permissions.py`

```python
@router.post("/grant", response_model=PermissionGrantResponse)
async def grant_permission(grant: PermissionGrant, request: Request):
    # Log incoming request
    logger.info(f"Received grant request: user={grant.user_id}")

    # Get OpenFGA manager from app state
    openfga = request.app.state.openfga

    # Create service and call grant_permission
    service = PermissionService(openfga)
    return await service.grant_permission(grant)
```

**Input:**

- `grant.user_id` = `"hung"`
- `grant.resource` = `{catalog: "prod", schema: "public", table: "customers"}`
- `grant.relation` = `"viewer"`
- `grant.condition` = `{name: "has_attribute_access", context: {...}}`

---

### **Step 2: Permission Service - Check if Row Filtering**

**File:** `app/services/permission_service.py`

```python
async def grant_permission(self, grant: PermissionGrant) -> PermissionGrantResponse:
    logger.info(
        f"Granting permission: user={grant.user_id}, "
        f"resource={grant.resource.model_dump(exclude_none=True)}, relation={grant.relation}"
    )

    resource = grant.resource

    # ✅ DETECT ROW FILTERING
    is_row_filtering = (
        grant.condition is not None              # Has condition
        and grant.relation == "viewer"           # Relation is viewer
        and grant.condition.name == "has_attribute_access"  # Condition name matches
    )
```

**Logic kiểm tra:**

1. `grant.condition is not None` ✅ (có condition)
2. `grant.relation == "viewer"` ✅ (relation = viewer)
3. `grant.condition.name == "has_attribute_access"` ✅ (condition name đúng)

**Kết quả:** `is_row_filtering = True` → Đi vào flow ROW FILTERING

---

### **Step 3: Build Row Filter Policy Identifier**

**File:** `app/services/permission_service.py`

```python
if is_row_filtering:
    # Row filtering: build row_filter_policy object_id
    object_id, resource_type, resource_id = (
        self._build_row_filter_policy_identifier(
            resource, grant.condition.context
        )
    )
```

**Method `_build_row_filter_policy_identifier`:**

```python
def _build_row_filter_policy_identifier(
    self, resource, condition_context
) -> Tuple[str, str, str]:
    """
    Build row_filter_policy identifier from resource and condition context

    Policy ID format: {table_name}_{attribute_name}_filter
    Example: "customers_region_filter" for table "customers" and attribute "region"
    """

    # 1. Validate resource has table information
    schema_name = resource.schema or resource.namespace
    if not (resource.catalog and schema_name and resource.table):
        raise ValueError(
            "Row filter policy requires catalog, schema, and table. "
            'Example: {"catalog": "prod", "schema": "public", "table": "customers"}'
        )

    # ✅ Validation pass:
    # - resource.catalog = "prod"
    # - schema_name = "public"
    # - resource.table = "customers"

    # 2. Get attribute name from condition context
    attribute_name = condition_context.attribute_name
    if not attribute_name:
        raise ValueError(
            "Row filter condition context must include attribute_name. "
            'Example: {"attribute_name": "region", "allowed_values": ["north"]}'
        )

    # ✅ attribute_name = "region"

    # 3. Build policy ID: {table_name}_{attribute_name}_filter
    table_name = resource.table  # "customers"
    policy_id = f"{table_name}_{attribute_name}_filter"
    # ✅ policy_id = "customers_region_filter"

    # 4. Build object_id
    object_id = f"row_filter_policy:{policy_id}"
    # ✅ object_id = "row_filter_policy:customers_region_filter"

    resource_type = "row_filter_policy"
    resource_id = policy_id

    logger.info(
        f"Built row filter policy identifier: policy_id={policy_id}, "
        f"table={resource.catalog}.{schema_name}.{table_name}, "
        f"attribute={attribute_name}"
    )

    return object_id, resource_type, resource_id
```

**Output:**

- `object_id` = `"row_filter_policy:customers_region_filter"`
- `resource_type` = `"row_filter_policy"`
- `resource_id` = `"customers_region_filter"`

**Log:**

```
INFO: Built row filter policy identifier: policy_id=customers_region_filter, table=prod.public.customers, attribute=region
```

---

### **Step 4: Ensure Policy-to-Table Link**

**File:** `app/services/permission_service.py`

```python
# Ensure policy-to-table link exists
await self._ensure_policy_table_link(resource, object_id)
```

**Method `_ensure_policy_table_link`:**

```python
async def _ensure_policy_table_link(self, resource, policy_object_id: str):
    """
    Ensure policy-to-table link exists in OpenFGA

    Creates tuple: table:{catalog}.{schema}.{table} --applies_to--> row_filter_policy:{policy_id}

    Args:
        resource: Resource specification
        policy_object_id: Policy object ID (e.g., "row_filter_policy:customers_region_filter")
    """
    try:
        # 1. Build table FQN
        schema_name = resource.schema or resource.namespace
        table_fqn = f"{resource.catalog}.{schema_name}.{resource.table}"
        table_object_id = f"table:{table_fqn}"

        # ✅ table_fqn = "prod.public.customers"
        # ✅ table_object_id = "table:prod.public.customers"

        # 2. Check if link already exists
        existing_tuples = await self.openfga.read_tuples(
            user=table_object_id,
            relation="applies_to",
            object_id=policy_object_id,
        )

        if existing_tuples:
            logger.debug(
                f"Policy-to-table link already exists: {table_object_id} --applies_to--> {policy_object_id}"
            )
            return

        # 3. Create the link
        await self.openfga.grant_permission(
            user=table_object_id,
            relation="applies_to",
            object_id=policy_object_id,
        )

        logger.info(
            f"Created policy-to-table link: {table_object_id} --applies_to--> {policy_object_id}"
        )

    except Exception as e:
        logger.warning(
            f"Error ensuring policy-table link (may already exist): {e}"
        )
        # Don't fail the grant if link creation fails - it might already exist
```

**OpenFGA Query (Check existing):**

```http
POST /stores/{store_id}/read
{
  "tuple_key": {
    "user": "table:prod.public.customers",
    "relation": "applies_to",
    "object": "row_filter_policy:customers_region_filter"
  }
}
```

**OpenFGA Write (Create link):**

```http
POST /stores/{store_id}/write
{
  "writes": [
    {
      "user": "table:prod.public.customers",
      "relation": "applies_to",
      "object": "row_filter_policy:customers_region_filter"
    }
  ]
}
```

**Kết quả:** Tuple **policy-to-table link** được tạo trong OpenFGA

**Log:**

```
INFO: Created policy-to-table link: table:prod.public.customers --applies_to--> row_filter_policy:customers_region_filter
```

---

### **Step 5: Build User Identifier**

**File:** `app/services/permission_service.py`

```python
# Build user identifier
user = build_user_identifier(grant.user_id)
# ✅ user = "user:hung"
```

---

### **Step 6: Prepare Condition Dictionary**

**File:** `app/services/permission_service.py`

```python
# Prepare condition dict if provided
condition_dict = None
if grant.condition:
    condition_dict = {
        "name": grant.condition.name,
        "context": grant.condition.context.model_dump(),
    }
    logger.info(
        f"Granting permission with condition: user={user}, relation={grant.relation}, "
        f"object={object_id}, condition={grant.condition.name}"
    )
```

**Output:**

```python
condition_dict = {
    "name": "has_attribute_access",
    "context": {
        "attribute_name": "region",
        "allowed_values": ["north"]
    }
}
```

**Log:**

```
INFO: Granting permission with condition: user=user:hung, relation=viewer, object=row_filter_policy:customers_region_filter, condition=has_attribute_access
```

---

### **Step 7: Grant Permission to OpenFGA**

**File:** `app/services/permission_service.py` → `app/external/openfga_client.py`

```python
# Grant permission in OpenFGA
await self.openfga.grant_permission(
    user, grant.relation, object_id, condition=condition_dict
)
```

**OpenFGA Manager:**

```python
async def grant_permission(
    self,
    user: str,               # "user:hung"
    relation: str,           # "viewer"
    object_id: str,          # "row_filter_policy:customers_region_filter"
    condition: Optional[Dict[str, Any]] = None,  # {...}
):
    # Create tuple using SDK model
    tuple_kwargs = {
        "user": user,
        "relation": relation,
        "object": object_id,
    }

    # Add condition if provided
    if condition:
        tuple_kwargs["condition"] = condition
        logger.info(
            f"Writing tuple with condition: user={user}, relation={relation}, "
            f"object={object_id}, condition={condition.get('name')}"
        )

    # ✅ tuple_kwargs = {
    #   "user": "user:hung",
    #   "relation": "viewer",
    #   "object": "row_filter_policy:customers_region_filter",
    #   "condition": {
    #     "name": "has_attribute_access",
    #     "context": {
    #       "attribute_name": "region",
    #       "allowed_values": ["north"]
    #     }
    #   }
    # }

    tuple_item = ClientTuple(**tuple_kwargs)

    # Create write request
    body = ClientWriteRequest(writes=[tuple_item])

    # Write to OpenFGA
    response = await self.client.write(body)
    logger.debug(f"OpenFGA write response: {response}")

    logger.info(
        f"Granted permission with condition: user={user}, relation={relation}, "
        f"object={object_id}, condition={condition.get('name')}"
    )
```

**OpenFGA Write Request:**

```http
POST /stores/{store_id}/write
{
  "writes": [
    {
      "user": "user:hung",
      "relation": "viewer",
      "object": "row_filter_policy:customers_region_filter",
      "condition": {
        "name": "has_attribute_access",
        "context": {
          "attribute_name": "region",
          "allowed_values": ["north"]
        }
      }
    }
  ]
}
```

**Kết quả:** Tuple **user-to-policy** với condition được tạo trong OpenFGA

**Log:**

```
INFO: Writing tuple with condition: user=user:hung, relation=viewer, object=row_filter_policy:customers_region_filter, condition=has_attribute_access
INFO: Granted permission with condition: user=user:hung, relation=viewer, object=row_filter_policy:customers_region_filter, condition=has_attribute_access
```

---

### **Step 8: Return Response**

**File:** `app/services/permission_service.py`

```python
logger.info(
    f"Permission granted with condition: user={user}, relation={grant.relation}, "
    f"object={object_id}, condition={grant.condition.name}"
)

return PermissionGrantResponse(
    success=True,
    user_id=grant.user_id,
    resource_type=resource_type,
    resource_id=resource_id,
    object_id=object_id,
    relation=grant.relation,
)
```

**Response:**

```json
{
  "success": true,
  "user_id": "hung",
  "resource_type": "row_filter_policy",
  "resource_id": "customers_region_filter",
  "object_id": "row_filter_policy:customers_region_filter",
  "relation": "viewer"
}
```

**Log:**

```
INFO: Permission granted with condition: user=user:hung, relation=viewer, object=row_filter_policy:customers_region_filter, condition=has_attribute_access
```

---

## 📊 Tổng kết - OpenFGA Tuples được tạo

Sau khi grant thành công, **2 tuples** được tạo trong OpenFGA:

### **Tuple 1: Policy-to-Table Link**

```json
{
  "user": "table:prod.public.customers",
  "relation": "applies_to",
  "object": "row_filter_policy:customers_region_filter"
}
```

### **Tuple 2: User-to-Policy Permission with Condition**

```json
{
  "user": "user:hung",
  "relation": "viewer",
  "object": "row_filter_policy:customers_region_filter",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "attribute_name": "region",
      "allowed_values": ["north"]
    }
  }
}
```

---

## 🔍 Chi tiết Logic Code

### **1. Detect Row Filtering Logic**

```python
is_row_filtering = (
    grant.condition is not None              # ✅ Có condition
    and grant.relation == "viewer"           # ✅ Relation = viewer
    and grant.condition.name == "has_attribute_access"  # ✅ Condition name đúng
)
```

**Điều kiện để vào flow row filtering:**

- Phải có `condition` trong request
- `relation` phải là `viewer`
- `condition.name` phải là `has_attribute_access`

### **2. Policy ID Naming Convention**

```python
policy_id = f"{table_name}_{attribute_name}_filter"
```

**Format:** `{table_name}_{attribute_name}_filter`

**Ví dụ:**

- Table: `customers`, Attribute: `region` → Policy ID: `customers_region_filter`
- Table: `employees`, Attribute: `department` → Policy ID: `employees_department_filter`

### **3. Object ID Format**

```python
object_id = f"row_filter_policy:{policy_id}"
```

**Format:** `row_filter_policy:{policy_id}`

**Ví dụ:**

- Policy ID: `customers_region_filter` → Object ID: `row_filter_policy:customers_region_filter`

### **4. Condition Context Structure**

```python
{
    "name": "has_attribute_access",
    "context": {
        "attribute_name": "region",      # Tên column trong table
        "allowed_values": ["north"]      # Giá trị được phép
    }
}
```

**OpenFGA lưu condition context:**

- Stored as **bytea** (serialized) in OpenFGA database
- **Automatically deserialized** by SDK when reading tuples
- Format: JSON object với `attribute_name` và `allowed_values`

---

## 🎬 Flow Diagram

```
┌─────────┐   ┌──────────┐   ┌──────────────┐   ┌─────────┐
│  Client │   │   API    │   │  Permission  │   │ OpenFGA │
│         │   │ Endpoint │   │   Service    │   │         │
└────┬────┘   └────┬─────┘   └──────┬───────┘   └────┬────┘
     │             │                 │                │
     │ POST /grant │                 │                │
     │────────────▶│                 │                │
     │             │                 │                │
     │             │ grant_permission│                │
     │             │────────────────▶│                │
     │             │                 │                │
     │             │          Detect Row Filtering    │
     │             │          (condition + viewer)    │
     │             │                 │                │
     │             │          Build Policy ID         │
     │             │          "customers_region_filter"│
     │             │                 │                │
     │             │                 │ Write Tuple 1  │
     │             │                 │ (policy→table) │
     │             │                 │───────────────▶│
     │             │                 │                │
     │             │                 │ Write Tuple 2  │
     │             │                 │ (user→policy   │
     │             │                 │  with condition)│
     │             │                 │───────────────▶│
     │             │                 │                │
     │             │        Response │                │
     │             │◀────────────────│                │
     │             │                 │                │
     │  Response   │                 │                │
     │◀────────────│                 │                │
     │             │                 │                │
```

---

## 🚀 Sử dụng khi Query

Sau khi grant, khi user `hung` query table `customers`:

```sql
SELECT * FROM prod.public.customers;
```

**Flow sẽ như sau:**

1. Trino → OPA → Permission API
2. Permission API queries OpenFGA:
   - Get policies for table → `["customers_region_filter"]`
   - Get user's allowed values → `["north"]`
3. Build filter: `region IN ('north')`
4. Trino executes: `SELECT * FROM customers WHERE region IN ('north')`

**Kết quả:** User `hung` chỉ thấy customers có `region = 'north'`

---

## ✅ Key Points

- ✅ **2 tuples** được tạo: policy-to-table link + user-to-policy permission
- ✅ **Policy ID** được generate tự động từ table name + attribute name
- ✅ **Condition context** được lưu trực tiếp trong tuple (bytea → JSON)
- ✅ **Idempotent**: Nếu policy-to-table link đã tồn tại, không tạo lại
- ✅ **Fail-safe**: Error khi tạo link không làm fail toàn bộ grant
- ✅ **Column mapping**: Column name được infer từ `attribute_name` trong condition context

## Cần check và sửa lại phần endpoint grant

## Cần check lại model, để merge giữa trino và lakekeeper
