#!/usr/bin/env python3
"""Describe an image by calling a multimodal LLM via OpenAI-compatible API.

Env vars (custom names to avoid polluting standard vars):
    DESCRIBE_IMAGE_API_KEY    – API key (required)
    DESCRIBE_IMAGE_BASE_URL   – Base URL, e.g. https://api.openai.com/v1 (required)
    DESCRIBE_IMAGE_MODEL      – Model name, e.g. gpt-4o (required)
    DESCRIBE_IMAGE_THINKING   – Set to "1"/"true" to enable thinking mode (chain-of-thought)
    DESCRIBE_IMAGE_EXTRA_BODY – JSON string merged into request body, for provider-specific params
    DESCRIBE_IMAGE_TIMEOUT    – Request timeout in seconds (default: 120)

Usage:
    python3 describe-image.py --path /path/to/image.png
    python3 describe-image.py --url https://example.com/photo.jpg
    python3 describe-image.py --path img.png --prompt "Extract all data from this chart"
    python3 describe-image.py --path img.png --thinking
"""

import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def get_config():
    missing = []
    api_key = os.environ.get("DESCRIBE_IMAGE_API_KEY")
    base_url = os.environ.get("DESCRIBE_IMAGE_BASE_URL")
    model = os.environ.get("DESCRIBE_IMAGE_MODEL")

    if not api_key:
        missing.append("DESCRIBE_IMAGE_API_KEY")
    if not base_url:
        missing.append("DESCRIBE_IMAGE_BASE_URL")
    if not model:
        missing.append("DESCRIBE_IMAGE_MODEL")

    if missing:
        print(
            json.dumps(
                {
                    "error": "Missing environment variables",
                    "missing": missing,
                    "hint": "Set them before running, e.g.: export DESCRIBE_IMAGE_API_KEY=sk-...",
                }
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    assert api_key and base_url and model
    base_url = base_url.rstrip("/")
    timeout = int(os.environ.get("DESCRIBE_IMAGE_TIMEOUT", "120"))
    thinking = os.environ.get("DESCRIBE_IMAGE_THINKING", "").lower() in ("1", "true", "yes")
    extra_body = os.environ.get("DESCRIBE_IMAGE_EXTRA_BODY", "")
    return api_key, base_url, model, timeout, thinking, extra_body


def guess_mime(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    if mime and mime.startswith("image/"):
        return mime
    suffix = Path(path).suffix.lower()
    mapping = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".svg": "image/svg+xml",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }
    return mapping.get(suffix, "image/png")


def load_image_bytes(path: str) -> tuple[bytes, str]:
    p = Path(path)
    if not p.exists():
        print(json.dumps({"error": f"File not found: {path}"}), file=sys.stderr)
        sys.exit(1)
    mime = guess_mime(path)
    return p.read_bytes(), mime


def fetch_image_bytes(url: str) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "describe-image/1.0"})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
    except urllib.error.URLError as e:
        print(json.dumps({"error": f"Failed to fetch URL: {e.reason}"}), file=sys.stderr)
        sys.exit(1)
    content_type = resp.headers.get("Content-Type", "")
    if content_type and content_type.startswith("image/"):
        mime = content_type.split(";")[0].strip()
    else:
        mime = "image/png"
    return resp.read(), mime


def api_request(
    base_url: str,
    api_key: str,
    model: str,
    image_b64: str,
    mime: str,
    prompt: str,
    timeout: int,
    thinking: bool = False,
    extra_body: str = "",
) -> dict:
    body: dict = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    }

    if thinking:
        body["thinking"] = {"type": "enabled"}

    if extra_body:
        try:
            extra = json.loads(extra_body)
            body.update(extra)
        except json.JSONDecodeError:
            print(
                json.dumps({"error": f"DESCRIBE_IMAGE_EXTRA_BODY is not valid JSON: {extra_body[:200]}"}),
                file=sys.stderr,
            )
            sys.exit(1)

    data = json.dumps(body).encode("utf-8")
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        print(
            json.dumps({"error": f"API HTTP {e.code}", "detail": detail[:500]}),
            file=sys.stderr,
        )
        sys.exit(1)
    except urllib.error.URLError as e:
        print(json.dumps({"error": f"API request failed: {e.reason}"}), file=sys.stderr)
        sys.exit(1)

    return json.loads(resp.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Describe an image via multimodal LLM")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--path", help="Path to a local image file")
    source.add_argument("--url", help="URL of an image to fetch")
    parser.add_argument(
        "--prompt",
        default="Please describe this image in detail. Include all text, numbers, labels, structures, and visual elements visible in the image.",
        help="Custom prompt to send with the image",
    )
    parser.add_argument(
        "--thinking",
        action="store_true",
        help="Enable thinking/reasoning mode (sets thinking: {type: enabled})",
    )
    args = parser.parse_args()

    api_key, base_url, model, timeout, env_thinking, extra_body = get_config()

    use_thinking = args.thinking or env_thinking

    if args.path:
        img_bytes, mime = load_image_bytes(args.path)
    else:
        img_bytes, mime = fetch_image_bytes(args.url)

    image_b64 = base64.b64encode(img_bytes).decode("ascii")

    response = api_request(
        base_url, api_key, model, image_b64, mime, args.prompt, timeout, use_thinking, extra_body
    )

    try:
        choice = response["choices"][0]
        content = choice["message"]["content"]
    except (KeyError, IndexError, TypeError):
        print(json.dumps({"error": "Unexpected API response", "response": response}), file=sys.stderr)
        sys.exit(1)

    result: dict = {
        "description": content,
        "model": model,
    }

    # Capture thinking/reasoning content if the model returned it
    reasoning = choice["message"].get("reasoning_content")
    if reasoning:
        result["reasoning"] = reasoning

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
