"""
Lakekeeper HTTP client with Keycloak authentication
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
import jwt

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
            f"\n{'='*60}\n"
            f"[KEYCLOAK AUTH] Authenticating with Keycloak\n"
            f"{'='*60}\n"
            f"URL: POST {self.keycloak_token_url}\n"
            f"Client ID: {self.client_id}\n"
            f"Scope: {self.scope}\n"
            f"{'='*60}"
        )

        # Prepare request data
        auth_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": self.scope,
        }

        # Log request data (without secret)
        safe_data = auth_data.copy()
        safe_data["client_secret"] = "***REDACTED***"
        logger.info(
            f"[KEYCLOAK AUTH] Request data:\n{json.dumps(safe_data, indent=2, ensure_ascii=False)}"
        )

        try:
            response = await self.client.post(
                self.keycloak_token_url,
                data=auth_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()

            token_data = response.json()
            self.access_token = token_data["access_token"]

            # Log full response (including full token)
            logger.info(
                f"\n{'='*60}\n"
                f"[KEYCLOAK AUTH] Response received\n"
                f"{'='*60}\n"
                f"{json.dumps(token_data, indent=2, ensure_ascii=False)}\n"
                f"{'='*60}"
            )

            # Print full access token to console
            print(f"\n{'='*60}")
            print("[KEYCLOAK AUTH] FULL ACCESS TOKEN:")
            print(f"{'='*60}")
            print(self.access_token)
            print(f"{'='*60}\n")

            # Decode and log JWT token
            try:
                decoded_token = jwt.decode(
                    self.access_token, options={"verify_signature": False}
                )

                # Print decoded token to console
                print(f"{'='*60}")
                print("[KEYCLOAK AUTH] DECODED JWT TOKEN:")
                print(f"{'='*60}")
                print(json.dumps(decoded_token, indent=4, ensure_ascii=False))
                print(f"{'='*60}\n")

                logger.info(
                    f"\n{'='*60}\n"
                    f"[KEYCLOAK AUTH] Decoded JWT Token\n"
                    f"{'='*60}\n"
                    f"{json.dumps(decoded_token, indent=4, ensure_ascii=False)}\n"
                    f"{'='*60}"
                )
            except Exception as decode_error:
                logger.warning(f"Failed to decode JWT token: {decode_error}")

            # Set expiration time (subtract 60s buffer for safety)
            expires_in = token_data.get("expires_in", 300)
            self.token_expires_at = datetime.now() + timedelta(
                seconds=expires_in - 60
            )

            logger.info(
                f"\n{'='*60}\n"
                f"[KEYCLOAK AUTH] Authentication successful\n"
                f"{'='*60}\n"
                f"Expires in: {expires_in}s\n"
                f"Token type: {token_data.get('token_type')}\n"
                f"Token expires at: {self.token_expires_at}\n"
                f"Full access token length: {len(self.access_token)} characters\n"
                f"{'='*60}"
            )

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
            f"\n{'='*60}\n"
            f"[WAREHOUSE CONFIG] Fetching warehouse config\n"
            f"{'='*60}\n"
            f"URL: GET {url}\n"
            f"Params: {json.dumps(params, indent=2, ensure_ascii=False)}\n"
            f"Warehouse name: {warehouse_name}\n"
            f"{'='*60}"
        )

        try:
            headers = await self._get_headers()

            # Log full headers (including full token)
            logger.info(
                f"[WAREHOUSE CONFIG] Request headers:\n{json.dumps(headers, indent=2, ensure_ascii=False)}"
            )

            # Print full headers to console
            print(f"\n{'='*60}")
            print("[WAREHOUSE CONFIG] FULL REQUEST HEADERS:")
            print(f"{'='*60}")
            print(json.dumps(headers, indent=2, ensure_ascii=False))
            print(f"{'='*60}\n")

            response = await self.client.get(
                url, headers=headers, params=params
            )
            response.raise_for_status()

            data = response.json()

            # Log response
            logger.info(
                f"\n{'='*60}\n"
                f"[WAREHOUSE CONFIG] Response received\n"
                f"{'='*60}\n"
                f"Status code: {response.status_code}\n"
                f"Response data:\n{json.dumps(data, indent=2, ensure_ascii=False)}\n"
                f"{'='*60}"
            )

            defaults = data.get("defaults", {})
            warehouse_id = defaults.get("prefix")

            if not warehouse_id:
                logger.warning(
                    f"\n{'='*60}\n"
                    f"[WAREHOUSE CONFIG] ✗ No prefix found\n"
                    f"{'='*60}\n"
                    f"Warehouse: {warehouse_name}\n"
                    f"Response data: {json.dumps(data, indent=2, ensure_ascii=False)}\n"
                    f"{'='*60}"
                )
                return None

            logger.info(
                f"\n{'='*60}\n"
                f"[WAREHOUSE CONFIG] ✓ Success\n"
                f"{'='*60}\n"
                f"Warehouse: {warehouse_name}\n"
                f"Warehouse ID: {warehouse_id}\n"
                f"{'='*60}"
            )

            return warehouse_id

        except httpx.HTTPStatusError as e:
            logger.error(
                f"\n{'='*60}\n"
                f"[WAREHOUSE CONFIG] ✗ HTTP Error\n"
                f"{'='*60}\n"
                f"Warehouse: {warehouse_name}\n"
                f"Status code: {e.response.status_code}\n"
                f"Response: {e.response.text}\n"
                f"{'='*60}"
            )
            return None
        except Exception as e:
            logger.error(
                f"\n{'='*60}\n"
                f"[WAREHOUSE CONFIG] ✗ Exception\n"
                f"{'='*60}\n"
                f"Warehouse: {warehouse_name}\n"
                f"Error: {e}\n"
                f"{'='*60}",
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
