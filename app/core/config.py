"""
Configuration management using environment variables
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class Settings:
    """Application settings loaded from environment variables"""

    def __init__(self):
        # OpenFGA configuration
        self.openfga_api_url: str = os.getenv(
            "OPENFGA_API_URL", "http://openfga-2:8080"
        )
        self.openfga_store_id: Optional[str] = os.getenv("OPENFGA_STORE_ID")

        # Server configuration
        self.port: int = int(os.getenv("PORT", "8000"))
        self.host: str = os.getenv("HOST", "0.0.0.0")

        # API timeouts
        self.openfga_timeout: str = os.getenv("OPENFGA_TIMEOUT", "5s")

        # Logging
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")

        # Lakekeeper configuration
        self.lakekeeper_management_url: str = os.getenv(
            "LAKEKEEPER_MANAGEMENT_URL", "http://lakekeeper:8181/management"
        )
        self.lakekeeper_catalog_url: str = os.getenv(
            "LAKEKEEPER_CATALOG_URL", "http://lakekeeper:8181/catalog"
        )

        # Keycloak configuration for Lakekeeper authentication
        self.keycloak_token_url: str = os.getenv(
            "KEYCLOAK_TOKEN_URL",
            "http://keycloak:8080/realms/iceberg/protocol/openid-connect/token",
        )
        self.keycloak_client_id: str = os.getenv("KEYCLOAK_CLIENT_ID", "trino")
        self.keycloak_client_secret: str = os.getenv(
            "KEYCLOAK_CLIENT_SECRET", "AK48QgaKsqdEpP9PomRJw7l2T7qWGHdZ"
        )
        self.keycloak_scope: str = os.getenv("KEYCLOAK_SCOPE", "lakekeeper")

        # API configuration
        self.api_v1_prefix: str = "/api/v1"
        self.project_name: str = "Permission Management API"
        self.version: str = "1.0.0"


# Global settings instance
settings = Settings()
