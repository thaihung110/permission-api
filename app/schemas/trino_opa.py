"""
Trino OPA compatible schemas

These schemas match the format that Trino sends to OPA for access control.
This allows our permission API to act as a drop-in replacement for OPA.

Trino OPA plugin documentation:
https://trino.io/docs/current/security/opa-access-control.html
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# =============================================================================
# Identity and Context
# =============================================================================


class TrinoIdentity(BaseModel):
    """User identity from Trino"""

    user: str = Field(
        ..., description="User identifier (can be UUID or username)"
    )
    groups: List[str] = Field(default_factory=list, description="User groups")


class TrinoSoftwareStack(BaseModel):
    """Software stack information"""

    trinoVersion: str = Field(..., description="Trino version")


class TrinoContext(BaseModel):
    """Request context from Trino"""

    identity: TrinoIdentity
    softwareStack: Optional[TrinoSoftwareStack] = None


# =============================================================================
# Resource Types
# =============================================================================


class TrinoCatalogResource(BaseModel):
    """Catalog resource"""

    name: str = Field(..., description="Catalog name")


class TrinoSchemaResource(BaseModel):
    """Schema resource"""

    catalogName: str
    schemaName: str


class TrinoTableResource(BaseModel):
    """Table resource"""

    catalogName: str
    schemaName: str
    tableName: str
    columns: Optional[List[str]] = None


class TrinoColumnResource(BaseModel):
    """Column resource (used in GetColumnMask and other column operations)"""

    catalogName: str
    schemaName: str
    tableName: str
    columnName: str


class TrinoFunctionResource(BaseModel):
    """Function resource"""

    catalogName: Optional[str] = None
    schemaName: Optional[str] = None
    functionName: str


class TrinoSystemInformationResource(BaseModel):
    """System information resource"""

    pass


class TrinoProcedureResource(BaseModel):
    """Procedure resource"""

    catalogName: str
    schemaName: str
    procedureName: str


class TrinoResource(BaseModel):
    """Union of all resource types"""

    catalog: Optional[TrinoCatalogResource] = None
    schema_: Optional[TrinoSchemaResource] = Field(None, alias="schema")
    table: Optional[TrinoTableResource] = None
    column: Optional[TrinoColumnResource] = None
    function: Optional[TrinoFunctionResource] = None
    systemInformation: Optional[TrinoSystemInformationResource] = None
    procedure: Optional[TrinoProcedureResource] = None

    class Config:
        populate_by_name = True


# =============================================================================
# Action
# =============================================================================


class TrinoAction(BaseModel):
    """Action to be authorized"""

    operation: str = Field(
        ...,
        description="Trino operation (e.g., SelectFromColumns, AccessCatalog)",
    )
    resource: Optional[TrinoResource] = None
    targetResource: Optional[TrinoResource] = None
    grantee: Optional[TrinoIdentity] = None


# =============================================================================
# Request/Response for Single Check (/v1/data/trino/allow)
# =============================================================================


class TrinoOpaInput(BaseModel):
    """Input wrapper for Trino OPA request"""

    context: TrinoContext
    action: TrinoAction


class TrinoOpaRequest(BaseModel):
    """
    Request format that Trino sends to OPA for authorization.

    This is the format for the `/v1/data/trino/allow` endpoint.
    """

    input: TrinoOpaInput


class TrinoOpaResponse(BaseModel):
    """
    Response format that OPA returns to Trino.

    Simple boolean result.
    """

    result: bool = Field(..., description="Whether the operation is allowed")


# =============================================================================
# Request/Response for Batch Check (/v1/data/trino/batch)
# =============================================================================


class TrinoBatchItem(BaseModel):
    """
    Single item in a batch request.

    Format from Trino is the same as TrinoResource - resource fields at root level.
    Example: {"catalog": {"name": "system"}}
    """

    # Resource fields are at root level (same as TrinoResource)
    catalog: Optional[TrinoCatalogResource] = None
    schema_: Optional[TrinoSchemaResource] = Field(None, alias="schema")
    table: Optional[TrinoTableResource] = None
    column: Optional[TrinoColumnResource] = None
    function: Optional[TrinoFunctionResource] = None
    procedure: Optional[TrinoProcedureResource] = None

    class Config:
        populate_by_name = True


class TrinoBatchAction(BaseModel):
    """Batch action containing multiple operations"""

    operation: str = Field(default="FilterResources")
    filterResources: List[TrinoBatchItem] = Field(default_factory=list)


class TrinoBatchInput(BaseModel):
    """Input for batch request"""

    context: TrinoContext
    action: TrinoBatchAction


class TrinoBatchRequest(BaseModel):
    """
    Batch request format for `/v1/data/trino/batch` endpoint.

    Used for FilterCatalogs, FilterSchemas, FilterTables, etc.
    """

    input: TrinoBatchInput


class TrinoBatchResponse(BaseModel):
    """
    Batch response format.

    Returns list of indices that are allowed.
    """

    result: List[int] = Field(
        default_factory=list,
        description="List of indices of allowed resources",
    )


# =============================================================================
# Helper Functions
# =============================================================================


def extract_resource_from_trino(
    resource: Optional[TrinoResource],
) -> Dict[str, Any]:
    """
    Extract resource information from Trino format to our internal format.

    Trino format:
    - catalog: {"name": "lakekeeper"}
    - schema: {"catalogName": "lakekeeper", "schemaName": "finance"}
    - table: {"catalogName": "lakekeeper", "schemaName": "finance", "tableName": "user"}

    Internal format:
    - {"catalog": "lakekeeper"}
    - {"catalog": "lakekeeper", "schema": "finance"}
    - {"catalog": "lakekeeper", "schema": "finance", "table": "user"}
    """
    if resource is None:
        return {}

    result = {}

    # Handle catalog resource
    if resource.catalog:
        result["catalog"] = resource.catalog.name

    # Handle schema resource
    if resource.schema_:
        result["catalog"] = resource.schema_.catalogName
        result["schema"] = resource.schema_.schemaName

    # Handle table resource
    if resource.table:
        result["catalog"] = resource.table.catalogName
        result["schema"] = resource.table.schemaName
        result["table"] = resource.table.tableName
        if resource.table.columns:
            result["columns"] = resource.table.columns

    # Handle column resource
    if resource.column:
        result["catalog"] = resource.column.catalogName
        result["schema"] = resource.column.schemaName
        result["table"] = resource.column.tableName
        result["column"] = resource.column.columnName

    # Handle function resource
    if resource.function:
        if resource.function.catalogName:
            result["catalog"] = resource.function.catalogName
        if resource.function.schemaName:
            result["schema"] = resource.function.schemaName
        result["function"] = resource.function.functionName

    # Handle procedure resource
    if resource.procedure:
        result["catalog"] = resource.procedure.catalogName
        result["schema"] = resource.procedure.schemaName
        result["procedure"] = resource.procedure.procedureName

    return result


def extract_resource_from_batch_item(
    item: TrinoBatchItem,
) -> Dict[str, Any]:
    """
    Extract resource information from TrinoBatchItem to our internal format.

    TrinoBatchItem has resource fields at root level (not nested):
    - {"catalog": {"name": "system"}}
    - {"table": {"catalogName": "...", "schemaName": "...", "tableName": "..."}}

    Internal format:
    - {"catalog": "system"}
    - {"catalog": "...", "schema": "...", "table": "..."}
    """
    result = {}

    # Handle catalog
    if item.catalog:
        result["catalog"] = item.catalog.name

    # Handle schema
    if item.schema_:
        result["catalog"] = item.schema_.catalogName
        result["schema"] = item.schema_.schemaName

    # Handle table
    if item.table:
        result["catalog"] = item.table.catalogName
        result["schema"] = item.table.schemaName
        result["table"] = item.table.tableName
        if item.table.columns:
            result["columns"] = item.table.columns

    # Handle column
    if item.column:
        result["catalog"] = item.column.catalogName
        result["schema"] = item.column.schemaName
        result["table"] = item.column.tableName
        result["column"] = item.column.columnName

    # Handle function
    if item.function:
        if item.function.catalogName:
            result["catalog"] = item.function.catalogName
        if item.function.schemaName:
            result["schema"] = item.function.schemaName
        result["function"] = item.function.functionName

    # Handle procedure
    if item.procedure:
        result["catalog"] = item.procedure.catalogName
        result["schema"] = item.procedure.schemaName
        result["procedure"] = item.procedure.procedureName

    return result
