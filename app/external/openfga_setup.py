"""
OpenFGA validation utilities
"""

import asyncio
import logging
from typing import Optional

from openfga_sdk.client import ClientConfiguration, OpenFgaClient

logger = logging.getLogger(__name__)


class OpenFGASetup:
    """Validates that OpenFGA store and authorization model exist"""

    def __init__(self, api_url: str):
        """
        Initialize OpenFGA validator

        Args:
            api_url: OpenFGA API URL
        """
        self.api_url = api_url

    async def validate_store_and_model(
        self, store_id: Optional[str] = None, max_retries: int = 10
    ) -> str:
        """
        Validate that OpenFGA store exists and has authorization models

        Args:
            store_id: Optional specific store ID to validate. If not provided,
                     will use the first available store.
            max_retries: Maximum number of connection retry attempts

        Returns:
            Store ID

        Raises:
            ValueError: If no store exists or no authorization models found
            Exception: If connection to OpenFGA fails
        """
        # Retry logic for connecting to OpenFGA
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"Validating OpenFGA setup (attempt {attempt}/{max_retries})..."
                )

                # Create client without store_id for validation operations
                config = ClientConfiguration(api_url=self.api_url)
                async with OpenFgaClient(config) as client:
                    # Step 1: Validate store exists
                    validated_store_id = await self._validate_store(
                        client, store_id
                    )
                    logger.info(f"Validated store: {validated_store_id}")

                    # Step 2: Validate authorization model exists
                    await self._validate_authorization_model(
                        client, validated_store_id
                    )

                    return validated_store_id

            except Exception as e:
                if attempt < max_retries:
                    wait_time = attempt * 2  # Exponential backoff
                    logger.warning(
                        f"Failed to connect to OpenFGA: {e}. "
                        f"Retrying in {wait_time} seconds..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"Failed to validate OpenFGA setup after {max_retries} attempts"
                    )
                    raise

    async def _validate_store(
        self, client: OpenFgaClient, store_id: Optional[str] = None
    ) -> str:
        """
        Validate that a store exists

        Args:
            client: OpenFGA client
            store_id: Optional specific store ID to validate

        Returns:
            Store ID

        Raises:
            ValueError: If no store exists
        """
        try:
            # Check if stores exist
            response = await client.list_stores()

            if not response.stores or len(response.stores) == 0:
                raise ValueError(
                    "No OpenFGA stores found. Please run bootstrap script to create store and model."
                )

            # If specific store_id provided, validate it exists
            if store_id:
                store_ids = [store.id for store in response.stores]
                if store_id not in store_ids:
                    raise ValueError(
                        f"Store ID '{store_id}' not found. Available stores: {store_ids}"
                    )
                logger.info(f"Validated specific store: {store_id}")
                return store_id

            # Use first available store
            store_id = response.stores[0].id
            logger.info(f"Using first available store: {store_id}")
            return store_id

        except Exception as e:
            logger.error(f"Error validating store: {e}")
            raise

    async def _validate_authorization_model(
        self, client: OpenFgaClient, store_id: str
    ):
        """
        Validate that authorization model exists

        Args:
            client: OpenFGA client
            store_id: Store ID

        Raises:
            ValueError: If no authorization model exists
        """
        try:
            # Reconfigure client with store_id for model operations
            config = ClientConfiguration(
                api_url=self.api_url, store_id=store_id
            )
            async with OpenFgaClient(config) as store_client:
                # Check if authorization models exist
                response = await store_client.read_authorization_models()

                if (
                    not hasattr(response, "authorization_models")
                    or not response.authorization_models
                    or len(response.authorization_models) == 0
                ):
                    raise ValueError(
                        f"No authorization models found in store '{store_id}'. "
                        "Please run bootstrap script to create authorization model."
                    )

                # Get the latest model ID (first in the list)
                latest_model_id = response.authorization_models[0].id
                logger.info(
                    f"Validated {len(response.authorization_models)} authorization model(s) exist"
                )
                logger.info(f"Latest authorization model ID: {latest_model_id}")

        except Exception as e:
            logger.error(f"Error validating authorization model: {e}")
            raise
