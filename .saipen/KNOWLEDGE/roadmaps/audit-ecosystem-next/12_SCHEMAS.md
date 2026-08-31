# 12 — CONCEPTUAL SCHEMAS

Adapt names to repository FIT.

## Audit inbox binding

```json
{
  "schema_version": 1,
  "layers": {
    "audit/18.md": {
      "layer": 18,
      "file_sha256": "...",
      "size_bytes": 12000,
      "receipt_id": "SRC-055",
      "work_id": "T-1301",
      "state": "ACTIVE",
      "producer": "SAIPAL",
      "producer_item_id": "PAL-0042"
    }
  }
}
```

This is a projection/binding.

Source Receipt remains semantic authority.

## Allocator

```json
{
  "schema_version": 1,
  "last_allocated_id": 18,
  "last_operation_id": "..."
}
```

Do not infer future IDs only from currently existing files once deletions are normal.

## Enqueue result

```json
{
  "audit_id": 18,
  "path": "audit/18.md",
  "sha256": "...",
  "producer": "SAIPAL",
  "producer_item_id": "PAL-0042",
  "operation_id": "audit-enqueue-..."
}
```

## Maintainer result projection

```json
{
  "audit_id": 18,
  "audit_sha256": "...",
  "producer": "SAIPAL",
  "producer_item_id": "PAL-0042",
  "receipt_id": "SRC-055",
  "work_id": "T-1301",
  "disposition": "REJECTED_FINDING",
  "fix_commit": null,
  "closed_at": "..."
}
```
