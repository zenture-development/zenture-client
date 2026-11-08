# Migrating to the canonical zenture client

The canonical distribution and Python import package are both `zenture`.
The previous published distribution is `zenture-sdk`; it also owns the
`zenture` import package. Never install both distributions in the same Python
environment: uninstall one before installing the other.

This is a hard cutover. The canonical REST classes are `ZentureClient` and
`AsyncZentureClient`; there are no `Zenture` / `AsyncZenture` aliases or new
compatibility distributions. The default install includes REST, hosted MCP,
native authentication, and the `zenture` command. It provides no local MCP
server. Backend/Engine remain the authorization, execution, billing, and
tenant authorities.

## Upgrade in one virtual environment

Use a user-owned virtual environment for this application and keep the same
interpreter for every install and uninstall. For example, with Python 3.11
on a POSIX shell:

```bash
python3 -m venv .venv-zenture
.venv-zenture/bin/python -m pip uninstall -y zenture-sdk
.venv-zenture/bin/python -m pip install --upgrade zenture==1.2.0
```

For an existing virtual environment containing `zenture-sdk`, skip creation
and substitute its Python executable in both commands. On Windows, the
executable inside the environment is `Scripts/python.exe` instead of
`bin/python`. The `--upgrade` flag also updates an existing canonical
`zenture` installation, including 1.1.0, to 1.2.0. If you come from a canonical
1.x release, read [Upgrading to 1.2.0](#upgrading-to-120) first.

Update your application imports and class references together:

```diff
-from zenture import AsyncZenture, Zenture
+from zenture import AsyncZentureClient, ZentureClient
```

The existing REST API-token contract is unchanged. Keep using an externally
provided `ZENTURE_API_KEY` with the canonical REST clients. API-token access
remains noninteractive; MCP login does not read that token. MCP uses separate
account OAuth credentials and explicit login; ordinary client calls never
start login. See [authentication](./authentication.md) and
[hosted MCP clients](./mcp-client.md) for those public interfaces.

## Upgrading to 1.2.0

Release 1.2.0 changes the file upload flow and removes two public methods. Run, MCP and
error handling for text Runs are unchanged. Only code that uploads a file or reads the
removed types needs edits.

| 1.1.x | 1.2.0 |
|---|---|
| `up = client.runs.signed_upload(file_name=..., mime_type=..., byte_size=..., content_hash=..., idempotency_key=...)` | Removed. `attach_artifact` issues the upload link itself. |
| `client.runs.attach_artifact(upload_id=up.upload_id, file_name=..., mime_type=..., content=..., content_hash=..., idempotency_key=...)` returned `ArtifactUploadResponse` | `client.runs.attach_artifact(file_name=..., mime_type=..., content=..., content_hash=..., idempotency_key=...)` (no `upload_id`) returns `ArtifactUploadAccepted` with `artifact_ref`, `status="pending"`, `retry_after_seconds`, `next_step`. |
| `SignedUploadResponse` in `zenture.types` | Removed. |
| bearer `POST /v1/run-artifacts` | Removed. The bytes go with `PUT` to the issued link and the single-use `X-Upload-Token` (no bearer, no redirects, never retried). |
| `McpClient.attach_artifact(...)` returned the old `ArtifactUploadResponse` | Returns an upload link (`upload_url`, `upload_id`, `upload_token` hidden in repr, `expires_at`) or a registered host file; it sends no bytes. |

Before:

```python
up = client.runs.signed_upload(
    file_name=name, mime_type=mime, byte_size=size, content_hash=digest, idempotency_key=key
)
done = client.runs.attach_artifact(
    upload_id=up.upload_id,
    file_name=name,
    mime_type=mime,
    content=data,
    content_hash=digest,
    idempotency_key=key,
)
```

After:

```python
accepted = client.runs.attach_artifact(
    file_name=name, mime_type=mime, content=data, content_hash=digest, idempotency_key=key
)
run = client.runs.run(
    task=task,
    artifact={"type": "zenture_ref", "value": accepted.artifact_ref},
    idempotency_key=run_key,
)
```

The file is read asynchronously. Starting a Run before that finishes raises
`ZentureArtifactNotReadyError` (HTTP 409) with `retry_after_seconds`: wait and send the
same request again. New closed errors you may want to handle:
`ZentureArtifactTooLargeError`, `ZentureArtifactTypeUnsupportedError`,
`ZentureArtifactExtractFailedError`, `ZentureArtifactNotFoundError`,
`ZentureArtifactQuotaExceededError` and `ZentureLengthRequiredError`.

New in 1.2.0: source checks. `runs.prepare(...)`, `runs.run(...)` and the MCP `run` take an
optional `reference_file` (an `art_...` reference from an upload). The inline text answer
is then checked against that file; the result carries `reference_file_attached=True` and
locations with `source="reference_file"`. See the [Run guide](./run-guide.md).

## Return to the published baseline

Use the same application virtual environment, uninstall the canonical
distribution, and reinstall the exact historical published version:

```bash
.venv-zenture/bin/python -m pip uninstall -y zenture
.venv-zenture/bin/python -m pip install zenture-sdk==1.0.0rc3
```

Restore the application imports and constructor names to the legacy form.
This inverse diff targets the historical published baseline, not the canonical
client:

```diff
-from zenture import AsyncZentureClient, ZentureClient
+from zenture import AsyncZenture, Zenture
```

`zenture-sdk==1.0.0rc3` is a retained historical baseline. It is not overwritten,
an alias, or a separate fallback product. Returning to it restores that
artifact's legacy client surface; it does not supply the canonical client's
new native OAuth, CLI, or Run functionality. The return path does not establish
compatibility with current services. Review the baseline's actual capabilities
before relying on it for your application.

## Configuration and credentials

If you reuse application configuration, keep credentials external to source
and opaque: do not inspect, print, copy into code, or log their values. Preserve
the separation between REST API tokens and MCP account authorization.

Package uninstall neither revokes server Connections nor promises credential
cleanup. Local credential removal and server revocation are separate actions:
`zenture auth clear` removes only the local record, while revocation happens
in the webapp under *Zugriff & Sicherheit -> Verbindungen*. Follow the existing
[status and removal guidance](./authentication.md#status-and-removal)
separately when needed; perform any canonical CLI cleanup before uninstalling
the package that provides it.

## What has been verified

An offline artifact rehearsal installed published `zenture-sdk==1.0.0rc3`,
uninstalled it, installed the canonical candidate, then uninstalled the
candidate and returned to the published baseline in one isolated virtual
environment. It checked the distribution and class names at each stage and
the absence of the other distribution and incompatible class exports. The
historical and candidate artifact hashes remained unchanged.

That rehearsal covered macOS with Python 3.11 and reused existing dependencies.
It did not prove clean dependency installation, the full Python or three-OS
matrix, native authentication, service compatibility, or public publication.
Those release gates remain separate; the rehearsal is package transition
proof only.
