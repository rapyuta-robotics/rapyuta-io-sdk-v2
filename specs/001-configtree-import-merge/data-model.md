# Data Model: Configtree Import and Fast Merge

**Related artifacts**: [specification](spec.md), [interface contract](contracts/sdk-interface.md), [lifecycle contract](contracts/revision-lifecycle.md)

## Existing platform models

Reuse `models/configtree.py` and `models/utils.py` without changing their general low-level validation semantics.

| Model | Relevant fields | Role |
| --- | --- | --- |
| `ConfigTree` | `metadata`, `head`, `keys` | Scoped tree and selected revision; `keys` is optional on the wire |
| `BaseMetadata` | required `name`, optional `guid`, scope GUIDs, labels | Tree identity; used in head-selection requests |
| `ConfigTreeRevision` | `metadata`, `parent`, `message`, `author`, `committed` | Initialization/commit payload and returned revision |
| `ConfigTreeRevisionMetadata` | optional `name`, `guid`, labels | Revision ID and optional commit labels; supports GUID-only head payloads |
| `ConfigTreeRevisionList` | `items`, `metadata` | Milestone candidates from a single page |
| `ListMeta` | `continue_: int or None` | Numeric next-page offset, serialized as `continue` |
| `ConfigValue` | `permissions`, `metadata`, `checksum`, `content_type`, `content_length`, `url`, `data` | Key storage payload; explicit aliases preserve platform names |
| `ConfigValues` | root dictionary of `ConfigValue` | Batch request serialized directly as the key map |
| `APIResponse` | optional `success`, `error` | Batch acknowledgement; only true success without a nonempty error permits publication |

Field presence matters: absent metadata and explicitly supplied `{}` differ during Merge. `exclude_unset=True` must survive snapshotting, validation, and submission. A data-included Merge read must contain a non-null whole key map; explicit `{}` is valid, while omission or null is a resolution error. Missing entry data is not empty text.

## Options models

Define in `models/configtree_operations.py`, export through `models/__init__.py`, and make available from `rapyuta_io_sdk_v2.configtree`.

| Model | Fields/defaults | Validation and relationship |
| --- | --- | --- |
| `RevisionOptions` | `with_project=True`, `commit=False`, `commit_body=None` | Frozen helper options; `commit_body` is an optional `ConfigTreeRevision`; deep-copy nested values into execution state |
| `ImportOptions` | all `RevisionOptions` fields plus `update_head=False` | All four commit/head combinations remain representable |
| `MergeOptions` | `with_project=True`, `commit_body=None` | Merge always commits and updates the head; these actions cannot be disabled |

No options model is sent directly to the platform. When committing, fill missing author from configured email or `rapyuta-io-sdk-v2`, and missing message from the operation default: `Created revision through rapyuta-io-sdk-v2` for direct contexts, `Imported configuration through rapyuta-io-sdk-v2` for Import, and `Merged configuration through rapyuta-io-sdk-v2` for Merge. Explicit empty/whitespace-only author or message is invalid before creation. Preserve supplied labels. Missing commit bodies do not require operating-system user lookup or additional platform calls.

## Configuration documents and metadata attachments

**Document**: A named UTF-8 JSON/YAML file, its basename stem, and parsed mapping content. Supported suffixes are `.json`, `.yaml`, and `.yml`. Filenames and all documents are prepared before mutation; duplicate stems are invalid.

**Supported content**: Strings, finite numbers, booleans, null, dates/datetimes, lists, and string-keyed mappings. Dates normalize to ISO strings. Lists remain leaf values; empty nested mappings are object leaves. Reject duplicate mapping entries, cyclic collections, unsupported YAML types, and content paths that would be ambiguous. This import validation does not apply new restrictions to the settings source.

**Metadata wrapper**: A mapping-valued child with exactly `value` and `metadata`, where the latter is a dictionary. Recognition allows empty metadata and any supported wrapped value, including null. Metadata schema validation is separate from recognition.

**Split result**: Content mapping plus opaque metadata attachments associated with path tuples. Ordinary mapping children are traversed; wrapper values and lists are not traversed during splitting. Attachments preserve complete `dict[str, str]` objects, including slash-containing metadata names. During flattening, filename stems prefix both paths. Join attachments to content only at identical final paths; never inherit parent attachments onto descendants.

Sharing this splitter with `ConfigTreeSource` means its `_split_metadata` returns only the content component. Its existing parser, flattening, settings behavior, and public inputs remain unchanged.

## Refspec and scoped routing

**`ConfigTreeRef`**: Immutable four-field tuple with `is_org: bool`, `tree_name: str`, `revision_id: str or None`, and `milestone: str or None`. Parsing produces at most one selector. `org` maps to true; `proj` maps to false. Selectors beginning with `rev-` are revision IDs; all others are milestones.

**Scope snapshot**: Private immutable record of `organization_guid`, optional `project_guid`, and `with_project`. Require organization context; project operations also require project context. Capture and pass source and destination contexts independently without changing caller configuration. A refspec selects scope within the caller's configured organization/project; cross-organization discovery is excluded.

**Resolved revision**: Scoped tree identity, selected revision GUID, and validated key-value map. Milestone resolution checks all relevant numeric pages, validates exact label matches, and requires one distinct GUID. Selected entry data must be present; missing whole maps on otherwise valid selected revisions normalize to empty.

## Pending dictionary and key snapshots

**Live dictionary**: A per-context `dict[str, ConfigValue]` exposed through a getter-only `keys` property. Adds, replacements, metadata edits, removal, and clear affect staged contents immediately. The property always returns the same dictionary. Removing a key does not delete inherited platform content.

**Encoded staged value**: `store()` builds a typed key-value entry from logical content with UTF-8/base64 data, MD5 artifact checksum, byte count, `content_type="kv"`, and default permissions `"644"`. Replacement through `store()` regenerates dependent fields. Direct entry assignments use complete valid `ConfigValue` payloads, not raw logical values.

**Final snapshot**: Independent plain-field copies of current entries, rebuilt with strict `ConfigValue`/`ConfigValues` validation. Validate nonempty string key paths with no empty segments or surrounding whole-key whitespace, present base64 key-value data, required content type/checksum and content length, and compatible field types. A supplied checksum and content length must agree with decoded bytes; direct edits that leave stale derived fields fail. Preserve declared optional fields. Before destination creation, reject any selected Merge source entry with absent or inconsistent content length, including an entry at a shared key; identify the key and leave the source payload unchanged. Do not repair or re-serialize Merge payloads.

The snapshot is prepared before awaiting batch submission. Supported edits occur inside the context body. The behavior of edits through retained references after the body exits, including during finalization, is unspecified; contexts are not a transaction or a shared concurrent editor.

## Revision lifecycle state

Private state carries tree/scope, copied options, optional pinned parent, live keys, `revision_id`, and current stage. Context construction is local. Entry calls initialization once. The parent normally follows the platform's current head; Merge supplies the checked destination head explicitly. Platform initialization copies a committed parent's keys.

```text
NEW -> CREATING -> ACTIVE -> VALIDATING -> STORING -> STORED
                                     \-> STORED (empty batch)
STORED -> COMMITTING -> COMMITTED -> CLOSED
STORED ---------------------------> CLOSED (commit disabled)
ACTIVE -> ABORTED (body exception/cancellation; no finalization)
any executing stage -> FAILED/CANCELLED (no later stage starts)
```

After context success the workflow may perform `HEAD` selection; this is not context finalization. Contexts are single-use. Closed/failed contexts cannot initialize or finalize again; edits through retained dictionary references are outside the supported contract. A valid empty merge still initializes and commits a new revision.

## Failure recovery

Input/reference/conflict errors carry file, refspec, or sorted conflicting-key information as applicable. Platform/transport/Pydantic errors retain their original types. After initialization, annotate known `configtree_revision_id` and `configtree_stage` on the original exception and in an exception note. Cancellation retains `CancelledError` with the same recovery annotations; no shielding, replacement, retry, or cleanup request follows it.

Stages are `prepare`, `resolve`, `create`, `body`, `validate`, `store`, `commit`, and `head`. If creation completes remotely without returning a GUID, its ID is unknown. A failure in any later request may also represent uncertain remote completion; the local state never claims rollback or publication success.
