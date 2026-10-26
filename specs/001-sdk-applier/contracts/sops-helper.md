# Contract: Optional SOPS Secret-File Helper

## Public signatures

Export from rapyuta_io_sdk_v2 and rapyuta_io_sdk_v2.apply:

```python
decrypt_secret_file(
    path: str | Path,
    *,
    options: SopsOptions | None = None,
) -> dict[str, JsonValue]

async async_decrypt_secret_file(
    path: str | Path,
    *,
    options: SopsOptions | None = None,
) -> dict[str, JsonValue]
```

JsonValue describes JSON-compatible nested scalar/list/mapping data. SopsOptions defines executable='sops' and termination_grace=1.0 seconds. The helper’s own diagnostic representations never contain decrypted content. Its returned mapping is ordinary caller data, and confidentiality guarantees do not extend to values injected into ManifestSource or subsequent Applier processing. The returned mapping can be supplied as ManifestSource(secrets=(values,)); Applier supplies it under the secrets template namespace.

## Invocation and dependencies

Callers install SOPS and configure its normal decryption credentials/environment. The SDK never installs SOPS, requests credentials interactively, changes platform context, or requires SOPS for callers using plain mappings/files.

Resolve the input into an absolute readable regular file and select input type yaml for .yaml/.yml or json for .json, case-insensitively. An unsupported extension is a source error. Pass the filename as one literal argument. Invoke the executable with decrypt, --input-type, the selected type, --output-type, json, and the absolute input filename. Do not use a shell, in-place mode, output-file mode, editor mode, or temporary plaintext file.

Capture stdout/stderr and wait for success before decoding JSON. Validate a single string-keyed mapping of JSON-compatible values; an empty mapping is valid, while null, arrays, scalar roots, malformed content, and nonzero exit are failures. Do not return partial stdout after failure. Encrypted source contents must remain unchanged; the helper must not deliberately alter its permissions, ownership, or location. Ordinary filesystem access-time updates from reading are outside this guarantee. Helper execution makes no platform requests.

Normal constructors, loading, inspection, apply, delete, and dry runs never invoke these helpers implicitly. Users explicitly call the helper before constructing their manifest source, including before an offline preview if needed.

## Async process lifecycle

Use create_subprocess_exec with captured pipes and communicate so pipe capacity cannot deadlock waiting. Keep ownership across cancellation during spawn. Once a process exists, cancellation must terminate it, wait the configured grace, kill if still running, and drain/reap it before returning. Repeated cancellation cannot abort cleanup and leave a running child; preserve and propagate cancellation once cleanup finishes. Handle a process that has already exited without treating cleanup races as new failures.

No threads or TaskGroup resource worker is needed for this separate utility; async process I/O is native awaitable subprocess I/O. Sync uses subprocess.run and returns after its child exits. Interruptions of the sync helper must also settle its direct child before propagating.

## Errors and confidential diagnostics

SopsDecryptionError exposes only source path, category, optional exit code, and generic corrective guidance:

| Category | Examples | Guidance |
| --- | --- | --- |
| unavailable | executable missing or not executable | Install/configure the command path |
| source | missing/unreadable file or unsupported extension | Correct the input file/path |
| decryption | command exits nonzero, including credential failure | Check local SOPS/key-provider setup |
| invalid_content | successful command returns malformed JSON or a non-mapping | Supply a valid YAML/JSON secret-values mapping |

Do not include stdout, stderr, decrypted excerpts, or exception chains that retain them in the helper’s own diagnostics. Catch and replace decoded-content errors without chaining. Do not classify every nonzero exit as missing credentials; return the decryption category and exit code. Async cancellation propagates asyncio.CancelledError after process cleanup.

## Acceptance validation

Use an isolated fake executable so automated tests require no real credentials. Cover both formats, empty mapping, invalid roots/content, unavailable command, nonzero exits containing secret-looking output, literal paths containing spaces/metacharacters or starting with '-', source immutability, no automatic helper use during preview, async responsiveness, cancellation during spawn/running/draining, repeated cancellation, and forced kill after grace. A real SOPS round trip with a locally configured non-production fixture can supplement these tests.
