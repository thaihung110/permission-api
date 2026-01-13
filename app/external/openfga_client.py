"""
OpenFGA client management and operations
"""

import logging
from typing import Any, Dict, List, Optional

from openfga_sdk.client import ClientConfiguration, OpenFgaClient
from openfga_sdk.client.models import ClientCheckRequest, ClientWriteRequest
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
        Check if user has permission

        Args:
            user: User identifier (e.g., "user:alice")
            relation: Relation to check (e.g., "can_select")
            object_id: Object identifier (e.g., "table:warehouse_id/table_id")

        Returns:
            True if allowed, False otherwise
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
            else:
                logger.info(
                    f"Writing tuple to OpenFGA: user={user}, relation={relation}, object={object_id}"
                )

            tuple_item = ClientTuple(**tuple_kwargs)

            # Create write request
            body = ClientWriteRequest(writes=[tuple_item])

            response = await self.client.write(body)
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
            # Some OpenFGA/SDK combinations may raise even though the tuple was
            # actually written. Treat this as a soft error and verify first.
            logger.warning(
                "Initial error while granting permission in OpenFGA: %s. "
                "Verifying if tuple was still written...",
                e,
            )

            try:
                check_result = await self.check_permission(
                    user, relation, object_id
                )
            except Exception as verify_err:
                # Verification itself failed – log the original error as real
                logger.error(
                    "Error verifying tuple after OpenFGA write failure. "
                    "original_error=%s verify_error=%s",
                    e,
                    verify_err,
                )
                raise

            if check_result:
                # Tuple exists – suppress the exception and treat as success.
                logger.info(
                    "Tuple was written successfully despite OpenFGA/SDK "
                    "error. Suppressing error."
                )
                return

            # Tuple does not exist – propagate as a real error.
            logger.error("Error granting permission in OpenFGA: %s", e)
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
            object_id: Object identifier to filter by (optional, e.g., "row_filter_policy:customers_region_filter")

        Returns:
            List of tuples with condition context (deserialized from bytea by SDK)

        Note:
            Condition context is stored as bytea in OpenFGA but automatically
            deserialized by the SDK when reading tuples.
        """
        if not self.client:
            raise RuntimeError("OpenFGA client not initialized")

        try:
            # Use read() method - OpenFGA SDK read() accepts tuple_key as keyword arguments
            # Build tuple_key dict with only non-None values
            tuple_key = {}
            if user is not None:
                tuple_key["user"] = user
            if relation is not None:
                tuple_key["relation"] = relation
            if object_id is not None:
                tuple_key["object"] = object_id

            # Call read() with tuple_key parameter
            response = await self.client.read(
                tuple_key=tuple_key if tuple_key else None
            )

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
