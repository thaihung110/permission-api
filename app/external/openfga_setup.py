"""
OpenFGA initialization and setup utilities
"""

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

import httpx
from openfga_sdk.client import ClientConfiguration, OpenFgaClient

logger = logging.getLogger(__name__)


class OpenFGASetup:
    """Handles OpenFGA store and authorization model setup"""

    def __init__(self, api_url: str):
        """
        Initialize OpenFGA setup

        Args:
            api_url: OpenFGA API URL
        """
        self.api_url = api_url

    async def ensure_store_and_model(
        self, auth_model_path: Optional[str] = None, max_retries: int = 5
    ) -> str:
        """
        Ensure OpenFGA store exists and authorization model is created

        Args:
            auth_model_path: Path to .fga authorization model file
            max_retries: Maximum number of connection retry attempts

        Returns:
            Store ID
        """
        # Retry logic for connecting to OpenFGA
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"Attempting to connect to OpenFGA (attempt {attempt}/{max_retries})..."
                )

                # Create client without store_id for setup operations
                config = ClientConfiguration(api_url=self.api_url)
                async with OpenFgaClient(config) as client:
                    # Step 1: Ensure store exists
                    store_id = await self._ensure_store(client)
                    logger.info(f"Using store: {store_id}")

                    # Step 2: Ensure authorization model exists
                    if auth_model_path:
                        await self._ensure_authorization_model(
                            client, store_id, auth_model_path
                        )

                    return store_id

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
                        f"Failed to connect to OpenFGA after {max_retries} attempts"
                    )
                    raise

    async def _ensure_store(self, client: OpenFgaClient) -> str:
        """
        Ensure store exists, create if not

        Args:
            client: OpenFGA client

        Returns:
            Store ID
        """
        try:
            # Check if stores exist
            response = await client.list_stores()

            if response.stores and len(response.stores) > 0:
                store_id = response.stores[0].id
                logger.info(f"Found existing store: {store_id}")
                return store_id

            # No stores found, create new one
            logger.info("No stores found, creating new store...")
            response = await client.create_store(
                body={"name": "Permission Management Store"}
            )
            store_id = response.id
            logger.info(f"Created new store: {store_id}")
            return store_id

        except Exception as e:
            logger.error(f"Error ensuring store exists: {e}")
            raise

    async def _ensure_authorization_model(
        self, client: OpenFgaClient, store_id: str, auth_model_path: str
    ):
        """
        Ensure authorization model exists, create if not

        Args:
            client: OpenFGA client
            store_id: Store ID
            auth_model_path: Path to .fga authorization model file
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
                    hasattr(response, "authorization_models")
                    and response.authorization_models
                    and len(response.authorization_models) > 0
                ):
                    logger.info(
                        f"Found {len(response.authorization_models)} existing authorization model(s)"
                    )
                    # Model already exists, no need to create
                    return

                # No model found, create from file
                logger.info(
                    f"No authorization model found, creating from {auth_model_path}..."
                )

                # Load JSON model
                model_json = self._load_json_model(auth_model_path)

                # Write using SDK
                response = await store_client.write_authorization_model(
                    model_json
                )

                model_id = response.authorization_model_id
                logger.info(f"Created authorization model: {model_id}")

        except Exception as e:
            logger.error(f"Error ensuring authorization model: {e}")
            raise

    def _load_json_model(self, model_path: str) -> dict:
        """
        Load authorization model from JSON file

        Args:
            model_path: Path to model file (.fga or .json)

        Returns:
            Model as dict
        """
        try:
            # Try .json file first, fallback to .fga path with .json extension
            json_path = Path(model_path)
            if json_path.suffix == ".fga":
                # Replace .fga with .json
                json_path = json_path.with_suffix(".json")

            if not json_path.exists():
                raise FileNotFoundError(
                    f"JSON model file not found: {json_path}. "
                    f"Please convert your .fga file to JSON format."
                )

            # Read and parse JSON
            with open(json_path, "r") as f:
                model_data = json.load(f)

            logger.info(f"Loaded authorization model from {json_path}")

            return model_data

        except Exception as e:
            logger.error(f"Error loading JSON model: {e}")
            raise
