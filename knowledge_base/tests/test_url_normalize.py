#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from url_normalize import canonicalize_url, is_tracking_param  # noqa: E402


def main() -> int:
    cases = [
        (
            " HTTPS://Example.COM:443/path?utm_source=x&B=2&a=1#frag ",
            "https://example.com/path?a=1&B=2",
        ),
        (
            "http://Example.com:80",
            "http://example.com/",
        ),
        (
            "https://example.com/post?gclid=1&id=42&utm_campaign=x",
            "https://example.com/post?id=42",
        ),
        (
            "https://example.com/a).",
            "https://example.com/a",
        ),
        (
            "https://newsletter.example/click?url=https%3A%2F%2FTarget.com%2Fpost%3Futm_medium%3Dx%26p%3D9&token=abc",
            "https://target.com/post?p=9",
        ),
        (
            "<https://Example.com/path?ref=x&page=2>",
            "https://example.com/path?page=2",
        ),
    ]
    errors: list[str] = []
    for raw_url, expected in cases:
        actual = canonicalize_url(raw_url)
        if actual != expected:
            errors.append(f"{raw_url!r}: expected {expected!r}, got {actual!r}")

    if canonicalize_url("mailto:test@example.com") is not None:
        errors.append("mailto URL must be rejected.")
    if canonicalize_url("https://example.com:bad/path") is not None:
        errors.append("URL with invalid port must be rejected.")
    if not is_tracking_param("utm_reader") or not is_tracking_param("FBCLID"):
        errors.append("Known tracking params must be detected case-insensitively.")
    if is_tracking_param("page"):
        errors.append("Business query param page must not be treated as tracking.")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("PASS: URL normalization rules validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
