"""
Column mask service - Business logic for column masking operations
"""

import logging
from typing import List

from app.external.openfga_client import OpenFGAManager
from app.schemas.column_mask import ColumnMaskGrant, ColumnMaskGrantResponse
from app.utils.operation_mapper import build_user_identifier
from app.utils.resource_builder import build_resource_identifiers

logger = logging.getLogger(__name__)


class ColumnMaskService:
    """Service for handling column mask operations"""

    def __init__(self, openfga: OpenFGAManager):
        """
        Initialize column mask service

        Args:
            openfga: OpenFGA manager instance
        """
        self.openfga = openfga

    async def grant_column_mask(
        self, grant: ColumnMaskGrant
    ) -> ColumnMaskGrantResponse:
        """
        Grant column mask permission to user

        Args:
            grant: Column mask grant request

        Returns:
            Column mask grant response

        Raises:
            ValueError: If resource specification is invalid
        """
        logger.info(
            f"Granting column mask: user={grant.user_id}, "
            f"resource={grant.resource.model_dump(exclude_none=True)}"
        )

        # Validate resource has column
        if not grant.resource.column:
            raise ValueError(
                "Column mask grant requires column in resource. "
                'Example: {"catalog": "lakekeeper", "schema": "finance", "table": "user", "column": "email"}'
            )

        # Build column object_id using resource_builder
        # Use "mask" as the relation to ensure correct column-level identifier
        result = build_resource_identifiers(
            grant.resource, "mask", raise_on_error=True
        )

        if not result:
            raise ValueError(
                "Unable to build column identifier from resource. "
                "Ensure catalog, schema, table, and column are provided."
            )

        object_id, resource_type, resource_id = result

        # Verify it's a column resource
        if resource_type != "column":
            raise ValueError(
                f"Expected column resource, got {resource_type}. "
                "Column mask requires column-level resource."
            )

        # Build user identifier
        user = build_user_identifier(grant.user_id)

        # Grant mask permission in OpenFGA
        await self.openfga.grant_permission(user, "mask", object_id)

        logger.info(
            f"Column mask granted: user={user}, object={object_id}, column={grant.resource.column}"
        )

        return ColumnMaskGrantResponse(
            success=True,
            user_id=grant.user_id,
            column_id=resource_id,
            object_id=object_id,
            relation="mask",
        )

    async def revoke_column_mask(
        self, grant: ColumnMaskGrant
    ) -> ColumnMaskGrantResponse:
        """
        Revoke column mask permission from user

        Args:
            grant: Column mask revoke request (reuses ColumnMaskGrant schema)

        Returns:
            Column mask revoke response

        Raises:
            ValueError: If resource specification is invalid
        """
        logger.info(
            f"Revoking column mask: user={grant.user_id}, "
            f"resource={grant.resource.model_dump(exclude_none=True)}"
        )

        # Validate resource has column
        if not grant.resource.column:
            raise ValueError(
                "Column mask revoke requires column in resource. "
                'Example: {"catalog": "lakekeeper", "schema": "finance", "table": "user", "column": "email"}'
            )

        # Build column object_id using resource_builder
        result = build_resource_identifiers(
            grant.resource, "mask", raise_on_error=True
        )

        if not result:
            raise ValueError(
                "Unable to build column identifier from resource. "
                "Ensure catalog, schema, table, and column are provided."
            )

        object_id, resource_type, resource_id = result

        # Verify it's a column resource
        if resource_type != "column":
            raise ValueError(
                f"Expected column resource, got {resource_type}. "
                "Column mask requires column-level resource."
            )

        # Build user identifier
        user = build_user_identifier(grant.user_id)

        # Revoke mask permission in OpenFGA
        await self.openfga.revoke_permission(user, "mask", object_id)

        logger.info(
            f"Column mask revoked: user={user}, object={object_id}, column={grant.resource.column}"
        )

        return ColumnMaskGrantResponse(
            success=True,
            user_id=grant.user_id,
            column_id=resource_id,
            object_id=object_id,
            relation="mask",
        )

    async def get_masked_columns_for_user(
        self, user_id: str, table_fqn: str
    ) -> List[str]:
        """
        Get list of column names that are masked for a user on a specific table

        Args:
            user_id: User identifier
            table_fqn: Fully qualified table name (format: catalog.schema.table)

        Returns:
            List of column names that are masked
        """
        logger.info(
            f"Getting masked columns for user={user_id}, table={table_fqn}"
        )

        try:
            # Build user identifier
            user = build_user_identifier(user_id)

            # Query all mask tuples for this user
            # object_id=None means get all tuples matching user and relation
            tuples = await self.openfga.read_tuples(
                user=user, relation="mask", object_id=None
            )

            # Build table prefix to filter columns
            # Format: column:catalog.schema.table.
            table_prefix = f"column:{table_fqn}."

            masked_columns = []
            for tuple_item in tuples:
                # OpenFGA SDK: object is in tuple_item.key.object
                tuple_key = getattr(tuple_item, "key", None)
                if not tuple_key:
                    continue

                object_id = getattr(tuple_key, "object", "")
                if not object_id:
                    continue

                # Filter: only columns from this table
                if object_id.startswith(table_prefix):
                    # Extract column name from object_id
                    # Format: column:catalog.schema.table.column
                    # We want just the column name (last part after last dot)
                    column_name = object_id.split(".")[-1]
                    if column_name:
                        masked_columns.append(column_name)
                        logger.debug(
                            f"Found masked column: {column_name} for user={user_id}, table={table_fqn}"
                        )

            logger.info(
                f"Found {len(masked_columns)} masked columns for user={user_id}, table={table_fqn}: {masked_columns}"
            )

            return masked_columns

        except Exception as e:
            logger.error(
                f"Error getting masked columns for user={user_id}, table={table_fqn}: {e}",
                exc_info=True,
            )
            # Return empty list on error (fail gracefully)
            return []
