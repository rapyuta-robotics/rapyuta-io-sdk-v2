# Copyright 2026 Rapyuta Robotics
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Offline canonical identity and dependency graph preparation."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import NoReturn

from rapyuta_io_sdk_v2.apply.errors import ApplierValidationError
from rapyuta_io_sdk_v2.models.applier import (
    DependencyGraph,
    DependencyReference,
    ResourceIdentity,
    ResourceReference,
    ResourceScope,
)

GraphNode = tuple[ResourceIdentity, Sequence[DependencyReference]]
_AliasKey = tuple[str, str | None, str | None, str | None, str, str]
_AliasTable = dict[_AliasKey, tuple[int, ...]]

_ORGANIZATION_SCOPED = frozenset(
    {"project", "usergroup", "role", "rolebinding", "serviceaccount"}
)
_PROJECT_SCOPED = frozenset(
    {"package", "deployment", "disk", "network", "staticroute", "secret"}
)


@dataclass(frozen=True, slots=True)
class ResolvedDependency:
    """One declared dependency with its offline resolution, if managed."""

    dependent: ResourceIdentity
    dependency: DependencyReference
    prerequisite: ResourceIdentity | None


@dataclass(frozen=True, slots=True)
class GraphPlan:
    """Canonical graph plus resolved declarations, including readiness flags."""

    dependency_graph: DependencyGraph
    dependencies: tuple[ResolvedDependency, ...]


def _raise_validation(
    message: str,
    category: str,
    identities: tuple[ResourceIdentity, ...] = (),
) -> NoReturn:
    """Raise the structured validation error through one diagnostic boundary."""
    error = ApplierValidationError(
        message,
        category=category,
        identities=identities,
    )
    raise error


def _scope_for_kind(scope: ResourceScope, kind: str) -> ResourceScope:
    """Keep only identifiers that participate in this kind's identity."""
    scoped_kinds = _ORGANIZATION_SCOPED | _PROJECT_SCOPED
    organization_guid = scope.organization_guid if kind in scoped_kinds else None
    project_guid = scope.project_guid if kind in _PROJECT_SCOPED else None
    return ResourceScope(
        organization_guid=organization_guid,
        project_guid=project_guid,
    )


def _canonical_identity(identity: ResourceIdentity) -> ResourceIdentity:
    """Discard routing and irrelevant scope from an offline identity."""
    updates: dict[str, object] = {
        "scope": _scope_for_kind(identity.scope, identity.kind)
    }
    if identity.kind == "rolebinding":
        updates.update(name=None, guid=None)
    return identity.model_copy(update=updates)


def _reference_key(
    reference: ResourceReference | None,
) -> tuple[str, str | None, str | None, str | None] | tuple[str]:
    """Return a structured reference identity without parsing display text."""
    if reference is None:
        return ("missing",)
    return (reference.kind, reference.name, reference.guid, reference.version)


def _identity_key(identity: ResourceIdentity) -> tuple[object, ...]:
    """Return a named resource's complete structured identity."""
    scope = identity.scope
    return (
        identity.kind,
        scope.organization_guid,
        scope.project_guid,
        identity.name,
        identity.version,
        identity.guid,
    )


def _exact_identity_key(identity: ResourceIdentity) -> tuple[object, ...]:
    """Return the full structured identity before alias reconciliation."""
    common = _identity_key(identity)
    if identity.kind != "rolebinding":
        return common
    return (
        *common,
        _reference_key(identity.role),
        _reference_key(identity.subject),
        _reference_key(identity.domain),
    )


def _alias_key(
    kind: str,
    scope: ResourceScope,
    *,
    version: str | None,
    selector: str,
    value: str,
) -> _AliasKey:
    return (kind, scope.organization_guid, scope.project_guid, version, selector, value)


def _register_alias(
    aliases: dict[_AliasKey, list[int]],
    index: int,
    identity: ResourceIdentity,
    *,
    selector: str,
    value: str,
) -> None:
    version = identity.version if identity.kind == "package" else None
    aliases[
        _alias_key(
            identity.kind,
            identity.scope,
            version=version,
            selector=selector,
            value=value,
        )
    ].append(index)


def _freeze_aliases(
    aliases: dict[_AliasKey, list[int]], identities: tuple[ResourceIdentity, ...]
) -> _AliasTable:
    frozen: _AliasTable = {}
    for alias, matches in aliases.items():
        if len(matches) > 1:
            message = (
                f"ambiguous local {alias[4]}={alias[5]} alias for {alias[0]} resources"
            )
            _raise_validation(
                message,
                "ambiguous_alias",
                tuple(identities[index] for index in matches),
            )
        frozen[alias] = tuple(matches)
    return frozen


def _alias_tables(
    identities: tuple[ResourceIdentity, ...],
) -> tuple[_AliasTable, _AliasTable]:
    """Index every known local name and GUID alias in effective scope."""
    names: dict[_AliasKey, list[int]] = defaultdict(list)
    guids: dict[_AliasKey, list[int]] = defaultdict(list)
    for index, identity in enumerate(identities):
        if identity.name is not None and identity.kind != "rolebinding":
            _register_alias(
                names, index, identity, selector="name", value=identity.name
            )
        if identity.guid is not None:
            _register_alias(
                guids, index, identity, selector="guid", value=identity.guid
            )
    return _freeze_aliases(names, identities), _freeze_aliases(guids, identities)


@dataclass(frozen=True, slots=True)
class _GraphIndex:
    identities: tuple[ResourceIdentity, ...]
    names: _AliasTable
    guids: _AliasTable
    routing_scope: ResourceScope

    @classmethod
    def create(
        cls, identities: tuple[ResourceIdentity, ...], scope: ResourceScope
    ) -> _GraphIndex:
        names, guids = _alias_tables(identities)
        return cls(identities=identities, names=names, guids=guids, routing_scope=scope)

    def resolve(
        self,
        reference: ResourceReference,
        dependent: ResourceIdentity,
    ) -> int | None:
        """Resolve one reference by the aliases that exist in its scope."""
        organization_guid = (
            dependent.scope.organization_guid or self.routing_scope.organization_guid
        )
        if dependent.kind == "organization":
            organization_guid = dependent.guid or organization_guid
        routing_scope = ResourceScope(
            organization_guid=organization_guid,
            project_guid=dependent.scope.project_guid
            or self.routing_scope.project_guid,
        )
        scope = _scope_for_kind(routing_scope, reference.kind)
        name_matches = self._matches(reference, scope, selector="name")
        guid_matches = self._matches(reference, scope, selector="guid")
        _reject_ambiguous_matches(
            reference,
            name_matches,
            guid_matches=guid_matches,
            identities=self.identities,
        )
        return _select_alias_match(
            reference,
            name_matches,
            guid_matches=guid_matches,
            identities=self.identities,
        )

    def _matches(
        self,
        reference: ResourceReference,
        scope: ResourceScope,
        *,
        selector: str,
    ) -> tuple[int, ...]:
        """Look up one selector against this index."""
        value = reference.name if selector == "name" else reference.guid
        if value is None or (selector == "name" and reference.kind == "rolebinding"):
            return ()
        version = reference.version if reference.kind == "package" else None
        key = _alias_key(
            reference.kind,
            scope,
            version=version,
            selector=selector,
            value=value,
        )
        aliases = self.names if selector == "name" else self.guids
        return aliases.get(key, ())


def _reject_ambiguous_matches(
    reference: ResourceReference,
    name_matches: tuple[int, ...],
    *,
    guid_matches: tuple[int, ...],
    identities: tuple[ResourceIdentity, ...],
) -> None:
    if len(name_matches) > 1 or len(guid_matches) > 1:
        matches = name_matches or guid_matches
        _raise_validation(
            f"ambiguous local reference for {reference.kind}",
            "ambiguous_reference",
            tuple(identities[index] for index in matches),
        )


def _selector_conflicts(
    reference: ResourceReference,
    identity: ResourceIdentity,
    *,
    selector: str,
) -> bool:
    known = identity.guid if selector == "guid" else identity.name
    requested = reference.guid if selector == "guid" else reference.name
    return requested is not None and known is not None and requested != known


def _select_alias_match(
    reference: ResourceReference,
    name_matches: tuple[int, ...],
    *,
    guid_matches: tuple[int, ...],
    identities: tuple[ResourceIdentity, ...],
) -> int | None:
    if name_matches and guid_matches:
        if name_matches[0] != guid_matches[0]:
            _raise_validation(
                f"conflicting name and GUID aliases for {reference.kind} reference",
                "conflicting_reference",
                (identities[name_matches[0]], identities[guid_matches[0]]),
            )
        return name_matches[0]
    return _select_one_alias(
        reference,
        name_matches,
        guid_matches=guid_matches,
        identities=identities,
    )


def _select_one_alias(
    reference: ResourceReference,
    name_matches: tuple[int, ...],
    *,
    guid_matches: tuple[int, ...],
    identities: tuple[ResourceIdentity, ...],
) -> int | None:
    # A shared nameOrGUID value is represented by equal selectors. In that
    # case the source model permits either alias, so a managed resource's
    # other identifier must not be treated as a contradictory assertion.
    alternative_selector = (
        reference.name is not None and reference.name == reference.guid
    )
    if name_matches:
        index = name_matches[0]
        if not alternative_selector and _selector_conflicts(
            reference, identities[index], selector="guid"
        ):
            _raise_validation(
                f"conflicting name and GUID aliases for {reference.kind} reference",
                "conflicting_reference",
                (identities[index],),
            )
        return index
    if guid_matches:
        index = guid_matches[0]
        if not alternative_selector and _selector_conflicts(
            reference, identities[index], selector="name"
        ):
            _raise_validation(
                f"conflicting name and GUID aliases for {reference.kind} reference",
                "conflicting_reference",
                (identities[index],),
            )
        return index
    return None


def _rolebinding_key(
    identity: ResourceIdentity, index: _GraphIndex
) -> tuple[object, ...]:
    references = (identity.role, identity.subject, identity.domain)
    return (
        *_identity_key(identity)[:3],
        *(_component_key(reference, identity, index) for reference in references),
    )


def _component_key(
    reference: ResourceReference | None,
    dependent: ResourceIdentity,
    index: _GraphIndex,
) -> tuple[object, ...]:
    if reference is None:
        return ("missing",)
    target_index = index.resolve(reference, dependent)
    if target_index is None:
        return ("external", *_reference_key(reference))
    return ("managed", *_identity_key(index.identities[target_index]))


def _validate_exact_duplicates(identities: tuple[ResourceIdentity, ...]) -> None:
    seen: dict[tuple[object, ...], int] = {}
    for index, identity in enumerate(identities):
        key = _exact_identity_key(identity)
        if key in seen:
            first = seen[key]
            _raise_validation(
                f"duplicate managed identity: {identity.kind}",
                "duplicate_identity",
                (identities[first], identity),
            )
        seen[key] = index


def _validate_rolebinding_duplicates(
    identities: tuple[ResourceIdentity, ...], index: _GraphIndex
) -> None:
    seen: dict[tuple[object, ...], int] = {}
    for position, identity in enumerate(identities):
        if identity.kind != "rolebinding":
            continue
        key = _rolebinding_key(identity, index)
        if key in seen:
            first = seen[key]
            _raise_validation(
                "duplicate managed identity: rolebinding",
                "duplicate_identity",
                (identities[first], identity),
            )
        seen[key] = position


def _visit_ready_nodes(
    ready: deque[int], outgoing: list[list[int]], indegree: list[int]
) -> int:
    visited = 0
    while ready:
        current = ready.popleft()
        visited += 1
        for following in outgoing[current]:
            indegree[following] -= 1
            if indegree[following] == 0:
                ready.append(following)
    return visited


def _check_cycles(
    identities: tuple[ResourceIdentity, ...], edges: tuple[tuple[int, int], ...]
) -> None:
    """Reject directed dependency cycles in prerequisite-to-dependent edges."""
    outgoing: list[list[int]] = [[] for _ in identities]
    indegree = [0] * len(identities)
    for prerequisite, dependent in edges:
        outgoing[prerequisite].append(dependent)
        indegree[dependent] += 1
    ready = deque(index for index, degree in enumerate(indegree) if degree == 0)
    if _visit_ready_nodes(ready, outgoing, indegree) != len(identities):
        cycle_members = tuple(
            identities[index] for index, degree in enumerate(indegree) if degree > 0
        )
        _raise_validation(
            "dependency graph contains a cycle",
            "dependency_cycle",
            cycle_members,
        )


@dataclass(slots=True)
class _GraphBuilder:
    identities: tuple[ResourceIdentity, ...]
    index: _GraphIndex
    edges: list[tuple[int, int]] = field(default_factory=list)
    seen_edges: set[tuple[int, int]] = field(default_factory=set)
    dependencies: list[ResolvedDependency] = field(default_factory=list)
    seen_dependencies: set[tuple[int, int | None, DependencyReference]] = field(
        default_factory=set
    )
    external: list[DependencyReference] = field(default_factory=list)
    seen_external: set[DependencyReference] = field(default_factory=set)

    def add(self, dependent_index: int, dependency: DependencyReference) -> None:
        dependent = self.identities[dependent_index]
        prerequisite_index = self.index.resolve(dependency.reference, dependent)
        prerequisite = self._identity_for(prerequisite_index)
        self._record_dependency(
            dependent_index,
            prerequisite_index,
            dependency=dependency,
            prerequisite=prerequisite,
        )
        if prerequisite_index is None:
            self._record_external(dependency)
            return
        if prerequisite_index == dependent_index:
            _raise_validation(
                f"resource {dependent.kind} depends on itself",
                "self_dependency",
                (dependent,),
            )
        self._record_edge(prerequisite_index, dependent_index)

    def _identity_for(self, index: int | None) -> ResourceIdentity | None:
        return self.identities[index] if index is not None else None

    def _record_dependency(
        self,
        dependent_index: int,
        prerequisite_index: int | None,
        *,
        dependency: DependencyReference,
        prerequisite: ResourceIdentity | None,
    ) -> None:
        key = (dependent_index, prerequisite_index, dependency)
        if key in self.seen_dependencies:
            return
        self.seen_dependencies.add(key)
        self.dependencies.append(
            ResolvedDependency(
                dependent=self.identities[dependent_index],
                dependency=dependency,
                prerequisite=prerequisite,
            )
        )

    def _record_external(self, dependency: DependencyReference) -> None:
        if dependency in self.seen_external:
            return
        self.seen_external.add(dependency)
        self.external.append(dependency)

    def _record_edge(self, prerequisite: int, dependent: int) -> None:
        edge = (prerequisite, dependent)
        if edge in self.seen_edges:
            return
        self.seen_edges.add(edge)
        self.edges.append(edge)

    def plan(self) -> GraphPlan:
        _check_cycles(self.identities, tuple(self.edges))
        graph = DependencyGraph(
            managed=self.identities,
            edges=tuple(
                (self.identities[before], self.identities[after])
                for before, after in self.edges
            ),
            external_references=tuple(self.external),
        )
        return GraphPlan(
            dependency_graph=graph,
            dependencies=tuple(self.dependencies),
        )


def _canonical_nodes(
    nodes: Sequence[GraphNode],
    scope: ResourceScope,
) -> tuple[tuple[ResourceIdentity, ...], _GraphIndex]:
    identities = tuple(_canonical_identity(identity) for identity, _ in nodes)
    _validate_exact_duplicates(identities)
    index = _GraphIndex.create(identities, scope)
    _validate_rolebinding_duplicates(identities, index)
    return identities, index


def _collect_dependencies(nodes: Sequence[GraphNode], builder: _GraphBuilder) -> None:
    for dependent_index, (_, dependencies) in enumerate(nodes):
        for dependency in dependencies:
            builder.add(dependent_index, dependency)


def prepare_dependency_graph(
    nodes: Sequence[GraphNode], *, scope: ResourceScope | None = None
) -> GraphPlan:
    """Prepare canonical dependencies from explicit typed identity records.

    This function is entirely offline. Nodes are the only resources eligible for
    mutation; unresolved references remain external metadata. Managed edges use
    prerequisite-to-dependent direction. ``GraphPlan.dependencies`` retains the
    declared readiness flag for managed edges, which ``DependencyGraph.edges``
    intentionally does not encode. ``scope`` retains the selected routing context
    for references whose scope is absent from the dependent's canonical identity.
    """
    identities, index = _canonical_nodes(nodes, scope or ResourceScope())
    builder = _GraphBuilder(identities=identities, index=index)
    _collect_dependencies(nodes, builder)
    return builder.plan()


def build_dependency_graph(
    nodes: Sequence[GraphNode], *, scope: ResourceScope | None = None
) -> DependencyGraph:
    """Return the public inspection graph for explicit identity/dependency pairs."""
    return prepare_dependency_graph(nodes, scope=scope).dependency_graph


__all__ = [
    "GraphNode",
    "GraphPlan",
    "ResolvedDependency",
    "build_dependency_graph",
    "prepare_dependency_graph",
]
