# Row Filtering Implementation Plan

## Tổng quan

Triển khai row filtering trong OpenFGA dựa trên user attributes (region, department, etc.) để lọc dữ liệu ở cấp độ row khi query Trino/database.

**Ý tưởng chính:** Sử dụng một type generic `user_attribute` để lưu tất cả user attributes dưới dạng key-value pairs, thay vì tạo type riêng cho từng loại attribute.

---

## 1. Sửa đổi OpenFGA Model (`openfga/auth_model.fga`)

### 1.1. Thêm type mới vào cuối file

```typescript
# ============================================================================
# ROW FILTERING SUPPORT
# ============================================================================

# Type lưu trữ user attributes (region, department, etc.)
type user_attribute
  relations
    # User sở hữu attribute này
    define owner: [user, role#assignee]

    # User có giá trị cho attribute (giá trị lưu trong condition context)
    define has_value: [user with attribute_value_set, role#assignee with attribute_value_set]

    # Admin có thể quản lý attribute
    define can_manage: [user, role#assignee]

# Type lưu trữ filter rules cho table/column
type attribute_filter_rule
  relations
    # Rule này áp dụng cho table/column nào
    define applies_to_table: [table]
    define applies_to_column: [column]

    # Rule sử dụng attribute key nào (lưu trong condition context)
    define uses_attribute_key: [user:*]

    # Admin có thể config rule
    define can_configure: [user, role#assignee]
```

### 1.2. Thêm conditions vào đầu model

Thêm sau dòng `schema 1.2`:

```typescript
# ============================================================================
# CONDITIONS
# ============================================================================

condition attribute_value_set(
  attribute_value: string
) {
  attribute_value != "" && attribute_value != null
}

condition row_matches_attribute(
  row_value: string,
  user_attribute_value: string
) {
  row_value == user_attribute_value
}

condition row_in_attribute_list(
  row_value: string,
  user_attribute_values: list<string>
) {
  row_value in user_attribute_values
}
```

---

## 2. Ví dụ Relationship Tuples

### 2.1. User có attribute `region` = `mien_bac`

```json
// Tuple 1: Owner relation
{
  "user": "user:sale_nam",
  "relation": "owner",
  "object": "user_attribute:sale_nam.region"
}

// Tuple 2: Attribute value
{
  "user": "user:sale_nam",
  "relation": "has_value",
  "object": "user_attribute:sale_nam.region",
  "condition": {
    "name": "attribute_value_set",
    "context": {
      "attribute_value": "mien_bac"
    }
  }
}
```

### 2.2. User có nhiều giá trị cho attribute (regional manager)

```json
// Cách 1: Nhiều tuples riêng biệt (khuyến nghị)
{
  "user": "user:manager_minh",
  "relation": "has_value",
  "object": "user_attribute:manager_minh.region.mien_bac",
  "condition": {
    "name": "attribute_value_set",
    "context": {"attribute_value": "mien_bac"}
  }
}

{
  "user": "user:manager_minh",
  "relation": "has_value",
  "object": "user_attribute:manager_minh.region.mien_nam",
  "condition": {
    "name": "attribute_value_set",
    "context": {"attribute_value": "mien_nam"}
  }
}

// Cách 2: Single tuple với comma-separated values
{
  "user": "user:manager_minh",
  "relation": "has_value",
  "object": "user_attribute:manager_minh.region",
  "condition": {
    "name": "attribute_value_set",
    "context": {"attribute_value": "mien_bac,mien_nam"}
  }
}
```

### 2.3. User có nhiều loại attributes

```json
// Region attribute
{
  "user": "user:sale_nam",
  "relation": "has_value",
  "object": "user_attribute:sale_nam.region",
  "condition": {
    "name": "attribute_value_set",
    "context": {"attribute_value": "mien_bac"}
  }
}

// Department attribute
{
  "user": "user:sale_nam",
  "relation": "has_value",
  "object": "user_attribute:sale_nam.department",
  "condition": {
    "name": "attribute_value_set",
    "context": {"attribute_value": "sales_hanoi"}
  }
}

// Employee level attribute
{
  "user": "user:sale_nam",
  "relation": "has_value",
  "object": "user_attribute:sale_nam.level",
  "condition": {
    "name": "attribute_value_set",
    "context": {"attribute_value": "junior"}
  }
}
```

### 2.4. Filter rule cho table `customers` dựa trên `region`

```json
// Tuple 1: Rule applies to table
{
  "user": "table:prod.public.customers",
  "relation": "applies_to_table",
  "object": "attribute_filter_rule:customers_region_filter"
}

// Tuple 2: Rule uses attribute key "region"
{
  "user": "user:*",
  "relation": "uses_attribute_key",
  "object": "attribute_filter_rule:customers_region_filter",
  "condition": {
    "name": "attribute_value_set",
    "context": {
      "attribute_value": "region"
    }
  }
}
```

### 2.5. Filter rule cho column cụ thể

```json
{
  "user": "column:prod.public.sales.region_code",
  "relation": "applies_to_column",
  "object": "attribute_filter_rule:sales_region_code_filter"
}

{
  "user": "user:*",
  "relation": "uses_attribute_key",
  "object": "attribute_filter_rule:sales_region_code_filter",
  "condition": {
    "name": "attribute_value_set",
    "context": {"attribute_value": "region"}
  }
}
```

---

## 3. Prototype/Pseudo Code cho Permission API

### 3.1. Core Functions

```python
# app/services/row_filter_service.py

from typing import List, Optional, Dict
from app.core.openfga_client import OpenFGAClient
import logging

logger = logging.getLogger(__name__)

class UserAttribute:
    """Represents a user attribute"""
    def __init__(self, user_id: str, attribute_key: str, values: List[str]):
        self.user_id = user_id
        self.attribute_key = attribute_key
        self.values = values

class FilterRule:
    """Represents a filter rule for table/column"""
    def __init__(self, rule_id: str, attribute_key: str, column_name: str,
                 table_fqn: str = None):
        self.rule_id = rule_id
        self.attribute_key = attribute_key
        self.column_name = column_name
        self.table_fqn = table_fqn


async def get_user_attribute_values(
    user_id: str,
    attribute_key: str
) -> List[str]:
    """
    Lấy tất cả values của một attribute từ OpenFGA

    Returns: List['mien_bac', 'mien_nam'] hoặc []
    """
    client = OpenFGAClient()
    values = []

    # Query: Tìm tất cả has_value tuples cho user và attribute_key
    tuples = await client.read_tuples(
        user=f"user:{user_id}",
        relation="has_value"
    )

    for tuple in tuples:
        obj_id = tuple.object.replace("user_attribute:", "")

        # Check nếu tuple này match với attribute_key
        if obj_id.startswith(f"{user_id}.{attribute_key}"):
            # Extract value từ condition context
            if tuple.condition and tuple.condition.context:
                attr_value = tuple.condition.context.get("attribute_value")

                if attr_value:
                    # Handle comma-separated values
                    if "," in attr_value:
                        values.extend([v.strip() for v in attr_value.split(",")])
                    else:
                        values.append(attr_value)

    return list(set(values))  # Remove duplicates


async def get_table_filter_rules(table_fqn: str) -> List[FilterRule]:
    """
    Lấy tất cả filter rules áp dụng cho table

    Args:
        table_fqn: "prod.public.customers"

    Returns:
        List[FilterRule(attribute_key='region', column_name='region')]
    """
    client = OpenFGAClient()
    rules = []

    # Query: Tìm filter rules cho table
    tuples = await client.read_tuples(
        user=f"table:{table_fqn}",
        relation="applies_to_table"
    )

    for tuple in tuples:
        rule_id = tuple.object.replace("attribute_filter_rule:", "")

        # Lấy attribute_key được sử dụng bởi rule này
        attribute_key = await _get_rule_attribute_key(rule_id)

        if attribute_key:
            rules.append(FilterRule(
                rule_id=rule_id,
                attribute_key=attribute_key,
                column_name=attribute_key,  # Default mapping
                table_fqn=table_fqn
            ))

    return rules


async def _get_rule_attribute_key(rule_id: str) -> Optional[str]:
    """Helper: Lấy attribute_key từ rule"""
    client = OpenFGAClient()

    tuples = await client.read_tuples(
        user="user:*",
        relation="uses_attribute_key",
        object=f"attribute_filter_rule:{rule_id}"
    )

    for tuple in tuples:
        if tuple.condition and tuple.condition.context:
            return tuple.condition.context.get("attribute_value")

    return None


async def build_row_filter_expression(
    user_id: str,
    table_fqn: str
) -> Optional[str]:
    """
    Build SQL WHERE clause cho row filtering

    Flow:
    1. Get filter rules cho table
    2. Với mỗi rule, lấy user's attribute values
    3. Build SQL IN clause
    4. Combine với AND/OR logic

    Example Output: "region IN ('mien_bac')"
    """
    # Step 1: Lấy filter rules
    filter_rules = await get_table_filter_rules(table_fqn)

    if not filter_rules:
        logger.info(f"No filter rules for {table_fqn}")
        return None

    # Step 2: Build filter cho mỗi rule
    filter_clauses = []

    for rule in filter_rules:
        # Lấy user's values cho attribute này
        user_values = await get_user_attribute_values(user_id, rule.attribute_key)

        if not user_values:
            # User không có values cho required attribute -> deny all
            logger.warning(
                f"User {user_id} has no {rule.attribute_key} attribute, "
                f"blocking access to {table_fqn}"
            )
            return "1=0"  # SQL always false

        # Build SQL IN clause
        safe_values = [_sanitize_sql(v) for v in user_values]
        values_str = "', '".join(safe_values)
        filter_clauses.append(f"{rule.column_name} IN ('{values_str}')")

    # Step 3: Combine filters
    if len(filter_clauses) == 0:
        return None

    if len(filter_clauses) == 1:
        return filter_clauses[0]

    # OR logic: user có thể thấy rows matching ANY attribute (permissive)
    return f"({' OR '.join(filter_clauses)})"

    # AND logic: user phải match ALL attributes (restrictive) - uncomment nếu cần
    # return f"({' AND '.join(filter_clauses)})"


def _sanitize_sql(value: str) -> str:
    """Sanitize SQL value để prevent injection"""
    sanitized = value.replace("'", "").replace(";", "")
    sanitized = sanitized.replace("--", "").replace("\\", "")
    return sanitized[:100]  # Limit length
```

### 3.2. FastAPI Endpoint

```python
# app/api/v1/endpoints/row_filter.py

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict
from app.services.row_filter_service import build_row_filter_expression
from app.api.deps import get_current_user

router = APIRouter()

class RowFilterRequest(BaseModel):
    user_id: str
    resource: Dict[str, str]  # catalog_name, schema_name, table_name

class RowFilterResponse(BaseModel):
    filter_expression: Optional[str]
    metadata: Optional[Dict] = None

@router.post("/permissions/row-filter")
async def get_row_filter(request: RowFilterRequest) -> RowFilterResponse:
    """
    Generate row filter expression cho user

    Request:
    {
        "user_id": "sale_nam",
        "resource": {
            "catalog_name": "prod",
            "schema_name": "public",
            "table_name": "customers"
        }
    }

    Response:
    {
        "filter_expression": "region IN ('mien_bac')",
        "metadata": {...}
    }
    """
    user_id = request.user_id
    resource = request.resource

    # Build table FQN
    table_fqn = f"{resource['catalog_name']}.{resource['schema_name']}.{resource['table_name']}"

    try:
        # Generate filter expression
        filter_expr = await build_row_filter_expression(user_id, table_fqn)

        return RowFilterResponse(
            filter_expression=filter_expr,
            metadata={
                "user_id": user_id,
                "table": table_fqn
            }
        )

    except Exception as e:
        logger.error(f"Error generating row filter: {e}", exc_info=True)

        # Fail closed: deny all on error
        return RowFilterResponse(
            filter_expression="1=0",
            metadata={"error": str(e)}
        )
```

### 3.3. Admin Endpoints - Manage User Attributes

```python
# app/api/v1/endpoints/user_attributes.py

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from app.core.openfga_client import OpenFGAClient

router = APIRouter()

class SetUserAttributeRequest(BaseModel):
    user_id: str
    attribute_key: str  # "region", "department", etc.
    values: List[str]   # ["mien_bac", "ha_noi"]

@router.post("/admin/user-attributes")
async def set_user_attribute(request: SetUserAttributeRequest):
    """
    Set attribute values cho user

    Example:
    {
        "user_id": "sale_nam",
        "attribute_key": "region",
        "values": ["mien_bac"]
    }
    """
    client = OpenFGAClient()
    user_id = request.user_id
    attr_key = request.attribute_key
    values = request.values

    # Delete existing attributes
    await _delete_user_attribute(client, user_id, attr_key)

    # Write new tuples
    tuples = []

    # Owner tuple
    tuples.append({
        "user": f"user:{user_id}",
        "relation": "owner",
        "object": f"user_attribute:{user_id}.{attr_key}"
    })

    # Value tuples
    for value in values:
        tuples.append({
            "user": f"user:{user_id}",
            "relation": "has_value",
            "object": f"user_attribute:{user_id}.{attr_key}.{value}",
            "condition": {
                "name": "attribute_value_set",
                "context": {"attribute_value": value}
            }
        })

    await client.write_tuples(tuples)

    return {"status": "success", "tuples_written": len(tuples)}


async def _delete_user_attribute(client, user_id: str, attr_key: str):
    """Helper: Delete existing attribute tuples"""
    # Read existing tuples
    existing = await client.read_tuples(
        user=f"user:{user_id}",
        relation="has_value"
    )

    # Filter tuples for this attribute
    to_delete = []
    for tuple in existing:
        obj_id = tuple.object.replace("user_attribute:", "")
        if obj_id.startswith(f"{user_id}.{attr_key}"):
            to_delete.append(tuple)

    if to_delete:
        await client.delete_tuples(to_delete)
```

### 3.4. Admin Endpoints - Configure Filter Rules

```python
# app/api/v1/endpoints/filter_rules.py

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class CreateFilterRuleRequest(BaseModel):
    rule_id: str
    table_fqn: str           # "prod.public.customers"
    attribute_key: str       # "region"
    column_name: str         # "region" (column in table)

@router.post("/admin/filter-rules")
async def create_filter_rule(request: CreateFilterRuleRequest):
    """
    Tạo filter rule cho table

    Example:
    {
        "rule_id": "customers_region_filter",
        "table_fqn": "prod.public.customers",
        "attribute_key": "region",
        "column_name": "region"
    }
    """
    client = OpenFGAClient()

    tuples = [
        # Rule applies to table
        {
            "user": f"table:{request.table_fqn}",
            "relation": "applies_to_table",
            "object": f"attribute_filter_rule:{request.rule_id}"
        },
        # Rule uses attribute key
        {
            "user": "user:*",
            "relation": "uses_attribute_key",
            "object": f"attribute_filter_rule:{request.rule_id}",
            "condition": {
                "name": "attribute_value_set",
                "context": {"attribute_value": request.attribute_key}
            }
        }
    ]

    await client.write_tuples(tuples)

    # Optionally: Store column mapping in database
    # await store_column_mapping(request.rule_id, request.column_name)

    return {"status": "success", "rule_id": request.rule_id}
```

---

## 4. Complete Flow sau khi sửa lại các module

### 4.1. Setup Flow (One-time)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. SETUP OPENFGA MODEL                                      │
└─────────────────────────────────────────────────────────────┘
    │
    ├─→ Update auth_model.fga với types và conditions mới
    │
    └─→ Upload model lên OpenFGA server
        $ openfga model write --store-id=... --file=auth_model.fga

┌─────────────────────────────────────────────────────────────┐
│ 2. CONFIGURE FILTER RULES (Admin)                           │
└─────────────────────────────────────────────────────────────┘
    │
    ├─→ POST /admin/filter-rules
    │   {
    │     "rule_id": "customers_region_filter",
    │     "table_fqn": "prod.public.customers",
    │     "attribute_key": "region",
    │     "column_name": "region"
    │   }
    │
    └─→ OpenFGA tuples được tạo:
        - table:prod.public.customers --applies_to_table-->
          attribute_filter_rule:customers_region_filter
        - user:* --uses_attribute_key-->
          attribute_filter_rule:customers_region_filter
          [context: {"attribute_value": "region"}]

┌─────────────────────────────────────────────────────────────┐
│ 3. ASSIGN USER ATTRIBUTES (Admin/HR)                        │
└─────────────────────────────────────────────────────────────┘
    │
    ├─→ POST /admin/user-attributes
    │   {
    │     "user_id": "sale_nam",
    │     "attribute_key": "region",
    │     "values": ["mien_bac"]
    │   }
    │
    └─→ OpenFGA tuples được tạo:
        - user:sale_nam --owner--> user_attribute:sale_nam.region
        - user:sale_nam --has_value-->
          user_attribute:sale_nam.region.mien_bac
          [context: {"attribute_value": "mien_bac"}]
```

### 4.2. Query Flow (Runtime)

```
┌─────────────────────────────────────────────────────────────┐
│ USER QUERY: SELECT * FROM prod.public.customers             │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. TRINO COORDINATOR                                        │
└─────────────────────────────────────────────────────────────┘
    │
    ├─→ Extract: user="sale_nam", table="prod.public.customers"
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. OPA POLICY CHECK                                         │
└─────────────────────────────────────────────────────────────┘
    │
    ├─→ Call Permission API: /permissions/row-filter
    │   Request: {
    │     "user_id": "sale_nam",
    │     "resource": {
    │       "catalog_name": "prod",
    │       "schema_name": "public",
    │       "table_name": "customers"
    │     }
    │   }
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. PERMISSION API PROCESSING                                │
└─────────────────────────────────────────────────────────────┘
    │
    ├─→ Step 1: get_table_filter_rules("prod.public.customers")
    │   → Query OpenFGA: Tìm filter rules cho table
    │   → Result: [FilterRule(attribute_key="region", column="region")]
    │
    ├─→ Step 2: get_user_attribute_values("sale_nam", "region")
    │   → Query OpenFGA: Tìm has_value tuples
    │   → Result: ["mien_bac"]
    │
    ├─→ Step 3: build_row_filter_expression()
    │   → Build SQL: "region IN ('mien_bac')"
    │
    └─→ Return: {
          "filter_expression": "region IN ('mien_bac')",
          "metadata": {...}
        }
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. OPA RETURNS POLICY DECISION                              │
└─────────────────────────────────────────────────────────────┘
    │
    └─→ {
          "result": {
            "allowed": true,
            "row_filter": "region IN ('mien_bac')"
          }
        }
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. TRINO APPLIES ROW FILTER                                 │
└─────────────────────────────────────────────────────────────┘
    │
    ├─→ Original query:
    │   SELECT * FROM prod.public.customers
    │
    ├─→ Modified query:
    │   SELECT * FROM prod.public.customers
    │   WHERE region IN ('mien_bac')
    │
    └─→ Execute và return filtered results
```

### 4.3. Module Integration

```
┌──────────────────────────────────────────────────────────────┐
│ ARCHITECTURE OVERVIEW                                        │
└──────────────────────────────────────────────────────────────┘

┌─────────────┐
│   Trino     │ Query với row filtering
└──────┬──────┘
       │
       ▼
┌─────────────┐
│     OPA     │ Policy enforcement
└──────┬──────┘
       │
       │ HTTP Request
       ▼
┌─────────────────────────────────────────────────────────┐
│  Permission API (FastAPI)                               │
│                                                         │
│  ┌────────────────────────────────────────────┐        │
│  │ /permissions/row-filter                     │        │
│  │  - Extract user_id, table_fqn               │        │
│  │  - Call RowFilterService                    │        │
│  │  - Return filter expression                 │        │
│  └────────────────────────────────────────────┘        │
│                                                         │
│  ┌────────────────────────────────────────────┐        │
│  │ RowFilterService                            │        │
│  │  - get_table_filter_rules()                 │        │
│  │  - get_user_attribute_values()              │        │
│  │  - build_row_filter_expression()            │        │
│  └────────────────────────────────────────────┘        │
│                 │                                       │
│                 │ OpenFGA SDK Calls                     │
│                 ▼                                       │
│  ┌────────────────────────────────────────────┐        │
│  │ OpenFGAClient Wrapper                       │        │
│  │  - read_tuples()                            │        │
│  │  - write_tuples()                           │        │
│  │  - delete_tuples()                          │        │
│  └────────────────────────────────────────────┘        │
└──────────────────────┬──────────────────────────────────┘
                       │
                       │ gRPC/HTTP
                       ▼
              ┌─────────────────┐
              │   OpenFGA       │ Authorization data store
              │   Server        │
              └─────────────────┘
```

### 4.4. File Structure

```
Permission-api/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── endpoints/
│   │           ├── row_filter.py          # NEW: Row filter endpoint
│   │           ├── user_attributes.py     # NEW: Admin manage user attrs
│   │           └── filter_rules.py        # NEW: Admin manage filter rules
│   │
│   ├── services/
│   │   ├── row_filter_service.py          # NEW: Core row filtering logic
│   │   └── openfga_service.py             # UPDATED: Add tuple helpers
│   │
│   ├── core/
│   │   ├── openfga_client.py              # UPDATED: Add read/write helpers
│   │   └── config.py                       # UPDATED: Add config
│   │
│   └── models/
│       └── row_filter.py                   # NEW: Pydantic models
│
├── openfga/
│   └── auth_model.fga                      # UPDATED: Add new types
│
├── policies/
│   └── trino_authz.rego                    # UPDATED: Add row filter call
│
└── docs/
    └── row-filtering-implementation-plan.md # THIS FILE
```

---

## 5. Key Changes Summary

### OpenFGA Model

- ✅ Add `user_attribute` type
- ✅ Add `attribute_filter_rule` type
- ✅ Add conditions: `attribute_value_set`, `row_matches_attribute`, `row_in_attribute_list`

### Permission API

- ✅ NEW: `RowFilterService` với core query functions
- ✅ NEW: `/permissions/row-filter` endpoint
- ✅ NEW: `/admin/user-attributes` endpoint
- ✅ NEW: `/admin/filter-rules` endpoint

### OPA Policy

- ✅ UPDATE: Call Permission API để get row filter expression
- ✅ UPDATE: Return filter trong policy result

### Trino Integration

- ✅ USE: Existing SystemAccessControl implementation
- ✅ UPDATE: Apply row filter từ OPA response

---

## 6. Testing Checklist

- [ ] Upload new OpenFGA model
- [ ] Create filter rule cho test table
- [ ] Assign user attributes
- [ ] Test row filter endpoint
- [ ] Test OPA integration
- [ ] Test Trino query với row filtering
- [ ] Test multiple attributes
- [ ] Test user without attributes (should deny)
- [ ] Test performance với large attribute sets

---

## 7. Migration Steps

1. **Backup current OpenFGA model**

   ```bash
   openfga model get --store-id=<STORE_ID> > backup_model.fga
   ```

2. **Update auth_model.fga** - Add new types và conditions

3. **Upload new model**

   ```bash
   openfga model write --store-id=<STORE_ID> --file=auth_model.fga
   ```

4. **Deploy Permission API changes** - Add new services và endpoints

5. **Update OPA policies** - Add row filter integration

6. **Test với sample data**

7. **Roll out changes to production**

---

## Appendix: API Examples

### Set User Attribute

```bash
curl -X POST http://permission-api/admin/user-attributes \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "sale_nam",
    "attribute_key": "region",
    "values": ["mien_bac"]
  }'
```

### Create Filter Rule

```bash
curl -X POST http://permission-api/admin/filter-rules \
  -H "Content-Type: application/json" \
  -d '{
    "rule_id": "customers_region_filter",
    "table_fqn": "prod.public.customers",
    "attribute_key": "region",
    "column_name": "region"
  }'
```

### Get Row Filter

```bash
curl -X POST http://permission-api/permissions/row-filter \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "sale_nam",
    "resource": {
      "catalog_name": "prod",
      "schema_name": "public",
      "table_name": "customers"
    }
  }'

# Response:
# {
#   "filter_expression": "region IN ('mien_bac')",
#   "metadata": {
#     "user_id": "sale_nam",
#     "table": "prod.public.customers"
#   }
# }
```
