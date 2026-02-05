"""
OpenFGA client management and operations
"""

import logging
from typing import Any, Dict, List, Optional

from openfga_sdk import ReadRequestTupleKey
from openfga_sdk.client import ClientConfiguration, OpenFgaClient
from openfga_sdk.client.models import (
    ClientCheckRequest,
    ClientListObjectsRequest,
    ClientWriteRequest,
)
from openfga_sdk.client.models.tuple import ClientTuple

logger = logging.getLogger(__name__)


class OpenFGAManager:
    """Manages OpenFGA client and operations"""

    def __init__(self, api_url: str, store_id: str):
        """
        Initialize OpenFGA manager

        Args:
            api_url: OpenFGA API URL
            store_id: OpenFGA store ID (must be created via OpenFGASetup first)

        Raises:
            ValueError: If store_id is not provided
        """
        if not store_id:
            raise ValueError(
                "store_id is required. Use OpenFGASetup.ensure_store_and_model() "
                "to create store before initializing OpenFGAManager."
            )

        self.api_url = api_url
        self.store_id = store_id
        self.client: Optional[OpenFgaClient] = None

    async def initialize(self):
        """Initialize OpenFGA client with pre-configured store"""
        try:
            # Create client with store_id configured
            config = ClientConfiguration(
                api_url=self.api_url, store_id=self.store_id
            )
            self.client = OpenFgaClient(config)

            logger.info(
                f"OpenFGA client initialized with store: {self.store_id}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize OpenFGA client: {e}")
            raise

    async def close(self):
        """Close OpenFGA client"""
        if self.client:
            try:
                await self.client.close()
                logger.info("OpenFGA client closed")
            except Exception as e:
                logger.error(f"Error closing OpenFGA client: {e}")

    async def health_check(self) -> bool:
        """Check if OpenFGA is healthy"""
        if not self.client:
            return False

        try:
            await self.client.list_stores()
            return True
        except Exception as e:
            logger.error(f"OpenFGA health check failed: {e}")
            return False

    # ========================================================================
    # Permission Operations
    # ========================================================================

    async def check_permission(
        self, user: str, relation: str, object_id: str
    ) -> bool:
        """
        Check if user has permission (includes inheritance from parent resources)

        Args:
            user: User identifier (e.g., "user:alice")
            relation: Relation to check (e.g., "can_select")
            object_id: Object identifier (e.g., "table:warehouse_id/table_id")

        Returns:
            True if allowed (including via inheritance), False otherwise
        """
        if not self.client:
            raise RuntimeError("OpenFGA client not initialized")

        try:
            body = ClientCheckRequest(
                user=user, relation=relation, object=object_id
            )

            response = await self.client.check(body)

            allowed = (
                response.allowed if hasattr(response, "allowed") else False
            )

            logger.debug(
                f"OpenFGA check: user={user}, relation={relation}, "
                f"object={object_id}, allowed={allowed}"
            )

            return allowed

        except Exception as e:
            logger.error(f"Error checking permission in OpenFGA: {e}")
            return False

    async def grant_permission(
        self,
        user: str,
        relation: str,
        object_id: str,
        condition: Optional[Dict[str, Any]] = None,
    ):
        """
        Grant permission by writing tuple to OpenFGA

        If tuple already exists, it will be overwritten (delete + write in single request)

        Args:
            user: User identifier
            relation: Relation/permission
            object_id: Object identifier
            condition: Optional condition dict with 'name' and 'context' keys
                Example: {
                    "name": "has_attribute_access",
                    "context": {
                        "attribute_name": "region",
                        "allowed_values": ["mien_bac"]
                    }
                }
        """
        if not self.client:
            raise RuntimeError("OpenFGA client not initialized")

        try:
            # Check if tuple already exists (to overwrite it)
            existing_tuples = await self.read_tuples(
                user=user, relation=relation, object_id=object_id
            )

            # If tuple exists, delete it first (separate request to avoid duplicate error)
            if existing_tuples:
                logger.info(
                    f"Tuple already exists, deleting before overwrite: user={user}, relation={relation}, object={object_id}"
                )

                # Delete existing tuple in separate request
                delete_tuple = ClientTuple(
                    user=user, relation=relation, object=object_id
                )

                delete_body = ClientWriteRequest(deletes=[delete_tuple])
                await self.client.write(delete_body)
                logger.debug(f"Deleted existing tuple successfully")

            # Now write the new tuple (with or without condition)
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
            else:
                logger.info(
                    f"Writing tuple to OpenFGA: user={user}, relation={relation}, object={object_id}"
                )

            new_tuple = ClientTuple(**tuple_kwargs)
            write_body = ClientWriteRequest(writes=[new_tuple])

            # Execute write
            response = await self.client.write(write_body)
            logger.debug(f"OpenFGA write response: {response}")

            if condition:
                logger.info(
                    f"Granted permission with condition: user={user}, relation={relation}, "
                    f"object={object_id}, condition={condition.get('name')}"
                )
            else:
                logger.info(
                    f"Granted permission: user={user}, relation={relation}, object={object_id}"
                )

        except Exception as e:
            logger.error(f"Error granting permission in OpenFGA: {e}")
            raise

    async def revoke_permission(self, user: str, relation: str, object_id: str):
        """
        Revoke permission by deleting tuple from OpenFGA

        Args:
            user: User identifier
            relation: Relation/permission
            object_id: Object identifier
        """
        if not self.client:
            raise RuntimeError("OpenFGA client not initialized")

        try:
            # Create tuple using SDK model
            tuple_item = ClientTuple(
                user=user, relation=relation, object=object_id
            )

            # Create write request with deletes
            body = ClientWriteRequest(deletes=[tuple_item])

            await self.client.write(body)

            logger.info(
                f"Revoked permission: user={user}, relation={relation}, object={object_id}"
            )

        except Exception as e:
            logger.error(f"Error revoking permission in OpenFGA: {e}")
            raise

    # ========================================================================
    # Tuple Reading Operations
    # ========================================================================

    async def read_tuples(
        self,
        user: Optional[str] = None,
        relation: Optional[str] = None,
        object_id: Optional[str] = None,
    ) -> list:
        """
        Read tuples from OpenFGA matching the given filters

        Args:
            user: User identifier (optional, e.g., "user:alice")
            relation: Relation to filter by (optional, e.g., "viewer")
            object_id: Object identifier to filter by (optional, e.g., "row_filter_policy:lakekeeper_bronze.finance.user.region")

        Returns:
            List of tuples with condition context (deserialized from bytea by SDK)

        Note:
            Condition context is stored as bytea in OpenFGA but automatically
            deserialized by the SDK when reading tuples.
        """
        if not self.client:
            raise RuntimeError("OpenFGA client not initialized")

        try:
            # Use ReadRequestTupleKey object - OpenFGA SDK read() accepts ReadRequestTupleKey
            # When querying by user and relation only, we need to provide object type
            # For pattern matching, we can use object type without id (e.g., "row_filter_policy:")
            read_request_kwargs = {}
            if user is not None:
                read_request_kwargs["user"] = user
            if relation is not None:
                read_request_kwargs["relation"] = relation
            if object_id is not None:
                read_request_kwargs["object"] = object_id
            # If only user and relation provided (no object_id), use object type pattern
            # OpenFGA requires object type field when querying by user and relation
            elif user is not None and relation is not None:
                # For applies_to relation, we expect row_filter_policy objects
                if relation == "applies_to":
                    # Pattern: "row_filter_policy:" matches all row_filter_policy objects
                    read_request_kwargs["object"] = "row_filter_policy:"
                # For viewer relation with user, we're querying user's permissions on policies
                elif relation == "viewer" and user.startswith("user:"):
                    # Pattern: "row_filter_policy:" matches all row_filter_policy objects
                    read_request_kwargs["object"] = "row_filter_policy:"
                # For mask relation with user, we're querying user's column mask permissions
                elif relation == "mask" and user.startswith("user:"):
                    # Pattern: "column:" matches all column objects
                    read_request_kwargs["object"] = "column:"
                else:
                    # For other relations, try to infer object type or use wildcard
                    # Default to empty string - OpenFGA will handle pattern matching
                    read_request_kwargs["object"] = ""

            # Create ReadRequestTupleKey object
            read_request = ReadRequestTupleKey(**read_request_kwargs)

            # Call read() with ReadRequestTupleKey object
            response = await self.client.read(read_request)

            tuples = []
            if hasattr(response, "tuples") and response.tuples:
                for tuple_item in response.tuples:
                    tuples.append(tuple_item)

            logger.debug(
                f"OpenFGA read: user={user}, relation={relation}, "
                f"object={object_id}, found {len(tuples)} tuples"
            )

            return tuples

        except Exception as e:
            logger.error(f"Error reading tuples from OpenFGA: {e}")
            raise

    async def list_objects(
        self,
        user: str,
        relation: str,
        object_type: str,
    ) -> List[str]:
        """
        List all objects of a given type that the user has the relation with

        This is more efficient than read_tuples when you only need object IDs.

        Args:
            user: User identifier (e.g., "table:lakekeeper_bronze.finance.user")
            relation: Relation to filter by (e.g., "applies_to")
            object_type: Object type (e.g., "row_filter_policy")

        Returns:
            List of object IDs (e.g., ["row_filter_policy:lakekeeper_bronze.finance.user.region"])

        Example:
            objects = await openfga.list_objects(
                user="table:lakekeeper_bronze.finance.user",
                relation="applies_to",
                object_type="row_filter_policy"
            )
            # Returns: ["row_filter_policy:lakekeeper_bronze.finance.user.region"]
        """
        if not self.client:
            raise RuntimeError("OpenFGA client not initialized")

        try:
            # Create ClientListObjectsRequest
            body = ClientListObjectsRequest(
                user=user,
                relation=relation,
                type=object_type,
            )

            # Call list_objects
            response = await self.client.list_objects(body)

            # Extract object IDs from response
            objects = []
            if hasattr(response, "objects") and response.objects:
                objects = list(response.objects)

            logger.debug(
                f"OpenFGA list_objects: user={user}, relation={relation}, "
                f"type={object_type}, found {len(objects)} objects"
            )

            return objects

        except Exception as e:
            logger.error(f"Error listing objects from OpenFGA: {e}")
            raise

    # ========================================================================
    # Tenant Operations
    # ========================================================================

    async def check_tenant_membership(
        self, user_id: str, tenant_id: str
    ) -> bool:
        """
        Check if a user is a member of a tenant

        Args:
            user_id: User identifier (without "user:" prefix)
            tenant_id: Tenant identifier (without "tenant:" prefix)

        Returns:
            True if user is a member of the tenant, False otherwise

        Example:
            is_member = await openfga.check_tenant_membership("alice", "acme_corp")
        """
        try:
            # Query: user -> member -> tenant
            is_member = await self.check_permission(
                user=f"user:{user_id}",
                relation="member",
                object_id=f"tenant:{tenant_id}",
            )
            logger.debug(
                f"User {user_id} membership in tenant {tenant_id}: {is_member}"
            )
            return is_member

        except Exception as e:
            logger.warning(
                f"Error checking tenant membership for user {user_id} "
                f"and tenant {tenant_id}: {e}"
            )
            return False
