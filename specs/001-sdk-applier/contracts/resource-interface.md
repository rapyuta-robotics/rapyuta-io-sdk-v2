# Contract: Resource Interface and Lifecycle Mapping

Add the field-free ResourceMethods mixin to the 12 covered kinds. It provides common behavior; each model declares typed ClassVar capabilities and explicitly overrides resource-specific operations and special cases. SecretCreate and UserGroupCreate keep existing payload inheritance and override request-variant behavior where needed. A typing-only Resource protocol describes the common signatures and is not runtime-checked. Do not add Pydantic fields, computed serialized properties, transport references, or graph caches to resource payloads. Clients retain one-operation behavior.

ResourceContext carries immutable scope/readiness and optional runtime-only progress: MutationJournal | None. The scheduler supplies a fresh recorder per resource operation; direct lifecycle calls create a local recorder when none is supplied. Direct callers needing progress after exceptions/cancellation may supply and retain a fresh recorder. Preserve the exact reference throughout nested helpers; never deep-copy it into separate journals. Dumps, repr and JSON Schema omit this field. The types, transitions, ownership and cancellation contract are specified in [resource-progress.md](resource-progress.md).

## Paired methods

```python
resource_identity(*, scope: ResourceScope | None = None) -> ResourceIdentity
resource_dependencies(*, scope: ResourceScope | None = None) -> tuple[DependencyReference, ...]
resource_capabilities() -> ResourceCapabilities
retention_policy() -> Literal["retain", "delete"]

create_object(client: Client, *, context: ResourceContext) -> SDKModel
update_object(client: Client, *, context: ResourceContext) -> SDKModel
delete_object(client: Client, *, context: ResourceContext) -> ResourceOutcome
apply(client: Client, *, context: ResourceContext) -> ResourceOutcome

async create_object_async(client: AsyncClient, *, context: ResourceContext) -> SDKModel
async update_object_async(client: AsyncClient, *, context: ResourceContext) -> SDKModel
async delete_object_async(client: AsyncClient, *, context: ResourceContext) -> ResourceOutcome
async apply_async(client: AsyncClient, *, context: ResourceContext) -> ResourceOutcome
```

These are signature declarations, not implementation bodies. Concrete resource methods declare the existing validated resource/response return type; SDKModel in this interface summary is the shared upper bound. Unsupported operations raise UnsupportedResourceOperationError before requests; do not infer capabilities from catching the SDK's unrelated exported NotImplementedError. `create_object`/`update_object` return validated payload responses; `apply` implements the policy and readiness contract. Delete includes retention and absence handling and returns a lifecycle outcome. Direct methods have the same immutable-input, context, and readiness semantics as Applier execution; a direct outcome may omit collection SourceLocation.

Named write helpers journal each attempt immediately around the client invocation; outer common policy and special overrides consume the same snapshot without recording it twice. Prior completed actions remain available when a later write/readiness check raises. Unconfirmed writes remain uncertain, while caller cancellation is re-raised unchanged. Create/update still return their modeled responses; collection settlement and direct callers recover partial progress from the retained recorder even if no lifecycle outcome was returned.

ResourceMethods shares common policy through ordinary calls to its declared override hooks. Resource models own ordinary endpoint implementations: Role.create_object names client.create_role directly and uses shared scope/copy/mutation utilities; its asynchronous counterpart awaits the same endpoint through the async recorder. Secret and UserGroup own creation-request conversion. Shared helpers contain generic utilities and multi-call resource workflows, including exact GUID/canonical-name lookup and Project cache provisioning. Common apply policy accepts the resource's declared create/update callables. No method-name construction, getattr/hasattr-based method discovery, or class-to-client-operation dispatch registry is used. The loader's fixed manifest-kind-to-model map is only for parsing, not lifecycle dispatch. Sync routines call Client directly and may block; async routines await AsyncClient and use awaitable polling. Resource methods do not invoke asyncio.run or a thread executor. Explicitly unsupported operations remain methods with documented failures, satisfying a uniform interface without fabricating API support.

Disk, Network, Project, and Deployment additionally expose `readiness_state() -> tuple[str | None, bool, bool]`, returning the observed state, ready flag, and terminal-failure flag without I/O or mutation. These ordinary methods add no serialized fields. Shared polling consumes a typing-only readiness interface and treats an absent resource observation as `(None, False, False)`. Existing ready/terminal decisions, polling budgets, and missing-status behavior are preserved. The general Resource protocol does not require readiness from kinds without provisioning observations.

## Common implementation and explicit overrides

| Method/behavior | ResourceMethods default | Resource override |
| --- | --- | --- |
| resource_identity | Ordinary named identity using declared kind and metadata | Package adds version; RoleBinding uses its composite references |
| resource_dependencies | Empty tuple | Models with declared prerequisites build typed references from explicit fields |
| resource_capabilities | Return the model's declared ClassVar capabilities | Each kind supplies its typed capability constant |
| retention_policy | Read the known metadata.labels field and retention key | Override only if the modeled retention contract differs |
| create_object/update_object and async counterparts | Raise documented unsupported-operation error | Supported operations explicitly call the named typed client/helper function |
| delete_object and async counterpart | Handle retention/absence and return the outcome using declared deletion hooks | Each deletable resource implements _delete_object/_delete_object_async returning None after its client call |
| apply/apply_async | Execute the declared apply policy using self.create_object/self.update_object and paired async methods | Project cache bootstrap, RoleBinding grant semantics, and other special cases override explicitly |

The deletion hooks have signatures _delete_object(client: Client, *, context: ResourceContext) -> None and async _delete_object_async(client: AsyncClient, *, context: ResourceContext) -> None; default hooks raise UnsupportedResourceOperationError. Capability declarations and operation overrides must agree. Guard optional metadata through normal typed field access; do not probe attributes dynamically. Do not use getattr, hasattr, inspect, dir, dynamically built client method names, or a class-to-client-operation registry. Pydantic validation/serialization and the loader's fixed kind-to-model map remain ordinary input processing, not operation discovery.

## Identity and dependency obligations

Use the structural model in [data-model.md](../data-model.md). No dependencies means an empty tuple. Preserve legacy list_dependencies methods for compatibility; the new canonical typed method drives Applier.

- Package: kind + exact metadata.name + non-empty metadata.version; include referenced image-pull secrets.
- Deployment: include its metadata package reference with version, volumes, static routes, ROS networks, device reference where relevant, explicit deployment prerequisites with wait flags, service-account reference, and named secret-key references. Preserve every applicable declared relationship rather than one runtime branch overwriting another.
- Network/Secret: device prerequisite when explicitly supplied for device runtime. Validate required device references in executable manifests without dereferencing absent response-only fields.
- UserGroup: declared member references/roles and role domains. ServiceAccount: declared role/domain references. RoleBinding: role, subject, and domain references.
- Organization/Project: declared membership subject/role references; Project's enabled Docker cache also references its registry secret and external device. Include declared references only, never imply that every object depends on every organization/project manifest.
- Disk, StaticRoute, and Role: empty direct dependencies unless a currently modeled explicit reference exists.

RoleBinding identity uses normalized reference kinds and identifiers for role, subject and domain; metadata.name is neither required nor synthesized. Local known GUID/name aliases resolve references consistently. If a reference has neither identity or is ambiguous, reject it. External User/Device resources remain external nodes in inspection only.

## Existing operations and models

Each named method has an existing synchronous Client and awaitable AsyncClient counterpart. The table specifies endpoint-level request types, not new transport methods.

| Kind | Modeled requests → responses | Methods composed / endpoint-specific arguments | Apply policy |
| --- | --- | --- | --- |
| Organization | Organization → Organization | update_organization(body, organization_guid); get_organization only for explicit lookup/routing metadata | update_only |
| Project | Project → Project; lookups → ProjectList/Project | create_project(body); list_projects(name, organizations); get_project(project_guid); update_project(body, project_guid); delete_project(project_guid) | create_or_update with cache bootstrap |
| Package | Package → Package; lookups → PackageList/Package | create_package(body); get_package(name, version); delete_package(name, version); scoped list_packages if lookup requires it | create_or_exists |
| Deployment | Deployment → Deployment; lookups → DeploymentList/Deployment | create_deployment(body); get_deployment(name); list_deployments(names or guids); delete_deployment(name) | create_or_exists; do not call existing update_deployment |
| Disk | Disk → Disk | create_disk(body); get_disk(name); delete_disk(name) | create_or_exists plus readiness |
| Network | Network → Network | create_network(body); get_network(name); delete_network(name) | create_or_exists plus readiness |
| StaticRoute | StaticRoute → StaticRoute; optional lookup → StaticRouteList | create_staticroute(body); update_staticroute(name, body); delete_staticroute(name); get_staticroute(name), list_staticroutes(names=[...]), and get_organization for canonical routing when needed | create_or_update |
| Secret | SecretCreate → Secret | create_secret(body); update_secret(name, body); delete_secret(name) | create_or_update |
| UserGroup | UserGroupCreate → UserGroup on create; UserGroup → UserGroup on update | create_user_group(user_group); list_user_groups(name/guid); update_user_group(user_group with GUID); delete_user_group(group_name, group_guid) | create_or_update |
| Role | Role → Role | create_role(role); update_role(role); delete_role(role_name); get_role(role_name)/list_roles when reference reconciliation requires it | create_or_update |
| RoleBinding | BulkRoleBindingUpdate → BulkRoleBindingUpdate; lookups → RoleBindingList/RoleBinding | list_role_bindings(typed list filters); get_role_binding(binding_guid); update_role_binding(binding) | grant |
| ServiceAccount | ServiceAccount → ServiceAccount | create_service_account(service_account); update_service_account(service_account, name); delete_service_account(name) | create_or_update |

Construct new/update payloads through the existing models. Deep-copy before timestamp cleanup, GUID population, scope population, or feature changes. Preserve unset/explicit null semantics; never downcast credential-bearing SecretCreate to Secret. UserGroup update conversion must preserve explicit memberships/roles and validate the intended update model. Raw mappings are allowed during local manifest parsing, never as client request/response payloads.

Use method-specific typed scope options from _client_options.py; do not blindly pass with_project/group_guid into endpoints that already set those keywords. No client context setters or rio configuration access. Exact lookup honors continuation metadata, explicit selected organization/project headers, and expected identity; list order is not evidence of a unique match.

## Create/update outcomes

For create_or_update, try creation. Catch HttpAlreadyExistsError or UnauthorizedAccessError for the specified update fallback; surface other errors directly. Updates must succeed before reporting updated. For create_or_exists, conflict reports exists but denied creation remains failure. There is no implicit delete/recreate policy. Organization apply always updates its identified GUID; deletion and creation unsupported.

Response-only Secret/UserGroup resource instances may be used for inspection/delete. Apply preflight revalidates them as creation payloads; if creation-only credentials are absent, report invalid input before any write, rather than dropping credentials or attempting a partial create. Normal model construction/serialization outside Applier stays unchanged.

Project cache workflow: when caching is disabled, use normal create then update-on-conflict/denial and await applicable update provisioning. When caching is enabled, resolve an existing scoped project and update it; if absent, create a private base copy with caching disabled, then update the full requested features using the returned GUID. If a concurrent create conflicts, resolve and update. Created outcome means a create occurred; updated means only update occurred. Record each successful write before readiness or a later write fails.

RoleBinding grant workflow: resolve the exact grant by known GUID or filtered/paginated role/subject/domain lookup. Present grant yields exists; absent grant calls update_role_binding(BulkRoleBindingUpdate(new_bindings=[binding], old_bindings=[])) and yields created. Revoke finds the exact grant, sends old_bindings=[resolved_binding] and new_bindings=[], and yields deleted with a revoked step; missing grant yields absent. Lists use actual list[str] filters, not scalar strings. Match every supplied role/subject/domain selector; do not compare entire reference models because responses may contain additional names/GUIDs. Reconcile mixed name/GUID selectors using known aliases or exact lookup. Verify a grant fetched by metadata.guid against the requested tuple before revocation. list_role_bindings has no role-GUID filter: omit role_names for GUID-only role references, list within available subject/domain/scope selectors, and match the returned role GUID exactly. If responses expose only a role name, resolve its GUID through get_role/list_roles and compare it; do not assume name/GUID equivalence. Never revoke the first approximate match. Permission/error lookups propagate instead of pretending absence.

StaticRoute workflow: retain logical name for collection identity, use canonical response routing name when available, otherwise resolve the organization short GUID from ResourceScope or get_organization and perform an exact routing lookup. Avoid double suffixes. Creation sends the logical name, while updates/deletes use the resolved platform routing name. Offline preview does not resolve this name or assert existence. Verify the payload/routing behavior with controlled typed responses and a test-platform scenario when available.

## Readiness and deletion

| Resource/readiness requirement | Ready | Immediate terminal error |
| --- | --- | --- |
| Newly created Disk | Available, Released | Failed |
| Newly created Network | phase Succeeded | Stopped, FailedToStart, FailedToUpdate; explicit Error status; DEP_E153 provisioning error |
| Project update requiring provisioning | Success | Error |
| Deployment prerequisite with wait=true | Running | Error/Stopped status or FailedToStart/FailedToUpdate/Stopped phase |

Each readiness target has its own budget of at most configured polling rounds. A round includes required paginated lookup/read requests and status evaluation; additional pages do not consume separate rounds. The first round is immediate and no sleep follows the final unsuccessful round. A target that is ready drops out of further polling. Reject repeated continuation tokens rather than looping indefinitely. A missing object or absent status remains pending until exhausted. Required deployment references are individually verified by names or GUID filters, with failure phases left visible; an empty response is not readiness success. For every read, use effective scope and exact identity. Sync uses blocking waits; async uses awaitable sleeps.

Retention is exactly metadata.labels['rapyuta.io/deletionPolicy'] == 'retain'; absent/other string values allow deletion. Retained nodes receive no delete request. Non-retained missing resources yield absent. Reverse graph order ensures dependents precede prerequisites; failure prevents later prerequisite deletion. Platform rejection after retention of another resource remains visible to the caller.

## Compatibility verification

Exercise all 12 kinds in both modes; assert exact modeled client arguments, validated responses, aliases, unchanged caller objects/configuration, and documented unsupported operations. Resource conformance tests cover common mixin behavior and explicit overrides, declared capabilities, and typed client requests. They verify special cases do not depend on runtime introspection or inferred operation names. Include credential-bearing Docker secrets, explicit user-group memberships, two package versions, composite binding identity without metadata.name, pagination/ambiguous matches, StaticRoute suffixes, and cache bootstrap partial failures. Existing model-contract tests remain authoritative for wire behavior.
