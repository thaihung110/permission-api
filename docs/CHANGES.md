# Permission API - recent changes (column masking integration)

- Added batch column masking policy for Trino: `opa/policies/trino/column_mask.rego`
  - Default unmask; mask only when a `MaskColumn` tuple exists (checked via permission-api).
  - Uses `rbac.call_permission_check` to evaluate relation `mask` on `column:<catalog>.<schema>.<table>.<column>`.
- Extended permission-api to handle column resources:
  - `models.py`: `ResourceSpec` now supports `column`.
  - `operation_mapper.py`: maps `MaskColumn` -> `mask` relation.
  - `utils.py`: `build_object_id_from_resource` builds column object IDs.
  - `routers/permissions.py`: grant/revoke/check handle column-level object IDs.
