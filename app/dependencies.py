"""
Shared dependencies for dependency injection
"""

from fastapi import Request

from app.external.openfga_client import OpenFGAManager
from app.services.permission_service import PermissionService


def get_openfga(request: Request) -> OpenFGAManager:
    """Get OpenFGA manager from app state"""
    return request.app.state.openfga


def get_permission_service(request: Request) -> PermissionService:
    """Create permission service with OpenFGA manager"""
    openfga = get_openfga(request)
    return PermissionService(openfga)
