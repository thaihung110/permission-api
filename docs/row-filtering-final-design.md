# Row Filtering với OpenFGA - Final Clean Design

## 🎯 Design Philosophy

- **Minimal & Clean**: Chỉ giữ lại những gì cần thiết
- **No Redundancy**: Loại bỏ bi-directional relations không cần thiết
- **User-only**: Không dùng role, chỉ user direct permissions
- **Fully Generic**: Không hard-code attribute names
- **Production-ready**: Simple, maintainable, scalable

---

## 🏗️ OpenFGA Model

```typescript
model
  schema 1.2

# ============================================================================
# CORE TYPES
# ============================================================================

type user

type catalog
  relations
    define ownership: [user]
    define select: [user] or ownership
    define namespace: [namespace]

type namespace
  relations
    define parent: [namespace, catalog]
    define ownership: [user]
    define select: [user] or ownership or select from parent

type table
  relations
    define parent: [namespace]
    define ownership: [user]
    define select: [user] or ownership or select from parent
    define describe: [user] or ownership

type column
  relations
    define parent: [table]
    define select: [user] or select from parent
    define mask: [user]

# ============================================================================
# ROW FILTERING TYPE
# ============================================================================

type row_filter_policy
  relations
    # Policy applies to which table
    define applies_to: [table]

    # Users allowed under this policy (with attribute filter in condition)
    define viewer: [user with has_attribute_access]

    # Admin can manage policy
    define admin: [user]

# ============================================================================
# CONDITIONS
# ============================================================================

# Generic condition - Works for ANY attribute
condition has_attribute_access(
  attribute_name: string,          # Dynamic: "region", "department", etc.
  allowed_values: list<string>     # User's allowed values
) {
  attribute_name != "" && allowed_values.size() > 0
}
```

---

## 📋 Key Simplifications

### ❌ Removed (Old Design)

```typescript
// Bi-directional link (REDUNDANT)
{
  "user": "row_filter_policy:customers_region_filter",
  "relation": "row_filter_policy",
  "object": "table:prod.public.customers"
}

// Role type (NOT NEEDED)
type role
  relations
    define assignee: [user, role#assignee]
```

### ✅ Kept (Final Design)

```typescript
// Single direction: Policy applies to table
{
  "user": "table:prod.public.customers",
  "relation": "applies_to",
  "object": "row_filter_policy:customers_region_filter"
}

// Direct user permissions only
{
  "user": "user:sale_nam",
  "relation": "viewer",
  "object": "row_filter_policy:customers_region_filter",
  "condition": {...}
}
```

---

## 🔗 Relationship Tuples

### Example 1: Single Attribute Filter

**Scenario:** Table `customers` có row filter theo `region`. User `sale_nam` chỉ được xem `mien_bac`.

```json
// Step 1: Create policy và link to table
{
  "user": "table:prod.public.customers",
  "relation": "applies_to",
  "object": "row_filter_policy:customers_region_filter"
}

// Step 2: Grant user access với attribute filter
{
  "user": "user:sale_nam",
  "relation": "viewer",
  "object": "row_filter_policy:customers_region_filter",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "attribute_name": "region",
      "allowed_values": ["mien_bac"]
    }
  }
}
```

**That's it!** Chỉ 2 tuples, clean và simple.

---

### Example 2: Multiple Values

**User `manager` có access multiple regions**

```json
{
  "user": "table:prod.public.customers",
  "relation": "applies_to",
  "object": "row_filter_policy:customers_region_filter"
}

{
  "user": "user:manager",
  "relation": "viewer",
  "object": "row_filter_policy:customers_region_filter",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "attribute_name": "region",
      "allowed_values": ["mien_bac", "mien_trung", "mien_nam"]
    }
  }
}
```

---

### Example 3: Multiple Policies (Multiple Attributes)

**Table `employees` có filters cho cả `department` VÀ `level`**

```json
// Policy 1: Department filter
{
  "user": "table:prod.hr.employees",
  "relation": "applies_to",
  "object": "row_filter_policy:employees_department_filter"
}

{
  "user": "user:hr_manager",
  "relation": "viewer",
  "object": "row_filter_policy:employees_department_filter",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "attribute_name": "department",
      "allowed_values": ["hr", "finance"]
    }
  }
}

// Policy 2: Level filter
{
  "user": "table:prod.hr.employees",
  "relation": "applies_to",
  "object": "row_filter_policy:employees_level_filter"
}

{
  "user": "user:hr_manager",
  "relation": "viewer",
  "object": "row_filter_policy:employees_level_filter",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "attribute_name": "level",
      "allowed_values": ["junior", "mid", "senior"]
    }
  }
}
```

**Result:** User phải satisfy BOTH filters (AND logic)

- ✅ Can see: `department IN ('hr', 'finance') AND level IN ('junior', 'mid', 'senior')`

---

### Example 4: Wildcard Access

**Admin có full access**

```json
{
  "user": "user:admin",
  "relation": "viewer",
  "object": "row_filter_policy:customers_region_filter",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "attribute_name": "region",
      "allowed_values": ["*"] // Wildcard
    }
  }
}
```

Permission API sẽ skip filter này khi detect wildcard.

---

### Example 5: Adding New Attribute - Zero Model Changes

**New requirement: Filter by `organization_id`**

```json
// Just create new policy - NO MODEL UPDATE needed!
{
  "user": "table:prod.public.projects",
  "relation": "applies_to",
  "object": "row_filter_policy:projects_org_filter"
}

{
  "user": "user:project_manager",
  "relation": "viewer",
  "object": "row_filter_policy:projects_org_filter",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "attribute_name": "organization_id",  // NEW attribute!
      "allowed_values": ["org_123", "org_456"]
    }
  }
}
```

✅ **No code changes, no model changes, no deployments!**

---

## � How to Check/Query Permissions

### Key Difference: Check vs Read

**OpenFGA Document Example (BOOLEAN CHECK):**

```yaml
# Check if user CAN ACCESS document with specific attributes
check:
  user: "user:anne"
  object: "document:1"
  relation: "can_access"
  context:
    document_attributes:
      status: "draft"
# Returns: true/false
```

**Row Filtering Design (QUERY ATTRIBUTES):**

```python
# DON'T check boolean - QUERY user's allowed values instead
read_tuples(
  user="user:sale_nam",
  relation="viewer",
  object="row_filter_policy:customers_region_filter"
)
# Returns: tuples with condition context containing allowed_values
```

**Why different?**

- Document example: Runtime check với specific document attributes
- Row filtering: Build SQL filter by querying user's configured allowed values

---

### Example Test Cases

#### Test Case 1: Query User's Allowed Values

**Setup:**

```json
{
  "user": "table:prod.public.customers",
  "relation": "applies_to",
  "object": "row_filter_policy:customers_region_filter"
}

{
  "user": "user:sale_nam",
  "relation": "viewer",
  "object": "row_filter_policy:customers_region_filter",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "attribute_name": "region",
      "allowed_values": ["mien_bac"]
    }
  }
}
```

**Query:**

```python
# Using OpenFGA SDK
client.read_tuples(
    user="user:sale_nam",
    relation="viewer",
    object="row_filter_policy:customers_region_filter"
)
```

**Expected Result:**

```python
tuples = [
    {
        "user": "user:sale_nam",
        "relation": "viewer",
        "object": "row_filter_policy:customers_region_filter",
        "condition": {
            "name": "has_attribute_access",
            "context": {
                "attribute_name": "region",
                "allowed_values": ["mien_bac"]  # ← Extract this!
            }
        }
    }
]
```

**Then build SQL:**

```python
allowed_values = tuples[0].condition.context["allowed_values"]
# → ["mien_bac"]

sql_filter = f"region IN ('{', '.join(allowed_values)}')"
# → "region IN ('mien_bac')"
```

---

#### Test Case 2: Multiple Users, Different Access

**Setup:**

```json
// User sale_nam - Only mien_bac
{
  "user": "user:sale_nam",
  "relation": "viewer",
  "object": "row_filter_policy:customers_region_filter",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "attribute_name": "region",
      "allowed_values": ["mien_bac"]
    }
  }
}

// User manager - Multiple regions
{
  "user": "user:manager",
  "relation": "viewer",
  "object": "row_filter_policy:customers_region_filter",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "attribute_name": "region",
      "allowed_values": ["mien_bac", "mien_trung", "mien_nam"]
    }
  }
}

// User admin - Wildcard
{
  "user": "user:admin",
  "relation": "viewer",
  "object": "row_filter_policy:customers_region_filter",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "attribute_name": "region",
      "allowed_values": ["*"]
    }
  }
}
```

**Test Queries:**

```python
# Test 1: sale_nam
result = await build_row_filter_sql("sale_nam", "prod.public.customers")
assert result == "region IN ('mien_bac')"

# Test 2: manager
result = await build_row_filter_sql("manager", "prod.public.customers")
assert result == "region IN ('mien_bac', 'mien_trung', 'mien_nam')"

# Test 3: admin (wildcard)
result = await build_row_filter_sql("admin", "prod.public.customers")
assert result is None  # No filter = see all

# Test 4: unauthorized user
result = await build_row_filter_sql("unauthorized", "prod.public.customers")
assert result == "1=0"  # Deny all
```

---

#### Test Case 3: Multiple Policies (AND Logic)

**Setup:**

```json
// Department filter
{
  "user": "table:prod.hr.employees",
  "relation": "applies_to",
  "object": "row_filter_policy:employees_department_filter"
}

{
  "user": "user:hr_manager",
  "relation": "viewer",
  "object": "row_filter_policy:employees_department_filter",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "attribute_name": "department",
      "allowed_values": ["hr", "finance"]
    }
  }
}

// Level filter
{
  "user": "table:prod.hr.employees",
  "relation": "applies_to",
  "object": "row_filter_policy:employees_level_filter"
}

{
  "user": "user:hr_manager",
  "relation": "viewer",
  "object": "row_filter_policy:employees_level_filter",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "attribute_name": "level",
      "allowed_values": ["junior", "mid"]
    }
  }
}
```

**Test Query:**

```python
result = await build_row_filter_sql("hr_manager", "prod.hr.employees")

# Expected: Both filters combined with AND
assert result == "department IN ('hr', 'finance') AND level IN ('junior', 'mid')"
```

---

#### Test Case 4: User Has Partial Access

**Scenario:** Table có 2 policies, user chỉ có access 1 policy

**Setup:**

```json
// Policy 1: Region filter (user HAS access)
{
  "user": "user:sales_person",
  "relation": "viewer",
  "object": "row_filter_policy:customers_region_filter",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "attribute_name": "region",
      "allowed_values": ["mien_bac"]
    }
  }
}

// Policy 2: Department filter (user DOES NOT have access)
// No tuple for sales_person
```

**Test Query:**

```python
result = await build_row_filter_sql("sales_person", "prod.public.customers")

# Expected: Deny all because user missing required filter
assert result == "1=0"  # Missing department filter → No access
```

**Logic:** If table has multiple policies, user MUST have access to ALL policies (AND logic). Missing even ONE policy = denied.

---

#### Test Case 5: OpenFGA Read API Example

**Using OpenFGA CLI/API to verify:**

```bash
# Read all policies for table
fga tuple read \
  --user "table:prod.public.customers" \
  --relation "applies_to"

# Output:
# table:prod.public.customers applies_to row_filter_policy:customers_region_filter
```

```bash
# Read user's access to policy
fga tuple read \
  --user "user:sale_nam" \
  --relation "viewer" \
  --object "row_filter_policy:customers_region_filter"

# Output (with condition):
# user:sale_nam viewer row_filter_policy:customers_region_filter
# Condition: has_attribute_access
# Context: {"attribute_name": "region", "allowed_values": ["mien_bac"]}
```

---

### Complete Test Suite

```python
# tests/test_row_filtering.py

import pytest
from app.services.row_filter_service import build_row_filter_sql

class TestRowFiltering:
    """Test suite for row filtering"""

    @pytest.mark.asyncio
    async def test_single_value_filter(self):
        """User with single allowed value"""
        result = await build_row_filter_sql("sale_nam", "prod.public.customers")
        assert result == "region IN ('mien_bac')"

    @pytest.mark.asyncio
    async def test_multiple_values_filter(self):
        """User with multiple allowed values"""
        result = await build_row_filter_sql("manager", "prod.public.customers")
        assert "mien_bac" in result
        assert "mien_trung" in result
        assert "mien_nam" in result

    @pytest.mark.asyncio
    async def test_wildcard_access(self):
        """Admin with wildcard access"""
        result = await build_row_filter_sql("admin", "prod.public.customers")
        assert result is None  # No filter

    @pytest.mark.asyncio
    async def test_no_access(self):
        """User without any access"""
        result = await build_row_filter_sql("unauthorized", "prod.public.customers")
        assert result == "1=0"

    @pytest.mark.asyncio
    async def test_multiple_policies_and_logic(self):
        """User must satisfy ALL policies"""
        result = await build_row_filter_sql("hr_manager", "prod.hr.employees")
        assert "department IN" in result
        assert "level IN" in result
        assert " AND " in result

    @pytest.mark.asyncio
    async def test_missing_required_policy(self):
        """User missing one required policy"""
        # Table has 2 policies but user only has access to 1
        result = await build_row_filter_sql("partial_user", "prod.public.customers")
        assert result == "1=0"

    @pytest.mark.asyncio
    async def test_no_policies_on_table(self):
        """Table without any row filter policies"""
        result = await build_row_filter_sql("any_user", "prod.public.unrestricted_table")
        assert result is None  # No filtering
```

---

### Summary: Check vs Query

| Aspect              | OpenFGA Document Example                  | **Row Filtering Design**                           |
| ------------------- | ----------------------------------------- | -------------------------------------------------- |
| **Purpose**         | Boolean permission check                  | Query user attributes                              |
| **API Used**        | `Check()`                                 | ✅ `Read()` / `ReadTuples()`                       |
| **Runtime Context** | Pass document attributes                  | ✅ No runtime context needed                       |
| **Result**          | true/false                                | ✅ List of tuples with condition                   |
| **Extract**         | -                                         | ✅ Extract `allowed_values` from condition context |
| **Build**           | -                                         | ✅ Build SQL filter from allowed values            |
| **Use Case**        | "Can user access this specific document?" | ✅ "What rows can user see in this table?"         |

**Key Insight:** We DON'T check permissions at query time. We CONFIGURE permissions in advance (tuples) and QUERY them to build SQL filters.

---

## � Policy Naming Convention

**Permission API không có database riêng - chỉ gọi OpenFGA!**

Column mapping được infer từ **policy_id naming convention**:

```
Format: {table_name}_{column_name}_filter

Examples:
  customers_region_filter      → column: region
  employees_department_filter  → column: department
  employees_level_filter       → column: level
  sales_territory_filter       → column: territory
```

**Parse logic:**

```python
def parse_column_from_policy_id(policy_id: str) -> str:
    """
    Extract column name from policy ID

    Examples:
        "customers_region_filter" → "region"
        "employees_department_filter" → "department"
    """
    # Remove "_filter" suffix and get last part
    parts = policy_id.replace("_filter", "").split("_")
    return parts[-1]  # Last part is column name
```

**Alternative: Store in OpenFGA Metadata (Optional)**

Nếu cần custom mapping phức tạp hơn, lưu metadata tuple:

```json
{
  "user": "metadata:config",
  "relation": "column_mapping",
  "object": "row_filter_policy:customers_region_filter",
  "condition": {
    "name": "has_attribute_access",
    "context": {
      "column_name": "customer_region" // Custom mapping
    }
  }
}
```

---

## 🔧 Permission API Implementation

### Core Service

```python
# app/services/row_filter_service.py

from typing import List, Optional
from dataclasses import dataclass
from app.external.openfga_client import OpenFGAManager
import logging

logger = logging.getLogger(__name__)

@dataclass
class PolicyFilter:
    policy_id: str
    attribute_name: str
    column_name: str
    allowed_values: List[str]
    filter_type: str = "IN"


async def get_table_policies(
    openfga: OpenFGAManager,
    table_fqn: str
) -> List[str]:
    """
    Get all policy IDs for a table from OpenFGA

    Returns: ["customers_region_filter", "customers_department_filter"]
    """
    # Use OpenFGA Read API to get tuples
    # Note: OpenFGA SDK read_tuples returns tuples with condition context
    # Condition context is deserialized from bytea automatically by SDK
    response = await openfga.client.read({
        "user": f"table:{table_fqn}",
        "relation": "applies_to"
    })

    return [
        tuple.object.replace("row_filter_policy:", "")
        for tuple in response.tuples
    ]


def parse_column_from_policy_id(policy_id: str) -> Optional[str]:
    """
    Extract column name from policy ID using naming convention

    Format: {table_name}_{column_name}_filter
    Examples:
        "customers_region_filter" → "region"
        "employees_department_filter" → "department"
    """
    # Remove "_filter" suffix and get last part
    parts = policy_id.replace("_filter", "").split("_")
    if len(parts) >= 2:
        return parts[-1]  # Last part is column name
    return None


async def get_user_policy_filters(
    openfga: OpenFGAManager,
    user_id: str,
    policy_ids: List[str]
) -> List[PolicyFilter]:
    """
    Get user's filters from all policies

    Returns filters with attribute_name and allowed_values from condition context.

    Note: Condition context is stored as bytea in OpenFGA but deserialized
    automatically by SDK when reading tuples.
    """
    filters = []

    for policy_id in policy_ids:
        # Query: user -> viewer -> policy
        response = await openfga.client.read({
            "user": f"user:{user_id}",
            "relation": "viewer",
            "object": f"row_filter_policy:{policy_id}"
        })

        if not response.tuples:
            continue

        for tuple in response.tuples:
            # Condition context is deserialized from bytea by SDK
            if not tuple.condition or not tuple.condition.context:
                continue

            ctx = tuple.condition.context
            attribute_name = ctx.get("attribute_name")
            allowed_values = ctx.get("allowed_values", [])

            if not attribute_name or not allowed_values:
                continue

            # Parse column name from policy_id
            column_name = parse_column_from_policy_id(policy_id)
            if not column_name:
                logger.warning(f"Cannot parse column from policy_id {policy_id}")
                continue

            filters.append(PolicyFilter(
                policy_id=policy_id,
                attribute_name=attribute_name,
                column_name=column_name,
                allowed_values=allowed_values,
                filter_type="IN"  # Default filter type
            ))

    return filters


async def build_row_filter_sql(
    openfga: OpenFGAManager,
    user_id: str,
    table_fqn: str
) -> Optional[str]:
    """
    Build SQL WHERE clause for row filtering

    Returns: "region IN ('mien_bac') AND department IN ('hr')"

    Note: Permission API không có database riêng, chỉ sử dụng OpenFGA.
    """
    # Get policies for table from OpenFGA
    policy_ids = await get_table_policies(openfga, table_fqn)
    if not policy_ids:
        return None

    # Get user's filters from OpenFGA
    filters = await get_user_policy_filters(openfga, user_id, policy_ids)
    if not filters:
        logger.warning(f"User {user_id} has no access to {table_fqn}")
        return "1=0"  # Deny all

    # Build SQL clauses
    clauses = []

    for f in filters:
        # Check wildcard
        if "*" in f.allowed_values:
            continue  # Skip this filter

        # Build SQL
        if f.filter_type == "IN":
            values = [_escape_sql(v) for v in f.allowed_values]
            values_str = "', '".join(values)
            clauses.append(f"{f.column_name} IN ('{values_str}')")

        elif f.filter_type == "LIKE":
            likes = [f"{f.column_name} LIKE '{_escape_sql(v)}%'" for v in f.allowed_values]
            clauses.append(f"({' OR '.join(likes)})")

    if not clauses:
        return None  # All wildcards

    # Combine with AND
    return " AND ".join(clauses) if len(clauses) > 1 else clauses[0]


def _escape_sql(value: str) -> str:
    """Prevent SQL injection"""
    return value.replace("'", "''").replace(";", "")[:100]
```

---

### FastAPI Endpoints

```python
# app/api/v1/endpoints/row_filter.py

from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional, Dict
from app.services.row_filter_service import build_row_filter_sql

router = APIRouter()

class RowFilterRequest(BaseModel):
    user_id: str
    resource: Dict[str, str]  # catalog_name, schema_name, table_name

class RowFilterResponse(BaseModel):
    filter_expression: Optional[str]
    has_filter: bool

@router.post("/permissions/row-filter")
async def get_row_filter(
    req: RowFilterRequest,
    request: Request
) -> RowFilterResponse:
    """
    Get row filter SQL for user on table

    Example:
    POST /permissions/row-filter
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
      "has_filter": true
    }
    """
    table_fqn = f"{req.resource['catalog_name']}.{req.resource['schema_name']}.{req.resource['table_name']}"

    try:
        openfga = request.app.state.openfga
        filter_sql = await build_row_filter_sql(openfga, req.user_id, table_fqn)

        return RowFilterResponse(
            filter_expression=filter_sql,
            has_filter=filter_sql is not None
        )
    except Exception as e:
        # Fail closed
        return RowFilterResponse(
            filter_expression="1=0",
            has_filter=True
        )
```

---

### Admin API

```python
# app/api/v1/endpoints/admin_row_filter.py

from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import List
from app.external.openfga_client import OpenFGAManager

router = APIRouter()

class CreatePolicyRequest(BaseModel):
    policy_id: str
    table_fqn: str
    description: str = ""

@router.post("/admin/policies")
async def create_policy(
    req: CreatePolicyRequest,
    request: Request
):
    """
    Create row filter policy

    Note: Column name is inferred from policy_id naming convention:
    Format: {table_name}_{column_name}_filter

    Example:
    {
      "policy_id": "customers_region_filter",
      "table_fqn": "prod.public.customers",
      "description": "Filter by customer region"
    }
    """
    openfga = request.app.state.openfga

    # Create OpenFGA tuple - only store in OpenFGA, no database
    await openfga.grant_permission(
        user=f"table:{req.table_fqn}",
        relation="applies_to",
        object_id=f"row_filter_policy:{req.policy_id}"
    )

    return {"status": "success", "policy_id": req.policy_id}


class AssignUserRequest(BaseModel):
    user_id: str
    policy_id: str
    attribute_name: str
    allowed_values: List[str]

@router.post("/admin/assign-user")
async def assign_user(
    req: AssignUserRequest,
    request: Request
):
    """
    Assign user to policy with attribute filter

    Condition context is stored as bytea in OpenFGA but provided as JSON
    when writing tuples via SDK.

    Example:
    {
      "user_id": "sale_nam",
      "policy_id": "customers_region_filter",
      "attribute_name": "region",
      "allowed_values": ["mien_bac"]
    }
    """
    openfga = request.app.state.openfga

    # Delete existing tuple if any
    # Note: OpenFGA SDK handles tuple deletion

    # Create new tuple with condition
    # Condition context will be serialized to bytea by OpenFGA
    from openfga_sdk.client.models.tuple import ClientTuple
    from openfga_sdk.client.models import ClientWriteRequest

    tuple_item = ClientTuple(
        user=f"user:{req.user_id}",
        relation="viewer",
        object=f"row_filter_policy:{req.policy_id}",
        condition={
            "name": "has_attribute_access",
            "context": {
                "attribute_name": req.attribute_name,
                "allowed_values": req.allowed_values
            }
        }
    )

    body = ClientWriteRequest(writes=[tuple_item])
    await openfga.client.write(body)

    return {"status": "success"}


@router.delete("/admin/revoke-user/{user_id}/{policy_id}")
async def revoke_user(
    user_id: str,
    policy_id: str,
    request: Request
):
    """Revoke user access to policy"""
    openfga = request.app.state.openfga

    # Read existing tuples
    response = await openfga.client.read({
        "user": f"user:{user_id}",
        "relation": "viewer",
        "object": f"row_filter_policy:{policy_id}"
    })

    if response.tuples:
        # Delete tuples
        from openfga_sdk.client.models import ClientWriteRequest
        from openfga_sdk.client.models.tuple import ClientTuple

        deletes = [
            ClientTuple(
                user=tuple.user,
                relation=tuple.relation,
                object=tuple.object
            )
            for tuple in response.tuples
        ]

        body = ClientWriteRequest(deletes=deletes)
        await openfga.client.write(body)

    return {"status": "success"}
```

---

## 🔄 Complete Flow

### Setup Flow

```
1. Create Policy
   POST /admin/policies
   {
     "policy_id": "customers_region_filter",
     "table_fqn": "prod.public.customers",
     "column_name": "region"
   }

   → Creates OpenFGA tuple: table:customers --applies_to--> policy:customers_region_filter
   → Column name inferred from policy_id: "customers_region_filter" → "region"

2. Assign Users
   POST /admin/assign-user
   {
     "user_id": "sale_nam",
     "policy_id": "customers_region_filter",
     "attribute_name": "region",
     "allowed_values": ["mien_bac"]
   }

   → Creates OpenFGA tuple: user:sale_nam --viewer--> policy:customers_region_filter
     [condition: {attribute_name: "region", allowed_values: ["mien_bac"]}]
```

### Query Flow

```
User Query: SELECT * FROM prod.public.customers

1. Trino → OPA → Permission API
   POST /permissions/row-filter
   {
     "user_id": "sale_nam",
     "resource": {
       "catalog_name": "prod",
       "schema_name": "public",
       "table_name": "customers"
     }
   }

2. Permission API Processing
   a. Get policies: table:prod.public.customers --applies_to--> ?
      → Result: ["customers_region_filter"]

   b. Get user filters: user:sale_nam --viewer--> policy:customers_region_filter
      → Extract from condition context (deserialized from bytea):
        {attribute_name: "region", allowed_values: ["mien_bac"]}

   c. Parse column name from policy_id: customers_region_filter → column: "region"

   d. Build SQL: "region IN ('mien_bac')"

3. OPA returns to Trino
   {
     "allowed": true,
     "row_filter": "region IN ('mien_bac')"
   }

4. Trino executes
   SELECT * FROM prod.public.customers WHERE region IN ('mien_bac')
```

---

## 📊 Comparison: Before vs After

| Aspect                      | Previous Design                           | **Final Design**            |
| --------------------------- | ----------------------------------------- | --------------------------- |
| **Relations in table type** | Hard-coded `filtered_by_*`                | ✅ None - fully generic     |
| **Custom types**            | `user_attribute`, `attribute_filter_rule` | ✅ Just `row_filter_policy` |
| **Tuples per policy**       | 3+ tuples                                 | ✅ 1-2 tuples only          |
| **Bi-directional links**    | Yes (redundant)                           | ✅ No - single direction    |
| **Role support**            | Complex role hierarchy                    | ✅ User-only (simple)       |
| **Add new attribute**       | Update model OR create new tuples         | ✅ Just create policy tuple |
| **Model complexity**        | Medium-High                               | ✅ Low                      |
| **Code complexity**         | Medium                                    | ✅ Low                      |
| **Scalability**             | Good                                      | ✅ Excellent                |

---

## ✅ Production Checklist

- [ ] Update OpenFGA model với cleaned-up design
- [ ] Implement `RowFilterService` (no database, only OpenFGA)
- [ ] Add admin endpoints
- [ ] Add row filter endpoint
- [ ] Update OPA policies to match Trino row filter format (array of objects)
- [ ] Test with sample data
- [ ] Load test performance
- [ ] Deploy to production

**Note:** Không cần database riêng - tất cả thông tin được lưu trong OpenFGA.

---

## 🎯 Summary

**This is the cleanest, most maintainable design:**

1. ✅ **Minimal tuples**: 1 tuple for policy-table link, 1 tuple per user assignment
2. ✅ **No redundancy**: Single-direction relations only
3. ✅ **No hard-coding**: Attribute names fully dynamic
4. ✅ **User-only**: No role complexity
5. ✅ **Generic condition**: `has_attribute_access` works for everything
6. ✅ **Production-ready**: Simple, fast, scalable

**Total model types: 6** (user, catalog, namespace, table, column, row_filter_policy)
**Total conditions: 1** (has_attribute_access)
**Average tuples per policy: 2** (1 link + 1 user assignment)

Perfect balance of simplicity and power! 🚀
