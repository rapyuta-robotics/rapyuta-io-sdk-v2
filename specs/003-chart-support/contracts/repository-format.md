# Repository and Package Compatibility Contract

The reference is `~/Projects/Work/rapyuta-io-cli/riocli/chart/` at revision `27bb77bb912705b58a5de0a2e99848dc023ba322`. Ordinary SDK use never imports it. Fixed URLs are intentionally constants under the user's clarification.

## Index Selection and Branch Construction

| Input | Selected index |
| --- | --- |
| Non-empty branch | Branch-specific URL, regardless of repository override. |
| No/empty branch and non-empty override | Explicit absolute HTTP(S) index URL. |
| No/empty branch and no/empty override | `https://rapyuta-robotics.github.io/rapyuta-charts/incubator/index.yaml`. |

Branch URL is `https://chartsbranch.blob.core.windows.net/charts-per-branch/` plus the branch quoted as a URL path with slash preserved, then `/incubator/index.yaml`. Match `quote(branch, safe="/")` exactly; do not strip the branch, turn spaces into `+`, encode `/`, normalize Unicode, or interpret `?` as a query. An empty branch is ignored by source selection; the pure construction function remains the CLI-equivalent formatter even for an empty string.

| Branch input | Path between base and `/incubator/index.yaml` |
| --- | --- |
| `feature-x` | `feature-x` |
| `bug/fix some` | `bug/fix%20some` |
| `feat?oops` | `feat%3Foops` |
| `bran©h@!` | `bran%C2%A9h%40%21` |

Use the same selected index for repository fetch/list/find and Chart loading. No implicit standard-index fallback is permitted. A loaded branch chart keeps its selected contents for apply/delete/inspection; no later operation re-resolves its source.

## Index Shape and Catalog Decisions

Safe YAML mapping with required `entries` mapping, chart-name keys, and ordered entry sequences. Entries contain non-empty string name/version and preserve optional metadata, created timestamp, digest, and ordered package URLs. Typed models are defined in [data-model.md](../data-model.md). Invalid structures or mismatched key/name pairs are index errors; empty catalog mappings return an empty listing.

- `find_chart("name")` returns all entries for that exact name, preserving index order.
- `find_chart("name:version")` returns a one-element tuple containing the first exact version match. Multiple matching version entries are not reordered or treated as ambiguous.
- Missing name or version produces an identifiable lookup error, including index source and selector.
- Loading chooses the first returned entry. Several unversioned matches emit a non-fatal `ChartVersionWarning` and still load the first. Do not infer a latest version from metadata.
- Listing flattens entries in mapping/sequence order, then stably sorts by `entry.name.lower()`, as the CLI does; same-name entries keep their initial relative order.
- CLI search/info correspondence is entry selection and returned metadata, not terminal rendering. Timestamp comparisons use equivalent typed values/JSON serialization; other names, versions, URLs, and metadata retain their values and types.

## Package Retrieval

Select only the first advertised URL. Missing/empty/unusable first location is a download-stage error; later URLs are not tried. Relative URL resolution is not introduced. Index and package requests support redirects, check successful HTTP status, and map HTTPX network/timeout errors to chart load stage/category while retaining request source. Chart transport errors do not contain raw response bodies. No retries, digest enforcement, persistent cache, or automatic alternative-repository selection are added.

One owned HTTPX transport may serve both requests during a Chart load, then closes before returning. A supplied compatible acquisition client remains open and is never mutated. Its timeout/authentication/proxy policy is caller-controlled. Platform clients and authentication are never used for acquisition.

## Chart Layout and Discovery

Local directory root or the single identified archive root:

```text
chart-root/
├── Chart.yaml             # One metadata mapping, non-empty name/version
├── values.yaml            # Default values input when explicit inputs are absent
└── templates/
    ├── resource.yaml
    └── nested/resource.yml
```

The archive may contain this layout at its root or under one top-level chart directory. Multiple identifiable roots, mixed ambiguous chart layouts, missing metadata/templates, and zero supported template files are rejected. Metadata name/version must match selected repository entry identity. Arbitrary documentation/assets may accompany an unambiguous chart but are not rendered outside `templates/`.

Discover ordinary `.yaml`, `.yml`, and `.json` files recursively under `templates/`, accepting extensions with the same case handling as Applier. Exclude hidden files and hidden path components as the CLI directory glob does. Sort their chart-relative POSIX paths and preserve the Applier's document order and empty-document handling. Do not render metadata or defaults outside `templates/`. Zero supported files is invalid; selected files rendering to zero resources follow existing successful empty-collection behavior.

Bundled `values.yaml` is read only when the normalized explicit values sequence is empty. With explicit values, a missing or malformed unused defaults file is irrelevant. A missing needed defaults file is a source-attributed preparation error. Default contents and explicit contents retain existing plain YAML/JSON mapping requirements and ordered merge behavior. No namespace wrapping or Helm values conventions are added.

## Root Confinement and Cleanup

Before extracting any member, validate the complete archive inventory. Permit ordinary files/directories only; reject symlinks, hard links, devices, FIFOs, absolute paths, parent-traversal components, foreign separators, duplicate normalized destination paths, and file/directory collisions. Apply the explicit tar `data` filter as an additional boundary and abort on rejected members; no invalid entry is silently skipped.

Extract only into a fresh owned temporary directory, never caller-owned source paths. For local sources, validate selected descendants/ancestors before reading and reject symlinks or special files under the selected root. Explicit caller values/secrets sources remain separately authorized input and need not lie under that root. Concurrent adversarial replacement of caller-owned local files is outside this scope; callers provide stable local inputs for a load.

Construct the prepared Applier before releasing extracted files. Preserve original chart selection, relative template paths, and private staging-path attribution for diagnostics. Temp cleanup runs on success, failure, and cancellation; async cleanup starts only after extraction/rendering workers settle. There are no owned artifacts left when load returns or raises. Prepared execution does not reread package files.

## Failure Compatibility

Preserve CLI decisions for successful input while providing SDK source/stage errors for absent names/versions, malformed indexes, bad packages, missing metadata, identity mismatch, unsafe members, and failed requests. Do not reproduce CLI unhandled exceptions, unsafe extraction, credential discovery, or terminal confirmation flows. Existing Apply validation/execution errors retain their type and data; chart origin notes supplement source paths for temporary packages.
