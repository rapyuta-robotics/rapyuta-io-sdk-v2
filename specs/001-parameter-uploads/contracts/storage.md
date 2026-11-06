# Storage Contract: Parameter Binary Transfers

This adapter is private helper infrastructure, outside `Client` and `AsyncClient`. Only signed upload authorization supplied by a validated Parameter preparation result is used for storage requests. No platform token, project/organization header, platform cookie, or HTTP auth is sent.

## Metadata and integrity

Preparation carries `Checksum` as lowercase hexadecimal MD5, `X-Rapyuta-Params-Version` as decimal node version (helpers use `0`), MIME `Content-Type`, and optional `Content-Encoding`. Guess MIME/encoding as in SDK v1; exactly `application/json` and `text/yaml` are overridden to `application/octet-stream` for blobs. Unknown MIME is passed according to the reference and may be normalized by the platform; it does not change uploaded bytes.

Hash original file bytes incrementally with `hashlib.md5(usedforsecurity=False)`, for protocol compatibility. Record preflight and pre-transfer identity/size/mtime. Transfer a second pass and compare length and full hash before finalizing staged content and before Parameter confirmation. Storage MD5 headers use Base64 of raw MD5 bytes, not platform hex strings. Local integrity checks are not atomic source snapshots.

## Request protocol

Use `x-ms-version: 2021-12-02`, explicit `Content-Length`, and an isolated client with redirects disabled. Preserve all original SAS query bytes. For staged operations append percent-encoded `comp` and `blockid` parameters; never replace existing authorization parameters.

| File size | Storage operations |
| --- | --- |
| 0 through 4194304 bytes | One PUT of original bytes to the signed URL |
| 4194305 through 209715200000 bytes | Sequential PUT block operations of at most 4194304 bytes, then one PUT block-list operation |
| Above 209715200000 bytes | Local preflight error before Parameter mutations |

Single PUT headers: `x-ms-blob-type: BlockBlob`, `x-ms-blob-content-type`, `x-ms-blob-content-md5`, optional `x-ms-blob-content-encoding`, and explicit length. The empty file sends an empty body, length zero, and the checksum of empty bytes. A completed storage operation requires the documented HTTP 201 result; XML/body errors are surfaced as storage failures.

For staged PUTs, append `comp=block` and `blockid=<Base64 ID>`. IDs use a unique fixed-length per-attempt prefix and fixed-width index so IDs have equal encoded length and concurrent attempts do not accidentally reuse blocks. Send the block's `Content-MD5` and length. Hold at most one block's payload at a time; the list of IDs may grow up to 50000 entries.

After all blocks succeed and the second-pass checksum and source stat agree, append `comp=blocklist` and PUT an XML `BlockList` containing ordered `Latest` IDs. Supply `Content-Type: application/xml`, XML-body length, `x-ms-blob-content-type`, full-file `x-ms-blob-content-md5`, and optional `x-ms-blob-content-encoding`. The stored MD5 property does not validate concatenated data, so the second-pass local check is required. Do not send the file MD5 as the XML request's `Content-MD5`.

Protocol sources: [Put Blob](https://learn.microsoft.com/en-us/rest/api/storageservices/put-blob), [Put Block](https://learn.microsoft.com/en-us/rest/api/storageservices/put-block), and [Put Block List](https://learn.microsoft.com/en-us/rest/api/storageservices/put-block-list).

## Async and resource ownership

Await HTTPX network operations. Obtain bounded byte chunks with offloaded local disk workers; a worker owns and closes its file handle. If a stream is used, supply an async iterator to AsyncClient rather than a synchronous file iterator. Never run synchronous network operations through thread offloading.

The helper creates one isolated storage client per submission when none is injected and closes it in a context/finally path. Injected storage clients remain open. Disk cancellation cannot forcibly stop an already running thread; workers must own cleanup and must never share a file handle that the cancelling task closes concurrently. No background transfer may trigger a later platform completion after cancellation.

## Failure ordering and limits

- Failed preparation: no storage request.
- Failed or interrupted storage request, checksum mismatch, source change, or failed block-list commit: no Parameter completion call.
- Successful storage completion followed by failed Parameter completion: file remains incomplete in the result unless public blob-list verification proves the exact reference Uploaded.
- Network timeouts/status errors fail immediately. Retries, expired-URL renewal, stale-block cleanup, and resume are outside scope.
- Unique block IDs limit accidental overlap; they do not guarantee isolation from concurrent external writers to the same blob. Live multi-writer atomicity is not claimed.

Use `httpx.MockTransport` to verify preserved query authorization, exact bytes and lengths, checksums, block order, empty files, injected-client ownership, and no platform headers. Require the separate network-isolated reference downloader round-trip defined in `contracts/sdk.md` and `quickstart.md` to prove fixture interoperability; transport mocks alone do not satisfy that gate. Optional live verification adds deployed-service evidence and is reported separately.
