"""
Row filter service - Build SQL filters from OpenFGA row filter policies
"""

import logging
from typing import List, Optional

from app.external.openfga_client import OpenFGAManager

logger = logging.getLogger(__name__)


def parse_column_from_policy_id(policy_id: str) -> Optional[str]:
    """
    Extract column name from policy ID using naming convention

    Format: {table_name}_{column_name}_filter
    Examples:
        "customers_region_filter" → "region"
        "employees_department_filter" → "department"

    Args:
        policy_id: Policy ID (e.g., "customers_region_filter")

    Returns:
        Column name or None if cannot parse
    """
    # Remove "_filter" suffix and get last part
    parts = policy_id.replace("_filter", "").split("_")
    if len(parts) >= 2:
        return parts[-1]  # Last part is column name
    return None


def escape_sql_value(value: str) -> str:
    """
    Escape SQL value to prevent injection

    Args:
        value: Raw value

    Returns:
        Escaped value
    """
    # Remove dangerous characters
    sanitized = value.replace("'", "''").replace(";", "").replace("--", "")
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
            List of policy IDs (e.g., ["customers_region_filter"])
        """
        try:
            tuples = await self.openfga.read_tuples(
                user=f"table:{table_fqn}", relation="applies_to"
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

        Args:
            user_id: User identifier
            policy_ids: List of policy IDs

        Returns:
            List of filter dicts with keys: policy_id, attribute_name, column_name, allowed_values
        """
        filters = []

        for policy_id in policy_ids:
            try:
                # Query: user -> viewer -> policy
                tuples = await self.openfga.read_tuples(
                    user=f"user:{user_id}",
                    relation="viewer",
                    object_id=f"row_filter_policy:{policy_id}",
                )

                if not tuples:
                    logger.debug(
                        f"User {user_id} has no access to policy {policy_id}"
                    )
                    continue

                for tuple_item in tuples:
                    # OpenFGA SDK: condition is in tuple_item.key.condition
                    tuple_key = getattr(tuple_item, "key", None)
                    if not tuple_key:
                        logger.warning(
                            f"Tuple for user {user_id} and policy {policy_id} has no key"
                        )
                        continue

                    condition = getattr(tuple_key, "condition", None)
                    if not condition:
                        logger.warning(
                            f"Tuple for user {user_id} and policy {policy_id} has no condition"
                        )
                        continue

                    ctx = getattr(condition, "context", None)
                    if not ctx:
                        logger.warning(
                            f"Tuple condition for user {user_id} and policy {policy_id} has no context"
                        )
                        continue

                    # Extract attribute_name and allowed_values from context
                    # Context should be a dict with attribute_name and allowed_values
                    if isinstance(ctx, dict):
                        attribute_name = ctx.get("attribute_name")
                        allowed_values = ctx.get("allowed_values", [])
                    else:
                        # Try to access as object attributes
                        attribute_name = getattr(ctx, "attribute_name", None)
                        allowed_values = getattr(ctx, "allowed_values", [])
                        # If still None, try to convert to dict
                        if attribute_name is None:
                            try:
                                ctx_dict = (
                                    dict(ctx)
                                    if hasattr(ctx, "__iter__")
                                    else {}
                                )
                                attribute_name = ctx_dict.get("attribute_name")
                                allowed_values = ctx_dict.get(
                                    "allowed_values", []
                                )
                            except Exception:
                                pass

                    if not attribute_name or not allowed_values:
                        logger.warning(
                            f"Invalid condition context for user {user_id} and policy {policy_id}: "
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

                    filters.append(
                        {
                            "policy_id": policy_id,
                            "attribute_name": attribute_name,
                            "column_name": column_name,
                            "allowed_values": allowed_values,
                        }
                    )

            except Exception as e:
                logger.error(
                    f"Error getting filters for user {user_id} and policy {policy_id}: {e}",
                    exc_info=True,
                )
                continue

        return filters

    async def build_row_filter_sql(
        self, user_id: str, table_fqn: str
    ) -> Optional[str]:
        """
        Build SQL WHERE clause for row filtering

        Args:
            user_id: User identifier
            table_fqn: Fully qualified table name (e.g., "prod.public.customers")

        Returns:
            SQL WHERE clause (e.g., "region IN ('north')") or None if no filter
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
                logger.warning(
                    f"User {user_id} has no access to any policies for table {table_fqn}"
                )
                return "1=0"  # Deny all

            # Check if user has access to all required policies
            if len(filters) < len(policy_ids):
                logger.warning(
                    f"User {user_id} missing access to some policies for table {table_fqn}. "
                    f"Required: {len(policy_ids)}, Found: {len(filters)}"
                )
                return "1=0"  # Deny all if missing any required policy

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
