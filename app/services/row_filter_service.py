"""
Row filter service - Build SQL filters from OpenFGA row filter policies
"""

import logging
from typing import List, Optional, Tuple, Union

from app.external.openfga_client import OpenFGAManager
from app.schemas.row_filter import (
    BatchRowFilterRequest,
    BatchRowFilterResponse,
    RowFilterExpression,
    RowFilterPolicyGrant,
    RowFilterPolicyGrantResponse,
    RowFilterPolicyInfo,
)
from app.utils.operation_mapper import (
    build_user_identifier,
    build_user_identifier_with_type,
)
from app.utils.type_mapper import FGA_TYPE_LAKEKEEPER_TABLE

logger = logging.getLogger(__name__)


def parse_column_from_policy_id(policy_id: str) -> Optional[str]:
    """
    Extract column name from policy ID.

    Supported formats:
    - New: "{catalog}.{schema}.{table}.{column}"  -> "column"
    - Old: "{table}_{column}_filter"              -> "column"
    """
    if not policy_id:
        return None

    # New format: fully-qualified column path
    if "." in policy_id:
        parts = [p for p in policy_id.split(".") if p]
        return parts[-1] if len(parts) >= 4 else None

    # Old format (legacy): {table}_{column}_filter
    parts = policy_id.replace("_filter", "").split("_")
    if len(parts) >= 2:
        return parts[-1]
    return None


def escape_sql_value(value: Union[str, int, float]) -> str:
    """
    Escape SQL value to prevent injection.
    Accepts strings and numbers (int, float); numbers are converted to string.

    Args:
        value: Raw value (string or number)

    Returns:
        Escaped value as string
    """
    s = str(value)
    # Remove dangerous characters
    sanitized = s.replace("'", "''").replace(";", "").replace("--", "")
    sanitized = sanitized.replace("\\", "").replace("\n", "").replace("\r", "")
    # Limit length
    return sanitized[:100]


class RowFilterService:
    """Service for building row filter SQL expressions from OpenFGA"""

    def __init__(self, openfga: OpenFGAManager):
        """
        Initialize row filter service

        Args:
            openfga: OpenFGA manager instance
        """
        self.openfga = openfga

    async def get_table_policies(self, table_fqn: str) -> List[str]:
        """
        Get all policy IDs for a table from OpenFGA

        Args:
            table_fqn: Fully qualified table name (e.g., "prod.public.customers")

        Returns:
            List of policy IDs (e.g., ["lakekeeper_bronze.finance.user.region"])
        """
        try:
            # Use FGA v3 type: lakekeeper_table instead of table
            tuples = await self.openfga.read_tuples(
                user=f"{FGA_TYPE_LAKEKEEPER_TABLE}:{table_fqn}",
                relation="applies_to",
            )

            policy_ids = []
            for tuple_item in tuples:
                # OpenFGA SDK: object is in tuple_item.key.object
                tuple_key = getattr(tuple_item, "key", None)
                if not tuple_key:
                    continue

                object_id = getattr(tuple_key, "object", "")
                if object_id.startswith("row_filter_policy:"):
                    policy_id = object_id.replace("row_filter_policy:", "")
                    policy_ids.append(policy_id)

            logger.debug(
                f"Found {len(policy_ids)} policies for table {table_fqn}: {policy_ids}"
            )
            return policy_ids

        except Exception as e:
            logger.error(
                f"Error getting policies for table {table_fqn}: {e}",
                exc_info=True,
            )
            return []

    async def get_user_policy_filters(
        self, user_id: str, policy_ids: List[str]
    ) -> List[dict]:
        """
        Get user's filters from all policies

        This method checks both:
        1. Direct user permissions: user -> viewer -> policy
        2. Role-based permissions: role#assignee -> viewer -> policy (for roles the user is assigned to)

        Args:
            user_id: User identifier
            policy_ids: List of policy IDs

        Returns:
            List of filter dicts with keys: policy_id, attribute_name, column_name, allowed_values
        """
        filters = []

        # First, get all roles the user is assigned to
        user_roles = await self._get_user_roles(user_id)
        logger.debug(f"User {user_id} is assigned to roles: {user_roles}")

        for policy_id in policy_ids:
            policy_object_id = f"row_filter_policy:{policy_id}"

            # Build list of users to query (direct user + role usersets)
            users_to_query = [f"user:{user_id}"]
            for role in user_roles:
                users_to_query.append(f"role:{role}#assignee")

            for query_user in users_to_query:
                try:
                    # Query: user/role#assignee -> viewer -> policy
                    tuples = await self.openfga.read_tuples(
                        user=query_user,
                        relation="viewer",
                        object_id=policy_object_id,
                    )

                    if not tuples:
                        logger.debug(
                            f"{query_user} has no access to policy {policy_id}"
                        )
                        continue

                    for tuple_item in tuples:
                        # OpenFGA SDK: condition is in tuple_item.key.condition
                        tuple_key = getattr(tuple_item, "key", None)
                        if not tuple_key:
                            logger.warning(
                                f"Tuple for {query_user} and policy {policy_id} has no key"
                            )
                            continue

                        condition = getattr(tuple_key, "condition", None)
                        if not condition:
                            logger.warning(
                                f"Tuple for {query_user} and policy {policy_id} has no condition"
                            )
                            continue

                        ctx = getattr(condition, "context", None)
                        if not ctx:
                            logger.warning(
                                f"Tuple condition for {query_user} and policy {policy_id} has no context"
                            )
                            continue

                        # Extract attribute_name and allowed_values from context
                        # Context should be a dict with attribute_name and allowed_values
                        if isinstance(ctx, dict):
                            attribute_name = ctx.get("attribute_name")
                            allowed_values = ctx.get("allowed_values", [])
                        else:
                            # Try to access as object attributes
                            attribute_name = getattr(
                                ctx, "attribute_name", None
                            )
                            allowed_values = getattr(ctx, "allowed_values", [])
                            # If still None, try to convert to dict
                            if attribute_name is None:
                                try:
                                    ctx_dict = (
                                        dict(ctx)
                                        if hasattr(ctx, "__iter__")
                                        else {}
                                    )
                                    attribute_name = ctx_dict.get(
                                        "attribute_name"
                                    )
                                    allowed_values = ctx_dict.get(
                                        "allowed_values", []
                                    )
                                except Exception:
                                    pass

                        if not attribute_name or not allowed_values:
                            logger.warning(
                                f"Invalid condition context for {query_user} and policy {policy_id}: "
                                f"attribute_name={attribute_name}, allowed_values={allowed_values}"
                            )
                            continue

                        # Parse column name from policy_id
                        column_name = parse_column_from_policy_id(policy_id)
                        if not column_name:
                            logger.warning(
                                f"Cannot parse column from policy_id {policy_id}"
                            )
                            continue

                        # Check if we already have a filter for this policy (avoid duplicates)
                        existing_policy_ids = [f["policy_id"] for f in filters]
                        if policy_id in existing_policy_ids:
                            logger.debug(
                                f"Policy {policy_id} already in filters, skipping duplicate from {query_user}"
                            )
                            continue

                        filters.append(
                            {
                                "policy_id": policy_id,
                                "attribute_name": attribute_name,
                                "column_name": column_name,
                                "allowed_values": allowed_values,
                                "source": query_user,  # Track where this filter came from
                            }
                        )
                        logger.info(
                            f"Found row filter policy: {policy_id} for {query_user}, "
                            f"attribute={attribute_name}, values={allowed_values}"
                        )
                        # Found filter for this policy, no need to check other users
                        break

                except Exception as e:
                    logger.error(
                        f"Error getting filters for {query_user} and policy {policy_id}: {e}",
                        exc_info=True,
                    )
                    continue

        return filters

    async def _get_user_roles(self, user_id: str) -> List[str]:
        """
        Get all roles that a user is assigned to

        Args:
            user_id: User identifier

        Returns:
            List of role names the user is assigned to
        """
        try:
            # Query: user -> assignee -> role:*
            role_objects = await self.openfga.list_objects(
                user=f"user:{user_id}",
                relation="assignee",
                object_type="role",
            )

            # Extract role names from object IDs (format: role:role_name)
            roles = []
            for role_obj in role_objects:
                if role_obj.startswith("role:"):
                    role_name = role_obj.replace("role:", "")
                    roles.append(role_name)

            logger.debug(f"User {user_id} is assigned to roles: {roles}")
            return roles

        except Exception as e:
            logger.warning(f"Error getting roles for user {user_id}: {e}")
            return []

    async def build_row_filter_sql(
        self, user_id: str, table_fqn: str
    ) -> Optional[str]:
        """
        Build SQL WHERE clause for row filtering

        Row filter is opt-in: if a user has select permission on a table but no
        policy access, they can see all rows (no filter applied). Filters are only
        applied for policies the user has explicit access to.

        Args:
            user_id: User identifier
            table_fqn: Fully qualified table name (e.g., "prod.public.customers")

        Returns:
            SQL WHERE clause (e.g., "region IN ('north')") or None if no filter
            - None: No filter applied (user can see all rows if they have select permission)
            - SQL string: Filter to apply based on user's policy access
        """
        try:
            # Get policies for table
            policy_ids = await self.get_table_policies(table_fqn)
            if not policy_ids:
                logger.debug(f"No policies found for table {table_fqn}")
                return None

            # Get user's filters
            filters = await self.get_user_policy_filters(user_id, policy_ids)
            if not filters:
                # User has no access to any policies - this is OK, row filter is opt-in
                # If user has select permission on table, they can see all rows
                logger.info(
                    f"User {user_id} has no access to any policies for table {table_fqn}. "
                    f"Row filter is opt-in - returning no filter (user can see all rows if they have select permission)."
                )
                return None  # No filter - user can see all rows

            # User has access to some policies - apply filters only for those policies
            # Note: It's OK if user doesn't have access to all policies - we only filter
            # based on policies they DO have access to
            if len(filters) < len(policy_ids):
                logger.info(
                    f"User {user_id} has access to {len(filters)} out of {len(policy_ids)} policies "
                    f"for table {table_fqn}. Applying filters only for accessible policies."
                )

            # Build SQL clauses
            clauses = []

            for f in filters:
                # Check wildcard
                if "*" in f["allowed_values"]:
                    logger.debug(
                        f"Wildcard detected for user {user_id}, policy {f['policy_id']}, skipping filter"
                    )
                    continue  # Skip this filter

                # Build SQL IN clause
                values = [escape_sql_value(v) for v in f["allowed_values"]]
                values_str = "', '".join(values)
                clauses.append(f"{f['column_name']} IN ('{values_str}')")

            if not clauses:
                # All wildcards - no filter needed
                logger.debug(
                    f"All filters are wildcards for user {user_id} and table {table_fqn}"
                )
                return None

            # Combine with AND
            result = " AND ".join(clauses) if len(clauses) > 1 else clauses[0]

            logger.info(
                f"Built row filter for user={user_id}, table={table_fqn}: {result}"
            )
            return result

        except Exception as e:
            logger.error(
                f"Error building row filter for user {user_id} and table {table_fqn}: {e}",
                exc_info=True,
            )
            # Fail closed - deny all on error
            return "1=0"

    def build_row_filter_policy_identifier(
        self, resource, attribute_name: str
    ) -> Tuple[str, str, str]:
        """
        Build row_filter_policy identifier from resource and attribute name

        Policy ID format (NEW): {catalog}.{schema}.{table}.{attribute_name}
        Example: "lakekeeper_bronze.finance.user.region"

        Args:
            resource: Resource specification (must have catalog, schema, table)
            attribute_name: Attribute name (e.g., "region", "department")

        Returns:
            Tuple of (object_id, resource_type, resource_id)

        Raises:
            ValueError: If resource or attribute_name is invalid
        """
        # Validate resource has table information
        schema_name = resource.schema
        if not (resource.catalog and schema_name and resource.table):
            raise ValueError(
                "Row filter policy requires catalog, schema, and table. "
                'Example: {"catalog": "lakekeeper_bronze", "schema": "finance", "table": "user"}'
            )

        if not attribute_name:
            raise ValueError(
                "Row filter policy requires attribute_name. "
                'Example: "region"'
            )

        # Build policy ID (fully-qualified column path).
        # IMPORTANT: do NOT use "_" as a separator since catalog/schema/table can contain "_"
        schema_name = resource.schema
        table_name = resource.table
        policy_id = (
            f"{resource.catalog}.{schema_name}.{table_name}.{attribute_name}"
        )

        # Build object_id
        object_id = f"row_filter_policy:{policy_id}"
        resource_type = "row_filter_policy"
        resource_id = policy_id

        logger.info(
            f"Built row filter policy identifier: policy_id={policy_id}, "
            f"table={resource.catalog}.{schema_name}.{table_name}, "
            f"attribute={attribute_name}"
        )

        return object_id, resource_type, resource_id

    async def ensure_policy_table_link(self, resource, policy_object_id: str):
        """
        Ensure policy-to-table link exists in OpenFGA

        Creates tuple: table:{catalog}.{schema}.{table} --applies_to--> row_filter_policy:{policy_id}

        Args:
            resource: Resource specification
            policy_object_id: Policy object ID (e.g., "row_filter_policy:lakekeeper_bronze.finance.user.region")
        """
        try:
            schema_name = resource.schema
            table_fqn = f"{resource.catalog}.{schema_name}.{resource.table}"
            # Use FGA v3 type: lakekeeper_table instead of table
            table_object_id = f"{FGA_TYPE_LAKEKEEPER_TABLE}:{table_fqn}"

            # Check if link already exists
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

            # Create the link
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

    async def grant_row_filter_policy(
        self, grant: RowFilterPolicyGrant
    ) -> RowFilterPolicyGrantResponse:
        """
        Grant row filter policy to user

        Args:
            grant: Row filter policy grant request

        Returns:
            Row filter policy grant response

        Raises:
            ValueError: If resource specification is invalid
        """
        logger.info(
            f"Granting row filter policy: user={grant.user_id}, "
            f"resource={grant.resource.model_dump(exclude_none=True)}, "
            f"attribute={grant.attribute_name}, allowed_values={grant.allowed_values}"
        )

        # Validate resource has table
        if not grant.resource.table:
            raise ValueError(
                "Row filter policy grant requires table in resource. "
                'Example: {"catalog": "lakekeeper_bronze", "schema": "finance", "table": "user"}'
            )

        # Build policy identifier
        object_id, resource_type, policy_id = (
            self.build_row_filter_policy_identifier(
                grant.resource, grant.attribute_name
            )
        )

        # Build user identifier based on user_type
        user = build_user_identifier_with_type(
            grant.user_id, grant.user_type.value
        )

        # Build condition dict (OpenFGA expects list<string>; normalize to str)
        condition_dict = {
            "name": "has_attribute_access",
            "context": {
                "attribute_name": grant.attribute_name,
                "allowed_values": [str(v) for v in grant.allowed_values],
            },
        }

        # Grant permission in OpenFGA
        await self.openfga.grant_permission(
            user, "viewer", object_id, condition=condition_dict
        )

        logger.info(
            f"Granted viewer permission: user={user}, policy={object_id}, "
            f"attribute={grant.attribute_name}"
        )

        # Ensure policy-to-table link exists
        await self.ensure_policy_table_link(grant.resource, object_id)

        # Build table FQN
        schema_name = grant.resource.schema
        table_fqn = (
            f"{grant.resource.catalog}.{schema_name}.{grant.resource.table}"
        )

        return RowFilterPolicyGrantResponse(
            success=True,
            user_id=grant.user_id,
            policy_id=policy_id,
            object_id=object_id,
            table_fqn=table_fqn,
            attribute_name=grant.attribute_name,
            relation="viewer",
        )

    async def revoke_row_filter_policy(
        self, grant: RowFilterPolicyGrant
    ) -> RowFilterPolicyGrantResponse:
        """
        Revoke row filter policy from user

        Args:
            grant: Row filter policy revoke request (reuses RowFilterPolicyGrant schema)

        Returns:
            Row filter policy revoke response

        Raises:
            ValueError: If resource specification is invalid
        """
        logger.info(
            f"Revoking row filter policy: user={grant.user_id}, "
            f"resource={grant.resource.model_dump(exclude_none=True)}, "
            f"attribute={grant.attribute_name}"
        )

        # Validate resource has table
        if not grant.resource.table:
            raise ValueError(
                "Row filter policy revoke requires table in resource. "
                'Example: {"catalog": "lakekeeper_bronze", "schema": "finance", "table": "user"}'
            )

        # Build policy identifier
        object_id, resource_type, policy_id = (
            self.build_row_filter_policy_identifier(
                grant.resource, grant.attribute_name
            )
        )

        # Build user identifier based on user_type
        user = build_user_identifier_with_type(
            grant.user_id, grant.user_type.value
        )

        # 1. Revoke user's viewer permission on the row_filter_policy
        await self.openfga.revoke_permission(user, "viewer", object_id)
        logger.info(
            f"Revoked viewer permission: user={user}, policy={object_id}"
        )

        # 2. Remove table-to-policy link (applies_to relation)
        schema_name = grant.resource.schema
        if grant.resource.catalog and schema_name and grant.resource.table:
            table_fqn = (
                f"{grant.resource.catalog}.{schema_name}.{grant.resource.table}"
            )
            # Use FGA v3 type: lakekeeper_table instead of table
            table_object_id = f"{FGA_TYPE_LAKEKEEPER_TABLE}:{table_fqn}"

            try:
                # Remove the applies_to link: table --applies_to--> row_filter_policy
                await self.openfga.revoke_permission(
                    user=table_object_id,
                    relation="applies_to",
                    object_id=object_id,
                )
                logger.info(
                    f"Removed table-to-policy link: {table_object_id} --applies_to--> {object_id}"
                )
            except Exception as e:
                logger.warning(
                    f"Error removing table-to-policy link (may not exist): {e}"
                )

        # Build table FQN
        table_fqn = (
            f"{grant.resource.catalog}.{schema_name}.{grant.resource.table}"
        )

        return RowFilterPolicyGrantResponse(
            success=True,
            user_id=grant.user_id,
            policy_id=policy_id,
            object_id=object_id,
            table_fqn=table_fqn,
            attribute_name=grant.attribute_name,
            relation="viewer",
        )

    async def get_user_policies_for_table(
        self, user_id: str, table_fqn: str
    ) -> List[RowFilterPolicyInfo]:
        """
        Get list of row filter policies that user has access to on a specific table

        Args:
            user_id: User identifier
            table_fqn: Fully qualified table name (format: catalog.schema.table)

        Returns:
            List of RowFilterPolicyInfo objects
        """
        logger.info(
            f"Getting row filter policies for user={user_id}, table={table_fqn}"
        )

        try:
            # Get all policies for table
            policy_ids = await self.get_table_policies(table_fqn)
            if not policy_ids:
                logger.debug(f"No policies found for table {table_fqn}")
                return []

            # Get user's filters (this already checks access)
            filters = await self.get_user_policy_filters(user_id, policy_ids)
            if not filters:
                logger.debug(
                    f"User {user_id} has no access to any policies for table {table_fqn}"
                )
                return []

            # Build response with policy details
            policies = [
                RowFilterPolicyInfo(
                    policy_id=f["policy_id"],
                    attribute_name=f["attribute_name"],
                    allowed_values=f["allowed_values"],
                )
                for f in filters
            ]

            logger.info(
                f"Found {len(policies)} policies for user={user_id}, table={table_fqn}"
            )

            return policies

        except Exception as e:
            logger.error(
                f"Error getting policies for user={user_id}, table={table_fqn}: {e}",
                exc_info=True,
            )
            # Return empty list on error (fail gracefully)
            return []

    async def batch_get_row_filters(
        self, request: BatchRowFilterRequest
    ) -> BatchRowFilterResponse:
        """
        Batch get row filter expressions for a user on a table (Trino integration).

        This method processes Trino's batch row filter request format and returns
        the SQL filter expression.

        Args:
            request: Batch row filter request from Trino

        Returns:
            Batch row filter response with filter expression
        """
        logger.info(
            f"Batch getting row filters: user={request.input.context.identity.user}, "
            f"table={request.input.action.resource.table.tableName}"
        )

        try:
            # Extract user_id from context
            user_id = request.input.context.identity.user

            # Validate operation
            if request.input.action.operation != "GetRowFilters":
                logger.warning(
                    f"Unexpected operation: {request.input.action.operation}, "
                    "expected 'GetRowFilters'"
                )

            # Extract table information
            table_resource = request.input.action.resource.table
            table_fqn = f"{table_resource.catalogName}.{table_resource.schemaName}.{table_resource.tableName}"

            logger.debug(
                f"Processing row filter request: user={user_id}, table={table_fqn}"
            )

            # Build row filter SQL using existing method
            filter_sql = await self.build_row_filter_sql(user_id, table_fqn)

            # Build response
            result = []
            if filter_sql:
                logger.info(
                    f"Row filter found for user={user_id}, table={table_fqn}: {filter_sql}"
                )
                result.append(RowFilterExpression(expression=filter_sql))
            else:
                logger.info(
                    f"No row filter found for user={user_id}, table={table_fqn}"
                )
                # Return empty result if no filter (Trino will not apply any filter)

            logger.info(
                f"Batch row filter check completed: user={user_id}, "
                f"table={table_fqn}, has_filter={len(result) > 0}"
            )

            return BatchRowFilterResponse(result=result)

        except Exception as e:
            logger.error(
                f"Error in batch row filter check: {e}",
                exc_info=True,
            )
            # Return empty result on error (fail gracefully - no filter applied)
            return BatchRowFilterResponse(result=[])
