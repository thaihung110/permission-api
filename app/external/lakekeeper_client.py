"""
Lakekeeper HTTP client with Keycloak authentication
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class LakekeeperClient:
    """Client for Lakekeeper API with Keycloak authentication"""

    def __init__(
        self,
        management_url: str,
        catalog_url: str,
        keycloak_token_url: str,
        client_id: str,
        client_secret: str,
        scope: str = "lakekeeper",
    ):
        """
        Initialize Lakekeeper client

        Args:
            management_url: Lakekeeper Management API URL
            catalog_url: Lakekeeper Catalog API URL
            keycloak_token_url: Keycloak token endpoint URL
            client_id: Keycloak client ID
            client_secret: Keycloak client secret
            scope: OAuth2 scope for Lakekeeper
        """
        self.management_url = management_url
        self.catalog_url = catalog_url
        self.keycloak_token_url = keycloak_token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope

        self.client: Optional[httpx.AsyncClient] = None
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None

    async def initialize(self):
        """Initialize HTTP client"""
        self.client = httpx.AsyncClient(timeout=30.0)
        logger.info("Lakekeeper client initialized")

    async def close(self):
        """Close HTTP client"""
        if self.client:
            await self.client.aclose()
            logger.info("Lakekeeper client closed")

    async def _authenticate(self) -> str:
        """
        Authenticate with Keycloak and get access token.
        Caches token and only refreshes when expired.

        Returns:
            Access token string

        Raises:
            Exception: If authentication fails
        """
        # Check if we have a valid cached token
        if self.access_token and self.token_expires_at:
            if datetime.now() < self.token_expires_at:
                logger.debug("Using cached Keycloak token")
                return self.access_token

        # Get new token from Keycloak
        logger.info(
            f"Authenticating with Keycloak: POST {self.keycloak_token_url} "
            f"(client_id={self.client_id}, scope={self.scope})"
        )

        try:
            response = await self.client.post(
                self.keycloak_token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": self.scope,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()

            token_data = response.json()
            self.access_token = token_data["access_token"]

            # Set expiration time (subtract 60s buffer for safety)
            expires_in = token_data.get("expires_in", 300)
            self.token_expires_at = datetime.now() + timedelta(
                seconds=expires_in - 60
            )

            logger.info(
                f"Successfully authenticated with Keycloak "
                f"(expires in {expires_in}s, token_type={token_data.get('token_type')})"
            )
            logger.debug(f"Access token: {self.access_token[:20]}...")
            return self.access_token

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Keycloak authentication failed (HTTP {e.response.status_code}): "
                f"{e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Failed to authenticate with Keycloak: {e}", exc_info=True
            )
            raise

    async def _get_headers(self) -> Dict[str, str]:
        """
        Get headers with authentication token

        Returns:
            Headers dict with Authorization bearer token
        """
        token = await self._authenticate()
        return {"Authorization": f"Bearer {token}"}

    async def get_warehouse_config(self, warehouse_name: str) -> Optional[str]:
        """
        GET /v1/config?warehouse=<warehouse_name> - Returns warehouse configuration

        Args:
            warehouse_name: Warehouse name (catalog name)

        Returns:
            Warehouse ID (prefix from defaults) or None on error
        """
        url = f"{self.catalog_url}/v1/config"
        params = {"warehouse": warehouse_name}
        logger.info(
            f"Fetching warehouse config: GET {url}?warehouse={warehouse_name}"
        )

        try:
            headers = await self._get_headers()
            response = await self.client.get(
                url, headers=headers, params=params
            )
            response.raise_for_status()

            data = response.json()
            defaults = data.get("defaults", {})
            warehouse_id = defaults.get("prefix")

            if not warehouse_id:
                logger.warning(
                    f"✗ No prefix found in warehouse config response for {warehouse_name}: {data}"
                )
                return None

            logger.info(
                f"✓ Fetched warehouse config for {warehouse_name}: warehouse_id={warehouse_id}"
            )
            logger.debug(f"  Full config response: {data}")
            return warehouse_id

        except httpx.HTTPStatusError as e:
            logger.error(
                f"✗ Failed to fetch warehouse config for {warehouse_name} "
                f"(HTTP {e.response.status_code}): {e.response.text}"
            )
            return None
        except Exception as e:
            logger.error(
                f"✗ Failed to fetch warehouse config for {warehouse_name}: {e}",
                exc_info=True,
            )
            return None

    async def get_warehouses(self) -> List[Dict[str, Any]]:
        """
        GET /v1/warehouse - Returns list of warehouses

        Returns:
            List of warehouse objects with 'id', 'name', 'project-id' fields.
            Returns empty list on error.
        """
        url = f"{self.management_url}/v1/warehouse"
        logger.info(f"Fetching warehouses: GET {url}")

        try:
            headers = await self._get_headers()
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            warehouses = data.get("warehouses", [])

            logger.info(
                f"✓ Fetched {len(warehouses)} warehouses from Lakekeeper"
            )
            for wh in warehouses:
                logger.debug(
                    f"  - Warehouse: id={wh.get('id')}, name={wh.get('name')}, "
                    f"project-id={wh.get('project-id')}"
                )
            return warehouses

        except httpx.HTTPStatusError as e:
            logger.warning(
                f"✗ Failed to fetch warehouses (HTTP {e.response.status_code}): "
                f"{e.response.text}"
            )
            return []
        except Exception as e:
            logger.warning(f"✗ Failed to fetch warehouses: {e}", exc_info=True)
            return []

    async def get_namespaces(self, warehouse_id: str) -> List[List[str]]:
        """
        GET /v1/{warehouse_id}/namespaces - Returns namespaces for warehouse

        Args:
            warehouse_id: Warehouse UUID (used as prefix in URL)

        Returns:
            List of namespace names (each namespace is a list of string parts).
            Returns empty list on error.
        """
        url = f"{self.catalog_url}/v1/{warehouse_id}/namespaces"
        logger.info(f"Fetching namespaces: GET {url}")

        try:
            headers = await self._get_headers()
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            namespaces = data.get("namespaces", [])

            logger.info(
                f"✓ Fetched {len(namespaces)} namespaces for warehouse {warehouse_id}"
            )
            for ns in namespaces:
                logger.debug(
                    f"  - Namespace: {'.'.join(ns) if isinstance(ns, list) else ns}"
                )
            return namespaces

        except httpx.HTTPStatusError as e:
            logger.warning(
                f"✗ Failed to fetch namespaces for warehouse {warehouse_id} "
                f"(HTTP {e.response.status_code}): {e.response.text}"
            )
            return []
        except Exception as e:
            logger.warning(
                f"✗ Failed to fetch namespaces for warehouse {warehouse_id}: {e}",
                exc_info=True,
            )
            return []

    async def get_tables(
        self, warehouse_id: str, namespace_name: str
    ) -> List[Dict[str, Any]]:
        """
        GET /v1/{warehouse_id}/namespaces/{namespace_name}/tables

        Args:
            warehouse_id: Warehouse UUID (used as prefix in URL)
            namespace_name: Namespace name

        Returns:
            List of table identifiers with 'namespace' and 'name' fields.
            Returns empty list on error.
        """
        url = f"{self.catalog_url}/v1/{warehouse_id}/namespaces/{namespace_name}/tables"
        logger.info(f"Fetching tables: GET {url}")

        try:
            headers = await self._get_headers()
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            identifiers = data.get("identifiers", [])

            logger.info(
                f"✓ Fetched {len(identifiers)} tables for "
                f"warehouse {warehouse_id}, namespace {namespace_name}"
            )
            for table in identifiers:
                logger.debug(f"  - Table: {table.get('name')}")
            return identifiers

        except httpx.HTTPStatusError as e:
            logger.warning(
                f"✗ Failed to fetch tables for warehouse {warehouse_id}, "
                f"namespace {namespace_name} (HTTP {e.response.status_code}): "
                f"{e.response.text}"
            )
            return []
        except Exception as e:
            logger.warning(
                f"✗ Failed to fetch tables for warehouse {warehouse_id}, "
                f"namespace {namespace_name}: {e}",
                exc_info=True,
            )
            return []

    async def get_table_metadata(
        self, warehouse_id: str, namespace_name: str, table_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        GET /v1/{warehouse_id}/namespaces/{namespace_name}/tables/{table_name}

        Fetch table metadata including schema information (columns).

        Args:
            warehouse_id: Warehouse UUID
            namespace_name: Namespace name
            table_name: Table name

        Returns:
            Table metadata dict with 'metadata' containing 'schemas', or None on error
        """
        url = f"{self.catalog_url}/v1/{warehouse_id}/namespaces/{namespace_name}/tables/{table_name}"
        logger.debug(f"Fetching table metadata: GET {url}")

        try:
            headers = await self._get_headers()
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            logger.debug(
                f"✓ Fetched table metadata for {namespace_name}.{table_name}"
            )
            return data

        except httpx.HTTPStatusError as e:
            logger.warning(
                f"✗ Failed to fetch table metadata for {namespace_name}.{table_name} "
                f"(HTTP {e.response.status_code}): {e.response.text}"
            )
            return None
        except Exception as e:
            logger.warning(
                f"✗ Failed to fetch table metadata for {namespace_name}.{table_name}: {e}"
            )
            return None
