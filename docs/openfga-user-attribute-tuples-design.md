# OpenFGA Row Filtering - User Attribute Tuples Approach

## Tổng quan

Approach này sử dụng một **single generic type** `user_attribute` để lưu trữ TẤT CẢ user attributes (region, department, role, etc.) thay vì tạo nhiều type riêng biệt. Attributes được lưu dưới dạng **key-value pairs** trong OpenFGA tuples.

### Key Idea

Instead of:

```typescript
type region
type department
type organization
```

We use:

```typescript
type user_attribute  // Generic container for ALL attributes
```

### Benefits

✅ **Minimal types** - Chỉ cần 1 type cho tất cả attributes  
✅ **Flexible** - Dễ dàng add attribute mới mà không cần modify model  
✅ **Scalable** - Không bị "type explosion"  
✅ **Simple model** - Easy to understand và maintain  
✅ **Dynamic** - Attribute values stored in condition context

### Trade-offs

⚠️ **Less type-safe** - Không có compile-time checking cho attribute values  
⚠️ **Harder to query** - Phải parse context để lấy values  
⚠️ **No built-in hierarchy** - Phải implement parent-child trong application code

---

## OpenFGA Model Design

### 1. Complete Model Schema

```typescript
model
  schema 1.2

# ============================================================================
# CORE TYPES (Keep existing)
# ============================================================================

type user

type role
  relations
    define assignee: [user, role#assignee] or ownership
    define can_assume: assignee or ownership
    define can_change_ownership: can_grant_assignee
    define can_delete: can_grant_assignee
    define can_grant_assignee: ownership
    define can_update: can_grant_assignee
    define ownership: [user, role#assignee]

type catalog
  relations
    define can_change_ownership: manage_grants
    define can_create_namespace: create
    define can_delete: modify
    define can_get_metadata: describe or can_get_metadata from namespace
    define can_grant_create: manage_grants or (create and pass_grants)
    define can_grant_describe: manage_grants or (describe and pass_grants)
    define can_grant_manage_grants: manage_grants
    define can_grant_modify: manage_grants or (modify and pass_grants)
    define can_grant_pass_grants: manage_grants
    define can_grant_select: manage_grants or (select and pass_grants)
    define can_include_in_list: can_get_metadata
    define can_list_everything: describe
    define can_list_namespaces: can_get_metadata
    define can_use: can_get_metadata
    define create: [user, role#assignee] or ownership
    define describe: [user, role#assignee] or ownership or select or create
    define manage_grants: [user, role#assignee] or ownership
    define modify: [user, role#assignee] or ownership
    define namespace: [namespace]
    define ownership: [user, role#assignee]
    define pass_grants: [user, role#assignee]
    define select: [user, role#assignee] or ownership or modify

type namespace
  relations
    define can_change_ownership: manage_grants
    define can_create_namespace: create
    define can_create_table: create
    define can_create_view: create
    define can_delete: modify
    define can_get_metadata: describe or can_get_metadata from child
    define can_grant_create: manage_grants or (create and pass_grants)
    define can_grant_describe: manage_grants or (describe and pass_grants)
    define can_grant_manage_grants: manage_grants
    define can_grant_modify: manage_grants or (modify and pass_grants)
    define can_grant_pass_grants: manage_grants
    define can_grant_select: manage_grants or (select and pass_grants)
    define can_include_in_list: can_get_metadata
    define can_list_everything: describe
    define can_list_namespaces: can_get_metadata
    define can_list_tables: can_get_metadata
    define can_list_views: can_get_metadata
    define can_read_assignments: can_grant_create or can_grant_describe or can_grant_modify or can_grant_select or can_grant_pass_grants or can_grant_manage_grants or can_change_ownership
    define can_set_managed_access: manage_grants
    define can_set_protection: modify
    define can_update_properties: modify
    define child: [namespace, table]
    define create: [user, role#assignee] or ownership or create from parent
    define describe: [user, role#assignee] or ownership or select or create or describe from parent
    define manage_grants: [user, role#assignee] or (ownership but not managed_access_inheritance from parent) or manage_grants from parent
    define managed_access: [user:*, role:*]
    define managed_access_inheritance: managed_access or managed_access_inheritance from parent
    define modify: [user, role#assignee] or ownership or modify from parent
    define ownership: [user, role#assignee]
    define parent: [namespace, catalog]
    define pass_grants: [user, role#assignee]
    define select: [user, role#assignee] or ownership or modify or select from parent

type table
  relations
    define can_change_ownership: manage_grants
    define can_commit: modify
    define can_control_tasks: modify
    define can_drop: modify
    define can_get_metadata: describe
    define can_get_tasks: describe
    define can_grant_describe: manage_grants or (describe and pass_grants)
    define can_grant_manage_grants: manage_grants
    define can_grant_modify: manage_grants or (modify and pass_grants)
    define can_grant_pass_grants: manage_grants
    define can_grant_select: manage_grants or (select and pass_grants)
    define can_include_in_list: can_get_metadata
    define can_read_assignments: can_grant_pass_grants or can_grant_manage_grants or can_grant_describe or can_grant_select or can_grant_modify or can_change_ownership
    define can_read_data: select
    define can_rename: modify
    define can_set_protection: modify
    define can_undrop: modify
    define can_write_data: modify
    define describe: [user, role#assignee] or ownership or select or describe from parent
    define manage_grants: [user, role#assignee] or (ownership but not managed_access_inheritance from parent) or manage_grants from parent
    define modify: [user, role#assignee] or ownership or modify from parent
    define ownership: [user, role#assignee]
    define parent: [namespace]
    define pass_grants: [user, role#assignee]
    define select: [user, role#assignee] or ownership or modify or select from parent

type column
  relations
    define parent: [table]
    define select: [user, role#assignee] or select from parent
    define mask: [user, role#assignee]

# ============================================================================
# NEW TYPE: user_attribute (Generic Attribute Container)
# ============================================================================

type user_attribute
  relations
    # User who owns this attribute
    define owner: [user, role#assignee]

    # Attribute value is set (with actual value in condition context)
    define has_value: [user with attribute_value_set, role#assignee with attribute_value_set]

    # Attribute can be used for filtering
    define is_filterable: [user:*]

    # Admin can manage this attribute
    define can_manage: [user, role#assignee]

# ============================================================================
# NEW TYPE: attribute_filter_rule (Filter Rules per Table/Column)
# ============================================================================

type attribute_filter_rule
  relations
    # Which table/column this rule applies to
    define applies_to_table: [table]
    define applies_to_column: [column]

    # Which attribute key this rule uses (e.g., "region", "department")
    define uses_attribute_key: [user:*]

    # Rule configuration
    define can_configure: [user, role#assignee]

# ============================================================================
# CONDITIONS
# ============================================================================

# Condition: Attribute value is set (non-empty)
condition attribute_value_set(
  attribute_value: string
) {
  attribute_value != "" && attribute_value != null
}

# Condition: Check if row value matches user's attribute value
condition row_matches_attribute(
  row_value: string,
  user_attribute_value: string
) {
  row_value == user_attribute_value
}

# Condition: Check if row value is in list of user attribute values
condition row_in_attribute_list(
  row_value: string,
  user_attribute_values: list
) {
  row_value in user_attribute_values
}

# Condition: Hierarchical matching with parent-child mapping
condition hierarchical_attribute_match(
  row_value: string,
  user_attribute_values: list,
  hierarchy_map: map
) {
  row_value in user_attribute_values ||
  (has(hierarchy_map[row_value]) && hierarchy_map[row_value] in user_attribute_values)
}
```

---

## Tuple Design Patterns

### 2. User Attribute Tuples

#### Pattern A: Single-Value Attribute

**User `sale_nam` có attribute `region` với value `mien_bac`**

```json
{
  "user": "user:sale_nam",
  "relation": "owner",
  "object": "user_attribute:sale_nam.region"
}
```

```json
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

**Explain:**

- Object ID format: `user_attribute:{user_id}.{attribute_key}`
- `attribute_value` stored in condition context
- Có thể add nhiều attributes cho cùng 1 user

#### Pattern B: Multi-Value Attribute

**User `regional_manager` có attribute `region` với multiple values**

```json
{
  "user": "user:regional_manager",
  "relation": "owner",
  "object": "user_attribute:regional_manager.region"
}
```

```json
{
  "user": "user:regional_manager",
  "relation": "has_value",
  "object": "user_attribute:regional_manager.region",
  "condition": {
    "name": "attribute_value_set",
    "context": {
      "attribute_value": "mien_bac,mien_trung" // Comma-separated
    }
  }
}
```

**Alternative: Separate tuples cho mỗi value**

```json
{
  "user": "user:regional_manager",
  "relation": "has_value",
  "object": "user_attribute:regional_manager.region.mien_bac",
  "condition": {
    "name": "attribute_value_set",
    "context": {
      "attribute_value": "mien_bac"
    }
  }
}
```

```json
{
  "user": "user:regional_manager",
  "relation": "has_value",
  "object": "user_attribute:regional_manager.region.mien_nam",
  "condition": {
    "name": "attribute_value_set",
    "context": {
      "attribute_value": "mien_nam"
    }
  }
}
```

#### Pattern C: Multiple Attribute Types

**User có cả `region` và `department`**

```json
// Region attribute
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

// Department attribute
{
  "user": "user:sale_nam",
  "relation": "has_value",
  "object": "user_attribute:sale_nam.department",
  "condition": {
    "name": "attribute_value_set",
    "context": {
      "attribute_value": "sales_hanoi"
    }
  }
}

// Employee ID attribute
{
  "user": "user:sale_nam",
  "relation": "has_value",
  "object": "user_attribute:sale_nam.employee_id",
  "condition": {
    "name": "attribute_value_set",
    "context": {
      "attribute_value": "EMP001"
    }
  }
}
```

### 3. Filter Rule Tuples

#### Pattern D: Table Filter Rule

**Table `customers` filters by `region` attribute**

```json
{
  "user": "table:prod.public.customers",
  "relation": "applies_to_table",
  "object": "attribute_filter_rule:customers_region_filter"
}
```

```json
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

**Metadata:** Table nào filter bằng attribute key nào

#### Pattern E: Column Filter Rule

**Column `customers.region` uses `region` attribute for filtering**

```json
{
  "user": "column:prod.public.customers.region",
  "relation": "applies_to_column",
  "object": "attribute_filter_rule:customers_region_column_filter"
}
```

```json
{
  "user": "user:*",
  "relation": "uses_attribute_key",
  "object": "attribute_filter_rule:customers_region_column_filter",
  "condition": {
    "name": "attribute_value_set",
    "context": {
      "attribute_value": "region"
    }
  }
}
```

---

## Permission API Implementation

### 4. Core Query Functions

```python
from typing import Dict, List, Optional, Set
from openfga_sdk import OpenFgaClient
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# Data Models
# ============================================================================

class UserAttribute(BaseModel):
    """Represents a user attribute"""
    user_id: str
    attribute_key: str  # e.g., "region", "department"
    attribute_values: List[str]  # e.g., ["mien_bac", "mien_trung"]

class FilterRule(BaseModel):
    """Represents a filter rule for a table/column"""
    rule_id: str
    table_fqn: Optional[str] = None
    column_fqn: Optional[str] = None
    attribute_key: str  # Which attribute to use for filtering
    column_name: str  # Column name in table for SQL


# ============================================================================
# OpenFGA Query Functions
# ============================================================================

async def get_user_attributes(
    user_id: str,
    attribute_key: Optional[str] = None
) -> List[UserAttribute]:
    """
    Get all attributes for a user from OpenFGA

    Args:
        user_id: User identifier
        attribute_key: Optional filter by specific attribute key

    Returns:
        List of UserAttribute objects

    Example:
        >>> attrs = await get_user_attributes("sale_nam")
        >>> # Returns: [
        >>> #   UserAttribute(user_id="sale_nam", attribute_key="region", attribute_values=["mien_bac"]),
        >>> #   UserAttribute(user_id="sale_nam", attribute_key="department", attribute_values=["sales_hanoi"])
        >>> # ]
    """
    client = get_openfga_client()

    # Query: Find all user_attribute objects owned by this user
    owner_tuples = await client.read(
        user=f"user:{user_id}",
        relation="owner"
    )

    attributes = []

    for tuple in owner_tuples.tuples:
        # Extract attribute key from object ID
        # Format: user_attribute:{user_id}.{attribute_key}[.{value}]
        obj_id = tuple.object.replace("user_attribute:", "")
        parts = obj_id.split(".")

        if len(parts) < 2:
            continue

        attr_user_id = parts[0]
        attr_key = parts[1]

        # Skip if filtering by specific key
        if attribute_key and attr_key != attribute_key:
            continue

        # Get attribute values by querying has_value relation
        values = await get_attribute_values(user_id, attr_key)

        if values:
            attributes.append(UserAttribute(
                user_id=user_id,
                attribute_key=attr_key,
                attribute_values=values
            ))

    return attributes


async def get_attribute_values(user_id: str, attribute_key: str) -> List[str]:
    """
    Get all values for a specific user attribute

    Args:
        user_id: User identifier
        attribute_key: Attribute key (e.g., "region")

    Returns:
        List of attribute values

    Example:
        >>> values = await get_attribute_values("sale_nam", "region")
        >>> # Returns: ["mien_bac"]
    """
    client = get_openfga_client()

    # Query: Find all has_value tuples for this attribute
    # Pattern 1: Single tuple with object user_attribute:{user_id}.{attribute_key}
    value_tuples = await client.read(
        user=f"user:{user_id}",
        relation="has_value"
    )

    values = []

    for tuple in value_tuples.tuples:
        obj_id = tuple.object.replace("user_attribute:", "")

        # Check if this tuple is for the requested attribute key
        if not obj_id.startswith(f"{user_id}.{attribute_key}"):
            continue

        # Extract value from condition context
        if tuple.condition and tuple.condition.context:
            attr_value = tuple.condition.context.get("attribute_value")

            if attr_value:
                # Handle comma-separated values
                if "," in attr_value:
                    values.extend([v.strip() for v in attr_value.split(",")])
                else:
                    values.append(attr_value)

    # Remove duplicates and return
    return list(set(values))


async def get_table_filter_rules(table_fqn: str) -> List[FilterRule]:
    """
    Get all filter rules that apply to a table

    Args:
        table_fqn: Fully qualified table name (e.g., "prod.public.customers")

    Returns:
        List of FilterRule objects

    Example:
        >>> rules = await get_table_filter_rules("prod.public.customers")
        >>> # Returns: [
        >>> #   FilterRule(rule_id="customers_region_filter", table_fqn="...",
        >>> #              attribute_key="region", column_name="region")
        >>> # ]
    """
    client = get_openfga_client()

    # Query: Find all filter rules that apply to this table
    rule_tuples = await client.read(
        user=f"table:{table_fqn}",
        relation="applies_to_table"
    )

    rules = []

    for tuple in rule_tuples.tuples:
        rule_id = tuple.object.replace("attribute_filter_rule:", "")

        # Get attribute key used by this rule
        attribute_key = await get_rule_attribute_key(rule_id)

        if attribute_key:
            # Infer column name from attribute key (or store in metadata)
            column_name = attribute_key  # Simple mapping

            rules.append(FilterRule(
                rule_id=rule_id,
                table_fqn=table_fqn,
                attribute_key=attribute_key,
                column_name=column_name
            ))

    return rules


async def get_column_filter_rules(column_fqn: str) -> List[FilterRule]:
    """
    Get filter rules that apply to a specific column

    Args:
        column_fqn: Fully qualified column name

    Returns:
        List of FilterRule objects
    """
    client = get_openfga_client()

    rule_tuples = await client.read(
        user=f"column:{column_fqn}",
        relation="applies_to_column"
    )

    rules = []

    for tuple in rule_tuples.tuples:
        rule_id = tuple.object.replace("attribute_filter_rule:", "")
        attribute_key = await get_rule_attribute_key(rule_id)

        if attribute_key:
            column_name = column_fqn.split(".")[-1]

            rules.append(FilterRule(
                rule_id=rule_id,
                column_fqn=column_fqn,
                attribute_key=attribute_key,
                column_name=column_name
            ))

    return rules


async def get_rule_attribute_key(rule_id: str) -> Optional[str]:
    """
    Get the attribute key used by a filter rule

    Args:
        rule_id: Filter rule ID

    Returns:
        Attribute key string or None
    """
    client = get_openfga_client()

    # Query: Find uses_attribute_key tuples
    tuples = await client.read(
        user="user:*",
        relation="uses_attribute_key",
        object=f"attribute_filter_rule:{rule_id}"
    )

    for tuple in tuples.tuples:
        if tuple.condition and tuple.condition.context:
            return tuple.condition.context.get("attribute_value")

    return None


# ============================================================================
# Filter Expression Builder
# ============================================================================

async def build_row_filter_expression(
    user_id: str,
    table_fqn: str
) -> Optional[str]:
    """
    Build SQL WHERE clause for row filtering

    Flow:
    1. Get filter rules for table
    2. For each rule, get user's attribute values
    3. Build SQL IN clause
    4. Combine with OR logic

    Args:
        user_id: User identifier
        table_fqn: Fully qualified table name

    Returns:
        SQL filter expression or None

    Example:
        >>> expr = await build_row_filter_expression("sale_nam", "prod.public.customers")
        >>> # Returns: "region IN ('mien_bac')"
    """
    # Step 1: Get filter rules for table
    filter_rules = await get_table_filter_rules(table_fqn)

    if not filter_rules:
        logger.info(f"No filter rules for table {table_fqn}")
        return None

    # Step 2: Build filter for each rule
    filter_clauses = []

    for rule in filter_rules:
        # Get user's values for this attribute
        attribute_values = await get_attribute_values(user_id, rule.attribute_key)

        if not attribute_values:
            logger.warning(
                f"User {user_id} has no values for attribute {rule.attribute_key}, "
                f"blocking access to table {table_fqn}"
            )
            # User has no values for this required attribute -> deny all
            return "1=0"

        # Build SQL IN clause
        safe_values = [sanitize_sql_value(v) for v in attribute_values]
        values_str = "', '".join(safe_values)
        filter_clauses.append(f"{rule.column_name} IN ('{values_str}')")

    if not filter_clauses:
        return None

    # Step 3: Combine filters
    # Use OR: user can see rows matching ANY attribute
    # Use AND: user must match ALL attributes (more restrictive)

    if len(filter_clauses) == 1:
        return filter_clauses[0]

    # OR logic: permissive
    return f"({' OR '.join(filter_clauses)})"

    # AND logic: restrictive (uncomment if needed)
    # return f"({' AND '.join(filter_clauses)})"


def sanitize_sql_value(value: str) -> str:
    """
    Sanitize SQL value to prevent injection

    Args:
        value: Raw value

    Returns:
        Sanitized value
    """
    # Remove dangerous characters
    sanitized = value.replace("'", "").replace(";", "").replace("--", "")
    sanitized = sanitized.replace("\\", "").replace("\n", "").replace("\r", "")

    # Limit length
    return sanitized[:100]


# ============================================================================
# FastAPI Endpoint
# ============================================================================

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class RowFilterRequest(BaseModel):
    user_id: str
    resource: Dict[str, str]  # catalog_name, schema_name, table_name

class RowFilterResponse(BaseModel):
    filter_expression: Optional[str]
    filter_metadata: Optional[Dict] = None

@router.post("/permissions/row-filter", response_model=RowFilterResponse)
async def get_row_filter(request: RowFilterRequest):
    """
    Generate row filter expression using user attributes from OpenFGA

    Request body:
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
        "filter_metadata": {
            "user_attributes": {...},
            "applied_rules": [...]
        }
    }
    """
    user_id = request.user_id
    resource = request.resource

    # Build table FQN
    table_fqn = f"{resource['catalog_name']}.{resource['schema_name']}.{resource['table_name']}"

    try:
        # Get user attributes for debugging
        user_attributes = await get_user_attributes(user_id)

        # Get filter rules
        filter_rules = await get_table_filter_rules(table_fqn)

        # Build filter expression
        filter_expr = await build_row_filter_expression(user_id, table_fqn)

        # Build metadata
        metadata = {
            "user_attributes": {
                attr.attribute_key: attr.attribute_values
                for attr in user_attributes
            },
            "applied_rules": [
                {
                    "rule_id": rule.rule_id,
                    "attribute_key": rule.attribute_key,
                    "column_name": rule.column_name
                }
                for rule in filter_rules
            ],
            "table": table_fqn
        }

        logger.info(
            f"Row filter for user={user_id}, table={table_fqn}: "
            f"filter={filter_expr}, metadata={metadata}"
        )

        return RowFilterResponse(
            filter_expression=filter_expr,
            filter_metadata=metadata
        )

    except Exception as e:
        logger.error(f"Error generating row filter: {e}", exc_info=True)

        # Fail closed: deny all access on error
        return RowFilterResponse(
            filter_expression="1=0",
            filter_metadata={"error": str(e)}
        )


def get_openfga_client() -> OpenFgaClient:
    """Get configured OpenFGA client instance"""
    # Implementation depends on your setup
    # This is a placeholder
    from app.config import settings

    client = OpenFgaClient(
        api_url=settings.OPENFGA_API_URL,
        store_id=settings.OPENFGA_STORE_ID,
        authorization_model_id=settings.OPENFGA_MODEL_ID
    )

    return client


# ============================================================================
# Admin Functions - Manage User Attributes
# ============================================================================

async def set_user_attribute(
    user_id: str,
    attribute_key: str,
    attribute_values: List[str]
) -> bool:
    """
    Set attribute values for a user

    Args:
        user_id: User identifier
        attribute_key: Attribute key (e.g., "region")
        attribute_values: List of values to set

    Returns:
        True if successful

    Example:
        >>> await set_user_attribute("sale_nam", "region", ["mien_bac", "ha_noi"])
    """
    client = get_openfga_client()

    # Delete existing attribute values
    await delete_user_attribute(user_id, attribute_key)

    # Write new tuples
    tuples = []

    # Owner tuple
    tuples.append({
        "user": f"user:{user_id}",
        "relation": "owner",
        "object": f"user_attribute:{user_id}.{attribute_key}"
    })

    # Value tuples
    # Option 1: Single tuple with comma-separated values
    if len(attribute_values) == 1:
        tuples.append({
            "user": f"user:{user_id}",
            "relation": "has_value",
            "object": f"user_attribute:{user_id}.{attribute_key}",
            "condition": {
                "name": "attribute_value_set",
                "context": {
                    "attribute_value": attribute_values[0]
                }
            }
        })
    else:
        # Option 2: Multiple tuples (one per value)
        for value in attribute_values:
            tuples.append({
                "user": f"user:{user_id}",
                "relation": "has_value",
                "object": f"user_attribute:{user_id}.{attribute_key}.{value}",
                "condition": {
                    "name": "attribute_value_set",
                    "context": {
                        "attribute_value": value
                    }
                }
            })

    await client.write(tuples=tuples)
    logger.info(f"Set attribute {attribute_key} for user {user_id}: {attribute_values}")

    return True


async def delete_user_attribute(user_id: str, attribute_key: str) -> bool:
    """
    Delete all values for a user attribute

    Args:
        user_id: User identifier
        attribute_key: Attribute key to delete

    Returns:
        True if successful
    """
    client = get_openfga_client()

    # Find all tuples to delete
    tuples_to_delete = []

    # Find owner tuples
    owner_tuples = await client.read(
        user=f"user:{user_id}",
        relation="owner"
    )

    for tuple in owner_tuples.tuples:
        obj_id = tuple.object.replace("user_attribute:", "")
        if obj_id.startswith(f"{user_id}.{attribute_key}"):
            tuples_to_delete.append({
                "user": tuple.user,
                "relation": tuple.relation,
                "object": tuple.object
            })

    # Find has_value tuples
    value_tuples = await client.read(
        user=f"user:{user_id}",
        relation="has_value"
    )

    for tuple in value_tuples.tuples:
        obj_id = tuple.object.replace("user_attribute:", "")
        if obj_id.startswith(f"{user_id}.{attribute_key}"):
            tuples_to_delete.append({
                "user": tuple.user,
                "relation": tuple.relation,
                "object": tuple.object
            })

    if tuples_to_delete:
        await client.write(deletes=tuples_to_delete)
        logger.info(f"Deleted {len(tuples_to_delete)} tuples for {user_id}.{attribute_key}")

    return True
```

---

## Migration Scripts

### 5. Setup OpenFGA

```python
#!/usr/bin/env python3
"""
Setup script for user attribute tuples approach
"""
import asyncio
from openfga_sdk import OpenFgaClient

async def setup_filter_rules():
    """Create filter rules for tables"""
    client = get_openfga_client()

    tuples = [
        # ===== Customers Table =====

        # Rule: customers table filters by region
        {
            "user": "table:prod.public.customers",
            "relation": "applies_to_table",
            "object": "attribute_filter_rule:customers_region_filter"
        },
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
        },

        # Rule: customers table also filters by department
        {
            "user": "table:prod.public.customers",
            "relation": "applies_to_table",
            "object": "attribute_filter_rule:customers_department_filter"
        },
        {
            "user": "user:*",
            "relation": "uses_attribute_key",
            "object": "attribute_filter_rule:customers_department_filter",
            "condition": {
                "name": "attribute_value_set",
                "context": {
                    "attribute_value": "department"
                }
            }
        },

        # ===== Orders Table =====

        {
            "user": "table:prod.public.orders",
            "relation": "applies_to_table",
            "object": "attribute_filter_rule:orders_region_filter"
        },
        {
            "user": "user:*",
            "relation": "uses_attribute_key",
            "object": "attribute_filter_rule:orders_region_filter",
            "condition": {
                "name": "attribute_value_set",
                "context": {
                    "attribute_value": "region"
                }
            }
        },

        # ===== Employees Table =====

        {
            "user": "table:prod.public.employees",
            "relation": "applies_to_table",
            "object": "attribute_filter_rule:employees_department_filter"
        },
        {
            "user": "user:*",
            "relation": "uses_attribute_key",
            "object": "attribute_filter_rule:employees_department_filter",
            "condition": {
                "name": "attribute_value_set",
                "context": {
                    "attribute_value": "department"
                }
            }
        },
    ]

    await client.write(tuples=tuples)
    print(f"✅ Created {len(tuples)} filter rule tuples")


async def setup_sample_user_attributes():
    """Create sample user attributes"""

    # User: sale_nam
    await set_user_attribute(
        user_id="sale_nam",
        attribute_key="region",
        attribute_values=["mien_bac"]
    )
    await set_user_attribute(
        user_id="sale_nam",
        attribute_key="department",
        attribute_values=["sales_hanoi"]
    )

    # User: sale_hung
    await set_user_attribute(
        user_id="sale_hung",
        attribute_key="region",
        attribute_values=["mien_nam"]
    )
    await set_user_attribute(
        user_id="sale_hung",
        attribute_key="department",
        attribute_values=["sales_hcm"]
    )

    # User: regional_coordinator (multi-region)
    await set_user_attribute(
        user_id="regional_coordinator",
        attribute_key="region",
        attribute_values=["mien_bac", "mien_trung"]
    )

    # User: hr_admin
    await set_user_attribute(
        user_id="hr_admin",
        attribute_key="department",
        attribute_values=["hr", "admin"]
    )

    print("✅ Created sample user attributes")


async def main():
    print("🚀 Setting up user attribute tuples...\n")

    await setup_filter_rules()
    await setup_sample_user_attributes()

    print("\n✅ Setup complete!")
    print("\nTest with:")
    print("  curl -X POST http://localhost:8080/permissions/row-filter \\")
    print("    -H 'Content-Type: application/json' \\")
    print("    -d '{")
    print('      "user_id": "sale_nam",')
    print('      "resource": {')
    print('        "catalog_name": "prod",')
    print('        "schema_name": "public",')
    print('        "table_name": "customers"')
    print("      }")
    print("    }'")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Testing

### 6. Test Cases

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_single_region_filter():
    """Test user with single region attribute"""

    # Setup
    await set_user_attribute("test_user_1", "region", ["mien_bac"])

    # Test
    values = await get_attribute_values("test_user_1", "region")
    assert values == ["mien_bac"]

    # Build filter
    filter_expr = await build_row_filter_expression(
        "test_user_1",
        "prod.public.customers"
    )
    assert filter_expr == "region IN ('mien_bac')"


@pytest.mark.asyncio
async def test_multi_region_filter():
    """Test user with multiple regions"""

    await set_user_attribute("test_user_2", "region", ["mien_bac", "mien_nam"])

    filter_expr = await build_row_filter_expression(
        "test_user_2",
        "prod.public.customers"
    )
    assert filter_expr == "region IN ('mien_bac', 'mien_nam')"


@pytest.mark.asyncio
async def test_no_attributes_deny_all():
    """Test user with no attributes gets denied"""

    # User has no region attribute
    filter_expr = await build_row_filter_expression(
        "test_user_3",
        "prod.public.customers"
    )
    assert filter_expr == "1=0"  # Deny all


@pytest.mark.asyncio
async def test_multiple_attribute_types():
    """Test user with both region and department"""

    await set_user_attribute("test_user_4", "region", ["mien_bac"])
    await set_user_attribute("test_user_4", "department", ["sales"])

    attrs = await get_user_attributes("test_user_4")
    assert len(attrs) == 2
    assert any(a.attribute_key == "region" for a in attrs)
    assert any(a.attribute_key == "department" for a in attrs)


@pytest.mark.asyncio
async def test_api_endpoint(client: AsyncClient):
    """Test API endpoint"""

    await set_user_attribute("sale_nam", "region", ["mien_bac"])

    response = await client.post("/permissions/row-filter", json={
        "user_id": "sale_nam",
        "resource": {
            "catalog_name": "prod",
            "schema_name": "public",
            "table_name": "customers"
        }
    })

    assert response.status_code == 200
    data = response.json()

    assert data["filter_expression"] == "region IN ('mien_bac')"
    assert data["filter_metadata"]["user_attributes"]["region"] == ["mien_bac"]
```

---

## Object ID Naming Conventions

### 7. Standard Formats

```
# User Attribute Objects
user_attribute:{user_id}.{attribute_key}
Examples:
  - user_attribute:sale_nam.region
  - user_attribute:sale_nam.department
  - user_attribute:admin_01.role

# Multi-value variant (one tuple per value)
user_attribute:{user_id}.{attribute_key}.{value}
Examples:
  - user_attribute:regional_manager.region.mien_bac
  - user_attribute:regional_manager.region.mien_nam

# Filter Rule Objects
attribute_filter_rule:{table_name}_{attribute_key}_filter
Examples:
  - attribute_filter_rule:customers_region_filter
  - attribute_filter_rule:employees_department_filter

# Column-specific rules
attribute_filter_rule:{table_name}_{column_name}_{attribute_key}_filter
Examples:
  - attribute_filter_rule:customers_region_region_filter
```

---

## Comparison với Other Approaches

### 8. Pros & Cons

| Aspect           | User Attribute Tuples | New Types         | Conditions Only |
| ---------------- | --------------------- | ----------------- | --------------- |
| **Types needed** | ✅ 2 types            | ❌ 5+ types       | ✅ 1 type       |
| **Flexibility**  | ✅✅ Very High        | ⚠️ Medium         | ✅✅ Very High  |
| **Type Safety**  | ⚠️ Low (strings)      | ✅ High           | ⚠️ Low          |
| **Query Speed**  | ⚠️ Medium             | ✅ Fast           | ❌ Slow         |
| **Scalability**  | ✅ Excellent          | ⚠️ Type explosion | ✅ Excellent    |
| **Hierarchies**  | ❌ App logic          | ✅ Native         | ❌ App logic    |
| **Audit**        | ✅ Good               | ✅✅ Excellent    | ⚠️ Medium       |
| **Maintenance**  | ✅ Easy               | ❌ Complex        | ✅ Easy         |

---

## Summary

Approach này cung cấp:

✅ **Minimal model** - Chỉ 2 type mới (`user_attribute`, `attribute_filter_rule`)  
✅ **Generic storage** - 1 pattern cho tất cả attributes  
✅ **Easy to extend** - Add attribute mới không cần modify model  
✅ **Clear separation** - User attributes vs Filter rules  
✅ **Admin-friendly** - Simple CRUD operations

Best for:

- Projects muốn minimize model complexity
- Frequent attribute changes
- Many different attribute types
- Small to medium scale (< 10k users)

Not ideal for:

- Cần complex hierarchies (use New Types)
- High performance requirements (use New Types với caching)
- Strict type safety requirements

---

## Next Steps

1. ✅ Review model schema
2. ✅ Test với sample data
3. ⏳ Implement admin UI để manage attributes
4. ⏳ Add caching layer
5. ⏳ Performance testing

---

## References

- [OpenFGA Conditions](https://openfga.dev/docs/modeling/conditions)
- [OpenFGA Best Practices](https://openfga.dev/docs/modeling/best-practices)
- [CEL Language Specification](https://github.com/google/cel-spec)
