from __future__ import annotations

from html import unescape
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlparse, urlunparse


TRACKING_PARAM_EXACT = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "msclkid",
    "ref",
    "ref_src",
    "source",
}
TRACKING_PARAM_PREFIXES = ("utm_",)
WRAPPER_PARAMS = {"redirect", "target", "u", "url"}
TRAILING_PUNCTUATION = ").,;]}>\"'"


class UrlNormalizeError(ValueError):
    pass


def is_tracking_param(name: str) -> bool:
    lowered = name.lower()
    return lowered in TRACKING_PARAM_EXACT or any(lowered.startswith(prefix) for prefix in TRACKING_PARAM_PREFIXES)


def canonicalize_url(raw_url: str, *, max_unwraps: int = 3) -> str | None:
    if not isinstance(raw_url, str):
        return None
    current = _clean_raw_url(raw_url)
    seen: set[str] = set()
    for _ in range(max_unwraps + 1):
        if current in seen:
            return None
        seen.add(current)
        parsed = urlparse(current)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            return None
        wrapped = _wrapped_target(parsed)
        if not wrapped:
            return _normalize_parsed_url(parsed) or None
        current = wrapped
    return _normalize_parsed_url(urlparse(current)) or None


def canonicalize_or_raise(raw_url: str) -> str:
    canonical_url = canonicalize_url(raw_url)
    if not canonical_url:
        raise UrlNormalizeError(f"Unable to canonicalize URL: {raw_url!r}")
    return canonical_url


def _clean_raw_url(raw_url: str) -> str:
    cleaned = unescape(raw_url).strip()
    if cleaned.startswith("<") and cleaned.endswith(">"):
        cleaned = cleaned[1:-1].strip()
    return cleaned.rstrip(TRAILING_PUNCTUATION)


def _wrapped_target(parsed) -> str | None:
    for key, value in parse_qsl(parsed.query, keep_blank_values=False):
        if key.lower() not in WRAPPER_PARAMS:
            continue
        cleaned = _clean_raw_url(value)
        candidate = urlparse(cleaned)
        if candidate.scheme.lower() in {"http", "https"} and candidate.netloc:
            return cleaned
    return None


def _normalize_parsed_url(parsed) -> str:
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    try:
        port = parsed.port
    except ValueError:
        return ""
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    else:
        netloc = host
    path = quote(unquote(parsed.path or "/"), safe="/:@-._~!$&'()*+,;=")
    query_items = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if not key or is_tracking_param(key):
            continue
        query_items.append((key, value))
    query_items.sort(key=lambda item: (item[0].lower(), item[1]))
    return urlunparse(
        (
            scheme,
            netloc,
            path,
            "",
            urlencode(query_items, doseq=True),
            "",
        )
    )
