"""Upload-link rules shared by the sync and async Run resources."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from zenture.errors import ZentureResponseError

UPLOAD_PATH_PREFIX = "/v1/run-artifacts/uploads/"
_UPLOAD_ID_RE = re.compile(r"^upload_[A-Za-z0-9_-]{8,128}$")
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_REFUSED = "Upload link was refused: it is not an https link on the client's API origin."


def validated_upload_url(upload_url: str, *, base_url: str) -> str:
    """Return the upload link only if it is safe to send the single-use token to.

    The link must sit on the client's own API origin (scheme, host, port) under
    /v1/run-artifacts/uploads/<upload_id>, be https (http only for a loopback origin
    that is itself the client's base URL), and carry no userinfo, query or fragment.
    The refusal text never includes the link or the token.
    """

    refusal: ZentureResponseError | None = None
    try:
        link = urlsplit(upload_url)
        base = urlsplit(base_url)
        host = link.hostname
        same_origin = (
            link.scheme == base.scheme
            and (host or "") == (base.hostname or "")
            and link.port == base.port
        )
        scheme_ok = link.scheme == "https" or (link.scheme == "http" and host in _LOCAL_HOSTS)
        plain = not (link.username or link.password or link.query or link.fragment)
        upload_id = link.path.removeprefix(UPLOAD_PATH_PREFIX)
        path_ok = link.path.startswith(UPLOAD_PATH_PREFIX) and bool(_UPLOAD_ID_RE.match(upload_id))
        if not (same_origin and scheme_ok and plain and path_ok and "\\" not in upload_url):
            refusal = ZentureResponseError(_REFUSED)
    except ValueError:
        refusal = ZentureResponseError(_REFUSED)
    if refusal is not None:
        raise refusal
    return upload_url
