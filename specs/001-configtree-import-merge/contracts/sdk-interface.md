# SDK Interface Contract

**Status**: Planned public interface; implementation is pending.

**Specification**: [spec.md](../spec.md) | **Models**: [data-model.md](../data-model.md) | **Context behavior**: [revision-lifecycle.md](revision-lifecycle.md)

## Public package and types

Expose the following from `rapyuta_io_sdk_v2.configtree`:

```python
class RevisionOptions(SDKModel):
    with_project: bool = True
    commit: bool = False
    commit_body: ConfigTreeRevision | None = None


class ImportOptions(RevisionOptions):
    update_head: bool = False


class MergeOptions(SDKModel):
    with_project: bool = True
    commit_body: ConfigTreeRevision | None = None


class ConfigTreeRef(NamedTuple):
    is_org: bool
    tree_name: str
    revision_id: str | None
    milestone: str | None


def parse_refspec(refspec: str) -> ConfigTreeRef: ...


def import_configtree(
    client: Client,
    tree_name: str,
    files: Iterable[str | Path],
    *,
    options: ImportOptions | None = None,
) -> str: ...


async def import_configtree_async(
    client: AsyncClient,
    tree_name: str,
    files: Iterable[str | Path],
    *,
    options: ImportOptions | None = None,
) -> str: ...


def merge_configtree(
    client: Client,
    tree_name: str,
    refspec: str,
    *,
    options: MergeOptions | None = None,
) -> str: ...


async def merge_configtree_async(
    client: AsyncClient,
    tree_name: str,
    refspec: str,
    *,
    options: MergeOptions | None = None,
) -> str: ...
```

These are interface sketches, not implementation bodies. Options models live in `models/configtree_operations.py` and are frozen; execution snapshots nested commit bodies. `None` options create fresh default options, not shared mutable defaults. Public methods document typed inputs, returns, and all failures. The helpers retain ownership of neither the client nor its transports.

## Import

`files` is a nonempty iterable of named local paths; a bare string/path is not itself a file collection. Materialize it once. Parse all files and prepare the full typed map before creating a revision. Accept mixed JSON/YAML/YML, one mapping-root document per file, prefixing by the basename with only the final suffix removed.

Split metadata before flattening using exactly the specification's recognition and traversal rules. Validate every extracted attachment, even when a wrapped mapping later produces no exact matching leaf path. Preserve empty attachments and do not emit their names as configuration keys. Input errors identify the file and relevant key/path when known.

Create exactly one fresh revision. The platform's normal inheritance remains intact; imported paths update that revision without requesting deletion of unrelated keys. Complete one nonempty batch before any commit or head selection. Return the created revision GUID as a string only after every requested stage succeeds.

| `commit` | `update_head` | Required outcome |
| --- | --- | --- |
| false | false | Store a new uncommitted revision; keep the old head |
| true | false | Store and commit; keep the old head |
| false | true | Store then attempt head selection; propagate any platform rejection of an uncommitted head with recovery information |
| true | true | Store, commit, then select head |

When committing, default message is `Imported configuration through rapyuta-io-sdk-v2`. Missing author defaults to configured email, then `rapyuta-io-sdk-v2`. Preserve caller commit labels; reject explicitly empty author/message before creation.

## Refspec grammar and resolution

```text
refspec  = scope "/" tree ["/" selector]
scope    = "org" | "proj"
tree     = nonempty component without "/"
selector = nonempty component without "/"
```

Reject missing/extra components, unsupported scope, and blank/whitespace-only tree or selector. Do not silently trim or reinterpret supplied identifiers. A selector starting with `rev-` sets `revision_id`; every other selector sets `milestone`. Both fields are absent for a two-component refspec.

| Input | Returned tuple |
| --- | --- |
| `org/source` | `(True, "source", None, None)` |
| `org/source/rev-123` | `(True, "source", "rev-123", None)` |
| `org/source/release` | `(True, "source", None, "release")` |
| `proj/source` | `(False, "source", None, None)` |
| `proj/source/rev-123` | `(False, "source", "rev-123", None)` |
| `proj/source/release` | `(False, "source", None, "release")` |

Parsing is pure. Resolving a missing selector reads the source head; an explicit selector reads the requested revision; milestones use `rapyuta.io/milestone=<name>`, inspecting advancing numeric pages and checking the actual label. Zero matches, multiple distinct revision matches, malformed continuation, or a missing revision GUID fail before destination mutation. `committed=False` in the list request means no committed-only filter. An explicit historical source must not be replaced with the current head.

## Merge

The destination scope comes from `MergeOptions.with_project`; the source scope comes from the refspec. Both use the caller's configured organization/project IDs captured for the workflow. Reads and mutations receive explicit per-call scope options; client configuration is never changed. Required missing scope IDs fail before mutation.

Read the destination head and selected source revision with data included and key-value content selected. Require valid revision identities and non-null whole key maps before destination revision creation. Explicit `{}` is valid; omitted or null maps and selected entries without data are invalid. The destination must be usable as a committed parent under the platform contract.

Shared entries are compatible only when their stored base64 data and metadata are equal. Metadata absence differs from `{}`. Permissions or other artifact fields do not alone make a conflict; retain the destination entry when a shared key is compatible. Keep all destination-only entries and copy source-only entries. Before creating a destination revision, require every selected source key to have a content length equal to its decoded byte count, including compatible shared keys; reject absent or inconsistent lengths with the key identified. Deep-copy valid staged payloads without re-encoding or re-serializing their stored data or repairing derived fields.

Report all conflicting key names before creating a revision. There is no editor, prompt, partial merge, or conflict-skip option. A compatible Merge always creates one new revision with the checked destination head as explicit parent, submits the union in one batch when nonempty, commits, and then selects it as head. Return the new GUID. The selected source revision and any different source tree's head remain unchanged. An empty/identical union still creates, commits, and selects one revision.

Default message is `Merged configuration through rapyuta-io-sdk-v2`; author fallback and caller-supplied metadata follow Import's rules. No option disables commit or head selection. The platform may inherit non-key-value content from the parent; this workflow never deletes it.

## Existing client requests

| Operation | Request |
| --- | --- |
| `get_configtree` | `GET /v2/configtrees/{name}/`; supply filters/selectors only when present |
| `list_revisions` | `GET /v2/configtrees/{name}/revisions/`; numeric `continue`, `limit`, optional label selector |
| `create_revision` | `POST /v2/configtrees/{name}/revisions/`; optional `ConfigTreeRevision` parent body |
| `put_keys_in_revision` | `PUT /v2/configtrees/{name}/revisions/{revision_id}/`; direct `ConfigValues` key map, no `/keys/` suffix |
| `commit_revision` | `PATCH /v2/configtrees/{name}/revisions/{revision_id}/`; flattened typed commit body |
| `set_configtree_revision` | `PUT /v2/configtrees/{name}/`; typed tree metadata plus GUID-only head reference |

Headers include organization context and include project context only for project scope. `with_project=False` suppresses the project header; passing a null project GUID alone does not. Both client variants serialize typed payloads with aliases and omitted-field preservation and validate responses with their existing models. Async requests must use awaited methods.

## Errors and recovery

Export domain failures from the helper package: `ConfigTreeInputError` (invalid files/content/names), `ConfigTreeReferenceError` (invalid or unresolved refspec/base/key map), `ConfigTreeMergeConflictError` (sorted conflicting keys), and `ConfigTreeMutationError` (batch without affirmative acknowledgement). Input/reference/conflict errors subclass `ValueError`; mutation-envelope errors subclass `RuntimeError`. Domain errors expose contextual fields such as `file_path`, `key`, `refspec`, or `conflicting_keys` as applicable; secrets/content are not included in messages.

Original client HTTP errors, HTTPX transport errors, Pydantic validation errors, and body exceptions keep their types and causes. Add `configtree_revision_id` when known, `configtree_stage`, and an exception note describing recovery context. `getattr(error, "configtree_revision_id", None)` retrieves the identifier without depending on a particular underlying exception class. Async cancellation remains `asyncio.CancelledError` with the same annotations; never convert it into a normal exception.

No later workflow stage starts after an error or cancellation. Requests may have completed remotely despite failure; there is no automatic retry/rollback and no guarantee of unchanged remote state after a dispatched mutation. A rejected compatibility/input check before creation makes zero destination mutations. A creation failure without a returned GUID cannot promise recovery by identifier.

## Concurrency and lifecycle limits

Source and destination snapshots are not an atomic cross-tree transaction. Explicit Merge parents preserve the checked base at creation, but head update has no compare-and-swap. Callers should serialize writers when they require ordering. Dictionary edits are supported inside the revision context body; edits through retained references after the body exits, including during finalization, have unspecified behavior. The helper neither closes caller clients nor changes their configuration.
