# Data Model: Reusable SDK Applier

All public operation/options/result models below use the SDK's validated model base. Identity and scope values are frozen/hashable where used as graph keys. Existing platform resource payload fields, aliases, schemas, and omission behavior are retained. Non-payload source configuration is a frozen typed dataclass; MutationJournal is a concrete runtime recorder rather than a payload model. Contracts: [Applier](contracts/applier-api.md), [Resource](contracts/resource-interface.md), [Mutation progress](contracts/resource-progress.md), [SOPS](contracts/sops-helper.md).

## Source and prepared collection

| Entity | Fields | Rules and relationships |
| --- | --- | --- |
| ManifestSource | files: tuple[PathLike, ...]; resources: tuple[SupportedResource, ...]; values/secrets: ordered tuples of mapping or PathLike; rio: optional mapping | Snapshot iterables on construction. Files and resource instances can be combined. Values are merged first, explicit secrets and rio become reserved namespaces. Supplied secret values, including decrypted mappings, are ordinary input data without secret-specific repr exclusion or redaction. |
| SourceLocation | path or instance index; document index | Each resource and preparation error retains source context without embedding file contents. |
| PreparedResource (internal) | deep-copied resource model; identity; dependencies; source; input position | No caller model mutations. Common preparation validates the supplied model, identity, and graph without selecting a lifecycle operation. Response-only Secret/UserGroup instances require conversion/revalidation to the corresponding create model at apply preflight, including apply preview; inspection/delete do not impose creation-only requirements. Invalid creation credentials fail apply preflight. |
| PreparedCollection (internal) | resources in input order; name/GUID aliases; managed edges; external references; resolved manifests | Created without clients or network. Graph state is recreated per operation. Inspection returns independent copies, not internal mutable data. |

Plain YAML/JSON value sources must contain exactly one string-keyed mapping; JSON-compatible nested scalar/list/mapping values are supported. Empty value mappings are valid. Empty manifest documents contribute no resource; unsupported JSON arrays/scalars fail as manifest input. Recursive value merge preserves unrelated mapping keys and replaces lists/scalars at matching keys. Reserved `rio`/`secrets` are installed from their explicit inputs and are not overwritten by ordinary values.

Construction performs common local preparation: parse/render, validate supplied modeled fields and required identity, reject unsupported kinds, duplicates, ambiguous local aliases and cycles. Capability checks, apply-specific creation conversion, and retention exceptions belong to each requested operation's preflight, including preview. A valid Organization can therefore be prepared and inspected, while its non-retained delete fails at delete preflight. Live context checks apply only to live execution and precede platform requests.

## Identity, scope, and dependencies

| Entity | Fields | Validation |
| --- | --- | --- |
| ResourceScope | organization_guid: optional non-empty string; project_guid: optional non-empty string; organization_short_guid: optional non-empty string | Required values depend on the mapped operation. Options override configured defaults; preview can use unresolved scope. A resolved copy is used during execution. |
| ResourceReference | kind: normalized lower-case supported/reference kind; name and/or guid; optional package version | Require name or GUID. Preserve exact spelling of names, GUIDs and versions. Package references require non-empty version. User/Device references can be external even though their lifecycle is outside scope. |
| ResourceIdentity | kind; effective organization/project scope; name for named resources; version for Package; role/subject/domain references for RoleBinding | Named resources require name. RoleBinding requires typed subject and domain kinds plus reference identifiers, rather than metadata.name. Structured tuples establish equality; display keys never get parsed for identity. |
| DependencyReference | reference; wait: bool=false | Resolve known local GUID and name aliases into managed identities. A package edge uses the referenced version. Wait applies to explicit deployment readiness references. Deduplicate identical edges; do not discard different versions. |
| ResourceCapabilities | create/update/delete booleans; apply_policy: create_or_update/create_or_exists/update_only/grant; readiness_kind | Immutable metadata, not serialized platform fields. Known unsupported operations fail before writes. |

Effective identity/routing scope is kind-specific:

| Kinds | Identity/routing scope |
| --- | --- |
| Organization | Identified organization GUID; selected project is irrelevant |
| Project | Selected organization plus the target Project name/GUID; selected project is irrelevant |
| UserGroup, Role, RoleBinding, ServiceAccount | Selected organization; selected project is irrelevant |
| Package, Deployment, Disk, Network, StaticRoute, Secret | Selected organization and project |

UserGroup group GUID comes from the resolved object, not a global group selection. RoleBinding domain is part of the grant identity. Alias/dependency matching drops irrelevant project scope according to the referenced kind, so a project-scoped resource can depend on an organization-scoped role or service account.

Scope is selected for an operation, not global SDK configuration mutation. Project/organization resource GUIDs identify their target objects. RoleBinding domain references describe the grant's domain and must not become a context-setter call. For aliases, managed resources known by both name and GUID resolve to one node. Conflicting local aliases fail preflight. Offline preparation cannot prove equivalence of unrelated external name-only and GUID-only references; exact platform lookups resolve them when an operation requires it.

A ResourceIdentity with unresolved scope is only an offline collection key; execution binds it to the selected effective scope before final results. Known explicit routing conflicts fail before the first write. Project metadata.organization_guid is populated on a private copy from the selected organization, preserving the CLI's intended routing behavior.

## Settings and context

| Entity | Fields/defaults | Validation |
| --- | --- | --- |
| ReadinessOptions | checks=50; interval=6.0 seconds | checks >=1; interval finite and >=0. Count polling rounds per readiness target, not retries of writes. Paginated lookup within a round is part of that round. Check immediately; each target has at most checks-1 between-round sleeps. |
| ApplierOptions | workers=6; readiness=ReadinessOptions(); scope=ResourceScope() | Positive non-boolean integer workers. Timeout and connection-pool settings belong to the supplied client and are not overridden. |
| ResourceContext | scope; readiness; progress: MutationJournal or None, default None | Frozen typed argument to direct resource lifecycle methods. Clients are supplied separately, not stored or serialized in context. Progress is an explicitly supplied runtime reference excluded from serialization, repr, and JSON Schema; scope/readiness remain immutable. |
| SopsOptions | executable='sops'; termination_grace=1.0 seconds | Non-empty executable; finite positive grace. Only executable location and cleanup grace configurable, not arbitrary command arguments. |

A source plus ApplierOptions creates an Applier facade, with no client constructor argument or stored client. Each non-empty live apply/delete call requires its client; offline preview can omit it. Applier snapshots that call's client context, uses the exact instance only for that operation, and never creates, closes, or replaces its transports. Re-resolve scope and lookup/routing caches for every call, including sequential calls using different clients. No execution context is necessary for offline preview. The same facade permits sequential repeated runs with the same or different clients, but simultaneous calls on one facade are rejected to keep `last_result` and operation ownership unambiguous; different facades may share a caller-managed client if the caller permits it.

## Mutation progress channel

| Entity | Fields/interface | Validation and ownership |
| --- | --- | --- |
| MutationAttempt | sequence: positive non-boolean integer; action: created/updated/deleted/revoked; state: started/completed/rejected/uncertain | Frozen validated model, with no client, resource payload, response, or exception. Sequence increases within one journal. |
| MutationJournal | begin(action) -> sequence; complete(sequence), reject(sequence), mark_uncertain(sequence); snapshot() -> tuple[MutationAttempt, ...] | Concrete typed mutable recorder with synchronous bookkeeping only. Fresh per resource operation, never shared across workers or reused across facade calls. Returned snapshots are immutable and detached from later journal changes. |

Put both types in models/progress.py, which depends only on the model base and standard typing/Pydantic facilities; it must not import clients, apply modules, or resource models. ResourceContext accepts the exact supplied journal instance using SkipJsonSchema[MutationJournal | None] and Field(default=None, exclude=True, repr=False). Enable arbitrary_types_allowed only on ResourceContext, not on SDKModel or resource payload classes. Normal type validation is permitted; no runtime operation discovery or reflective dispatch is introduced.

The scheduler creates and retains one journal outside each resource call, and passes it through that worker's ResourceContext. Named helpers journal each actual write; outer lifecycle policy does not duplicate entries. Mark started immediately before the client invocation, completed immediately after its validated successful response, and rejected only for a documented definitive no-effect rejection. Mark uncertain on cancellation or an unconfirmed effect, including transport interruption or response-validation failure, then re-raise the original exception. These bookkeeping steps contain no await, callback, logging, or platform access. Reads, readiness, retention, and a lookup establishing absence produce no mutation entry.

Settlement derives completed_actions from completed attempts and write_uncertain from uncertain or still-started attempts even when no ResourceOutcome was returned. Returned successful outcomes use the same journal snapshot; do not append their completed_actions again. Journals retain no clients or payloads and are discarded after immutable result construction. Never deep-copy a ResourceContext's recorder or recreate it between nested writes for the same resource.

Direct lifecycle calls with progress=None create a local journal for the call; direct callers who need progress after exceptions/cancellation supply and retain their own fresh journal. Cancellation remains the original CancelledError, with no partial-result wrapper or exception mutation. Such callers read their journal; collection callers read last_result after settlement. The full transition and caller contract is in [resource-progress.md](contracts/resource-progress.md).

## Results and errors

| Entity | Fields | Meaning |
| --- | --- | --- |
| ResourceOutcome | identity; source; operation; status; planned_action; completed_actions; failure; incomplete_reason; write_uncertain | One result for every managed input resource, ordered by input rather than worker completion. Outcomes contain lifecycle data rather than raw resource payloads. |
| ApplierResult | operation: apply/delete; dry_run; outcomes: tuple; successful: bool | Immutable snapshot. Successful includes exists/absent/retained and valid plans; failure or incomplete work makes live execution unsuccessful. |
| OperationFailure | category; stage; message; optional exception type | Source/resource/operation diagnostics; arbitrary platform response bodies are not copied into results. |
| DependencyGraph | managed identities; edges from prerequisite to dependent; external references | Inspectable data; reversed by the delete scheduler internally. No Graphviz requirement. |
| InspectionResult | resource_identities: tuple; resolved_manifests: tuple of independent copies; dependency_graph: DependencyGraph | Explicit inspection can contain resolved secret values. SDK does not print or persist it automatically. Injected values have no special protection in inspection, representations, or diagnostics. |
| SopsDecryptionError | source; category; optional return_code; safe guidance | Never contains stdout/stderr or chained decoded-content/parser exceptions. Categories: unavailable, source, decryption, invalid_content. |

Outcome statuses: `created`, `updated`, `exists`, `deleted`, `absent`, `retained`, `planned`, `failed`, `not_completed`. `not_completed` carries `cancelled`, `blocked`, or `not_started`. Planned apply actions are `create_or_update`, `create_or_exists`, `update`, or `grant`; planned delete actions are `delete` or `revoke`. A retained resource is reported `retained` even in preview. Offline planning cannot claim to know whether a platform resource exists.

Mutation steps are recorded as `created`, `updated`, `deleted`, or `revoked` immediately after their validated responses through the retained journal. Example: a Project is created and updated but readiness fails; its outcome is `failed` with `completed_actions=('created', 'updated')`. An interrupted or otherwise unconfirmed write sets `write_uncertain=True`; absence of a completed step does not prove absence of a platform effect. Cancellation during readiness alone does not make earlier completed writes uncertain. Definitively rejected create followed by successful update contributes only `updated` to completed_actions.

## State transitions

- Preparation: input → rendered → validated → identities/edges checked → prepared, or preflight error. No platform mutations in this sequence.
- Apply: pending → running → optional create/update/grant → optional waiting → created/updated/exists, or failed/not_completed.
- Delete: pending → retained, or running → deleted/absent; revoke uses the identified exact grant.
- Preview: prepared → planned/retained, with no client construction or platform request.
- Failure: failing node → failed; interrupted workers → not_completed/cancelled; descendants → not_completed/blocked; other queued nodes → not_completed/not_started. No new node begins after stop is observed.
- Caller cancellation: settle workers while leaving the supplied client open → publish last_result → propagate original CancelledError. No automatic rollback.
- SOPS: source validated → process owned → successful exit → decoded mapping, or categorized failure. Cancellation drains/reaps the process before propagation.

## Existing models and compatibility

Participating kinds: Organization, Project, Package, Deployment, Disk, Network, StaticRoute, Secret/SecretCreate, UserGroup/UserGroupCreate, Role, RoleBinding, and ServiceAccount. SecretCreate and UserGroupCreate are creation payload variants, not additional kinds. They retain secrets and explicit membership data that response models may omit.

ResourceMethods supplies common implementation with explicit override hooks and typed ClassVar capability metadata. Resource models override client operations, dependencies, and special cases; a typing-only Resource protocol describes the signatures for static checking. No getattr/hasattr, inferred method names, or reflection-based runtime discovery is used. Do not store clients, graph state, response caches, or derived IDs as serialized resource fields. Model-level compatibility checks compare schemas, aliases, and exclude_unset output before/after adding methods. Preserve existing legacy list_dependencies behavior where callers rely on it; use the new resource_dependencies interface for canonical Applier identity and readiness.
