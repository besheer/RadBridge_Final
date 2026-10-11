"""Secure OCR provider adapters and validation for RadBridge.

This module deliberately has no Flask or database dependency.  It can be unit
tested in isolation and reused by the web process or a future OCR worker.

Patient-safety rules:
* Configuration tests use an internally generated, non-PHI image.
* Secrets are resolved by environment-variable name and are never returned.
* Provider errors are normalized and scrubbed before reaching the UI or logs.
* Remote destinations are restricted by an explicit hostname allow-list.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlparse

import requests


SUPPORTED_PROVIDERS = (
    "GENERIC_OCR_REST",
    "GOOGLE_VISION",
    "GEMINI",
)

DEFAULT_BASE_URLS = {
    "GENERIC_OCR_REST": "http://radbridge-ocr:7400",
    "GOOGLE_VISION": "https://vision.googleapis.com/v1",
    "GEMINI": "https://generativelanguage.googleapis.com/v1beta",
}

DEFAULT_ALLOWED_HOSTS = (
    "radbridge-ocr",
    "localhost",
    "127.0.0.1",
    "vision.googleapis.com",
    "generativelanguage.googleapis.com",
)

ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]{2,119}$")
MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9._:/-]{2,180}$")
GOOGLE_KEY_RE = re.compile(r"AIza[0-9A-Za-z_-]{20,}")
BEARER_RE = re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/-]{8,}")


@dataclass(frozen=True)
class OCRConfig:
    enabled: bool
    provider_key: str
    base_url: str
    model_name: str
    timeout_seconds: int
    secret_env_name: str


class OCRProviderError(RuntimeError):
    def __init__(self, code: str, message: str, *, field: str = "provider", http_status: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field
        self.http_status = http_status


def _source_value(source: Any, name: str, default: Any = "") -> Any:
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


def normalize_config(source: Any) -> OCRConfig:
    provider = str(_source_value(source, "provider_key", "GENERIC_OCR_REST") or "GENERIC_OCR_REST").strip().upper()
    try:
        timeout = int(_source_value(source, "timeout_seconds", 60) or 60)
    except (TypeError, ValueError):
        timeout = -1
    enabled_value = _source_value(source, "enabled", False)
    if isinstance(enabled_value, str):
        enabled = enabled_value.strip().lower() in {"1", "true", "yes", "on"}
    else:
        enabled = bool(enabled_value)
    return OCRConfig(
        enabled=enabled,
        provider_key=provider,
        base_url=str(_source_value(source, "base_url", "") or "").strip(),
        model_name=str(_source_value(source, "model_name", "") or "").strip(),
        timeout_seconds=timeout,
        secret_env_name=str(_source_value(source, "secret_env_name", "RIS_OCR_API_KEY") or "RIS_OCR_API_KEY").strip(),
    )


def public_config(config: Any) -> dict[str, Any]:
    cfg = normalize_config(config)
    return {
        "enabled": cfg.enabled,
        "provider_key": cfg.provider_key,
        "base_url": cfg.base_url,
        "model_name": cfg.model_name,
        "timeout_seconds": cfg.timeout_seconds,
        "secret_env_name": cfg.secret_env_name,
    }


def configuration_hash(config: Any) -> str:
    payload = json.dumps(public_config(config), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _field(status: str, message: str, code: str = "") -> dict[str, str]:
    return {"status": status, "message": message, "code": code}


def _allowed_hosts(environ: Mapping[str, str]) -> tuple[str, ...]:
    raw = str(environ.get("RIS_OCR_ALLOWED_HOSTS", "") or "").strip()
    if not raw:
        return DEFAULT_ALLOWED_HOSTS
    return tuple(x.strip().lower() for x in raw.split(",") if x.strip())


def _host_allowed(hostname: str, allowed: tuple[str, ...]) -> bool:
    host = (hostname or "").strip().lower().rstrip(".")
    for entry in allowed:
        item = entry.strip().lower().rstrip(".")
        if not item:
            continue
        if item.startswith(".") and host.endswith(item):
            return True
        if host == item:
            return True
    return False


def validate_local(config: Any, environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    cfg = normalize_config(config)
    fields: dict[str, dict[str, str]] = {}

    if cfg.enabled:
        fields["enabled"] = _field("valid", "OCR is enabled. Full readiness still requires all checks.")
    else:
        fields["enabled"] = _field("warning", "OCR is disabled. Documents remain available for manual review.", "OCR_DISABLED")

    if cfg.provider_key in SUPPORTED_PROVIDERS:
        fields["provider_key"] = _field("valid", f"Supported adapter: {cfg.provider_key}.")
    else:
        fields["provider_key"] = _field("invalid", "Select a supported OCR provider.", "UNSUPPORTED_PROVIDER")

    parsed = urlparse(cfg.base_url)
    hostname = (parsed.hostname or "").lower()
    if not cfg.base_url:
        fields["base_url"] = _field("invalid", "Base URL is required.", "BASE_URL_REQUIRED")
    elif parsed.scheme not in {"http", "https"} or not hostname:
        fields["base_url"] = _field("invalid", "Enter a complete HTTP or HTTPS URL.", "BASE_URL_INVALID")
    elif parsed.username or parsed.password or parsed.query or parsed.fragment:
        fields["base_url"] = _field(
            "invalid",
            "Base URL must not contain credentials, a query string, or a fragment.",
            "BASE_URL_COMPONENTS_INVALID",
        )
    elif not _host_allowed(hostname, _allowed_hosts(env)):
        fields["base_url"] = _field("invalid", "Host is not in RIS_OCR_ALLOWED_HOSTS.", "BASE_URL_NOT_ALLOWED")
    elif cfg.provider_key in {"GOOGLE_VISION", "GEMINI"} and parsed.scheme != "https":
        fields["base_url"] = _field("invalid", "Google providers require HTTPS.", "HTTPS_REQUIRED")
    elif cfg.provider_key == "GOOGLE_VISION" and hostname != "vision.googleapis.com":
        fields["base_url"] = _field("invalid", "Google Vision must use vision.googleapis.com.", "VISION_HOST_INVALID")
    elif cfg.provider_key == "GEMINI" and hostname != "generativelanguage.googleapis.com":
        fields["base_url"] = _field("invalid", "Gemini must use generativelanguage.googleapis.com.", "GEMINI_HOST_INVALID")
    elif parsed.scheme == "http" and hostname not in {"localhost", "127.0.0.1", "radbridge-ocr"}:
        fields["base_url"] = _field("warning", "Unencrypted HTTP is allowed only for a trusted private OCR gateway.", "INSECURE_HTTP")
    else:
        fields["base_url"] = _field("valid", "URL syntax and destination allow-list are valid.")

    if cfg.provider_key == "GOOGLE_VISION":
        fields["model_name"] = _field("na", "Google Vision uses DOCUMENT_TEXT_DETECTION; no model name is required.")
    elif cfg.provider_key == "GEMINI":
        if not cfg.model_name:
            fields["model_name"] = _field("invalid", "A Gemini model name is required.", "MODEL_REQUIRED")
        elif not MODEL_NAME_RE.fullmatch(cfg.model_name):
            fields["model_name"] = _field("invalid", "Model name contains unsupported characters.", "MODEL_INVALID")
        else:
            fields["model_name"] = _field("valid", "Model name syntax is valid; access is checked remotely.")
    elif cfg.model_name and not MODEL_NAME_RE.fullmatch(cfg.model_name):
        fields["model_name"] = _field("invalid", "Model name contains unsupported characters.", "MODEL_INVALID")
    elif cfg.model_name:
        fields["model_name"] = _field("valid", "Model name will be forwarded to the generic OCR gateway.")
    else:
        fields["model_name"] = _field("warning", "No model is selected; the generic gateway default will be used.", "MODEL_DEFAULT")

    if 5 <= cfg.timeout_seconds <= 120:
        if cfg.timeout_seconds > 90:
            fields["timeout_seconds"] = _field("warning", "Valid, but a value above 90 seconds may delay staff workflows.", "HIGH_TIMEOUT")
        else:
            fields["timeout_seconds"] = _field("valid", "Timeout is within the supported range.")
    else:
        fields["timeout_seconds"] = _field("invalid", "Timeout must be between 5 and 120 seconds.", "TIMEOUT_INVALID")

    if not ENV_NAME_RE.fullmatch(cfg.secret_env_name):
        fields["secret_env_name"] = _field(
            "invalid",
            "Enter an environment-variable name such as RIS_OCR_API_KEY, never the secret value.",
            "SECRET_ENV_NAME_INVALID",
        )
    elif str(env.get(cfg.secret_env_name, "") or ""):
        fields["secret_env_name"] = _field("valid", "Secret environment variable is configured; its value is hidden.")
    else:
        fields["secret_env_name"] = _field("invalid", "Environment variable is not present in the running process.", "SECRET_NOT_CONFIGURED")

    invalid = any(item["status"] == "invalid" for item in fields.values())
    warning = any(item["status"] == "warning" for item in fields.values())
    if not cfg.enabled:
        overall = "DISABLED" if not invalid else "INVALID"
    elif invalid:
        overall = "INVALID"
    elif warning:
        overall = "LOCAL_VALID_WITH_WARNINGS"
    else:
        overall = "LOCAL_VALID"

    return {
        "ok": not invalid,
        "overall": overall,
        "fields": fields,
        "config_hash": configuration_hash(cfg),
        "remote_checked": False,
        "latency_ms": None,
    }


def _safe_message(value: Any, secret: str = "") -> str:
    text = str(value or "")
    if secret:
        text = text.replace(secret, "[REDACTED]")
    text = GOOGLE_KEY_RE.sub("[REDACTED_GOOGLE_KEY]", text)
    text = BEARER_RE.sub(r"\1[REDACTED]", text)
    return re.sub(r"[\r\n\t]+", " ", text).strip()[:300]


def _provider_error_from_response(response: requests.Response, secret: str = "") -> OCRProviderError:
    status = int(response.status_code or 500)
    detail = ""
    try:
        payload = response.json()
        err = payload.get("error", payload) if isinstance(payload, dict) else payload
        if isinstance(err, dict):
            detail = err.get("message") or err.get("status") or ""
        else:
            detail = str(err or "")
    except Exception:
        detail = response.text or ""
    detail = _safe_message(detail, secret)

    if status == 400:
        return OCRProviderError("PROVIDER_REQUEST_INVALID", detail or "Provider rejected the request.", field="provider", http_status=400)
    if status == 401:
        return OCRProviderError("AUTH_INVALID", "Provider rejected the configured credential.", field="secret_env_name", http_status=401)
    if status == 403:
        return OCRProviderError("API_DISABLED_OR_FORBIDDEN", detail or "API access is disabled or forbidden.", field="secret_env_name", http_status=403)
    if status == 404:
        return OCRProviderError("MODEL_OR_ENDPOINT_NOT_FOUND", detail or "Endpoint or model was not found.", field="model_name", http_status=404)
    if status == 429:
        return OCRProviderError("QUOTA_EXCEEDED", "Provider quota or billing limit was reached.", field="provider", http_status=429)
    if status >= 500:
        return OCRProviderError("PROVIDER_UNAVAILABLE", "Provider returned a temporary server error.", field="provider", http_status=503)
    return OCRProviderError("PROVIDER_HTTP_ERROR", detail or f"Provider returned HTTP {status}.", field="provider", http_status=502)


def _request(session: requests.Session, method: str, url: str, *, timeout: int, secret: str, **kwargs: Any) -> requests.Response:
    try:
        response = session.request(method, url, timeout=timeout, **kwargs)
    except requests.Timeout as exc:
        raise OCRProviderError("PROVIDER_TIMEOUT", "Provider did not respond before the configured timeout.", field="timeout_seconds", http_status=504) from exc
    except requests.SSLError as exc:
        raise OCRProviderError("TLS_ERROR", "TLS certificate validation failed.", field="base_url", http_status=502) from exc
    except requests.ConnectionError as exc:
        raise OCRProviderError("PROVIDER_UNREACHABLE", "Provider could not be reached from the RIS container.", field="base_url", http_status=502) from exc
    except requests.RequestException as exc:
        raise OCRProviderError("PROVIDER_REQUEST_FAILED", _safe_message(exc, secret) or "Provider request failed.", field="provider", http_status=502) from exc
    if not response.ok:
        raise _provider_error_from_response(response, secret)
    return response


def _sample_image() -> tuple[bytes, str, str]:
    """Return a deterministic OCR smoke-test image with no patient information."""
    try:
        from PIL import Image, ImageDraw, ImageFont

        image = Image.new("RGB", (900, 260), "white")
        draw = ImageDraw.Draw(image)
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        try:
            font = ImageFont.truetype(font_path, 44)
            small = ImageFont.truetype(font_path, 30)
        except OSError:
            font = ImageFont.load_default()
            small = font
        draw.text((36, 35), "RADBRIDGE OCR TEST 2026", fill="black", font=font)
        draw.text((36, 115), "PATIENT SAFETY SAMPLE - NO PHI", fill="black", font=small)
        draw.text((36, 175), "REFERENCE 0123456789", fill="black", font=small)
        stream = io.BytesIO()
        image.save(stream, format="PNG", optimize=True)
        return stream.getvalue(), "radbridge-ocr-test.png", "image/png"
    except Exception:
        # Valid 1x1 PNG fallback. Connection/authentication still work, while
        # OCR text assertion will correctly report that the test is incomplete.
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        return png, "radbridge-ocr-test.png", "image/png"


def _confidence_from_vision(payload: dict[str, Any], text: str) -> float:
    values: list[float] = []
    annotation = payload.get("fullTextAnnotation") or {}
    for page in annotation.get("pages") or []:
        for block in page.get("blocks") or []:
            for paragraph in block.get("paragraphs") or []:
                for word in paragraph.get("words") or []:
                    value = word.get("confidence")
                    if isinstance(value, (int, float)):
                        values.append(float(value))
    if values:
        return max(0.0, min(1.0, sum(values) / len(values)))
    return 0.80 if text.strip() else 0.0


def _generic_extract(
    cfg: OCRConfig,
    secret: str,
    content: bytes,
    original_name: str,
    mime_type: str,
    document_type: str,
    session: requests.Session,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {secret}"} if secret else {}
    files = {"file": (original_name, io.BytesIO(content), mime_type or "application/octet-stream")}
    data = {"model": cfg.model_name, "document_type": document_type}
    response = _request(
        session,
        "POST",
        cfg.base_url.rstrip("/") + "/extract",
        timeout=cfg.timeout_seconds,
        secret=secret,
        files=files,
        data=data,
        headers=headers,
    )
    try:
        payload = response.json()
    except ValueError as exc:
        raise OCRProviderError("INVALID_OUTPUT", "OCR gateway did not return JSON.", field="provider") from exc
    text = str(payload.get("text") or "")
    fields = payload.get("fields") or {}
    if not isinstance(fields, dict):
        raise OCRProviderError("INVALID_OUTPUT", "OCR fields must be a JSON object.", field="provider")
    try:
        confidence = float(payload.get("confidence") or 0)
    except (TypeError, ValueError) as exc:
        raise OCRProviderError("INVALID_OUTPUT", "OCR confidence must be numeric.", field="provider") from exc
    return {"text": text, "fields": fields, "confidence": max(0.0, min(1.0, confidence))}


def _google_vision_extract(
    cfg: OCRConfig,
    secret: str,
    content: bytes,
    mime_type: str,
    session: requests.Session,
) -> dict[str, Any]:
    if mime_type and mime_type not in {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/tiff", "image/bmp"}:
        raise OCRProviderError(
            "UNSUPPORTED_MIME_TYPE",
            "Google Vision direct OCR accepts image files here. Use Gemini or a document gateway for PDF.",
            field="provider",
            http_status=400,
        )
    request_payload = {
        "requests": [{
            "image": {"content": base64.b64encode(content).decode("ascii")},
            "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
            "imageContext": {"languageHints": ["ar", "en"]},
        }]
    }
    response = _request(
        session,
        "POST",
        cfg.base_url.rstrip("/") + "/images:annotate",
        timeout=cfg.timeout_seconds,
        secret=secret,
        params={"key": secret},
        json=request_payload,
    )
    payload = response.json()
    first = (payload.get("responses") or [{}])[0]
    if first.get("error"):
        fake = requests.Response()
        rpc_code = int(first["error"].get("code") or 3)
        fake.status_code = {3: 400, 5: 404, 7: 403, 8: 429, 16: 401}.get(rpc_code, 503 if rpc_code in {13, 14} else 400)
        fake._content = json.dumps({"error": first["error"]}).encode("utf-8")
        raise _provider_error_from_response(fake, secret)
    text = str((first.get("fullTextAnnotation") or {}).get("text") or "")
    if not text:
        annotations = first.get("textAnnotations") or []
        text = str(annotations[0].get("description") or "") if annotations else ""
    return {"text": text, "fields": {}, "confidence": _confidence_from_vision(first, text)}


def _parse_gemini_json(raw: str) -> dict[str, Any]:
    cleaned = str(raw or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise OCRProviderError("INVALID_OUTPUT", "Gemini did not return valid structured JSON.", field="provider") from exc
    if not isinstance(payload, dict):
        raise OCRProviderError("INVALID_OUTPUT", "Gemini output must be a JSON object.", field="provider")
    fields = payload.get("fields") or {}
    if not isinstance(fields, dict):
        raise OCRProviderError("INVALID_OUTPUT", "Gemini fields must be a JSON object.", field="provider")
    try:
        confidence = float(payload.get("confidence") or 0)
    except (TypeError, ValueError) as exc:
        raise OCRProviderError("INVALID_OUTPUT", "Gemini confidence must be numeric.", field="provider") from exc
    return {
        "text": str(payload.get("text") or ""),
        "fields": fields,
        "confidence": max(0.0, min(1.0, confidence)),
    }


def _gemini_extract(
    cfg: OCRConfig,
    secret: str,
    content: bytes,
    mime_type: str,
    document_type: str,
    session: requests.Session,
) -> dict[str, Any]:
    model = cfg.model_name
    if model.startswith("models/"):
        model = model.split("/", 1)[1]
    prompt = (
        "You are a document OCR extraction service. Transcribe visible Arabic and English text exactly. "
        "Do not infer medical facts, diagnoses, eligibility, approvals, or identity values that are not visible. "
        f"The declared document type is {document_type}. "
        "Return only JSON with this schema: "
        '{"text":"verbatim transcription","fields":{},"confidence":0.0}. '
        "Allowed fields when visibly present include patient_name, national_id, phone, dob, sex, "
        "member_no, approval_no, payer_name, referring_physician, procedure_text, and study_date. "
        "confidence must be between 0 and 1. Never create a patient or order."
    )
    payload = {
        "contents": [{"parts": [
            {"text": prompt},
            {"inlineData": {"mimeType": mime_type or "application/octet-stream", "data": base64.b64encode(content).decode("ascii")}},
        ]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    response = _request(
        session,
        "POST",
        cfg.base_url.rstrip("/") + f"/models/{model}:generateContent",
        timeout=cfg.timeout_seconds,
        secret=secret,
        params={"key": secret},
        json=payload,
    )
    body = response.json()
    candidates = body.get("candidates") or []
    if not candidates:
        raise OCRProviderError("INVALID_OUTPUT", "Gemini returned no candidate output.", field="provider")
    parts = ((candidates[0].get("content") or {}).get("parts") or [])
    raw = "\n".join(str(part.get("text") or "") for part in parts if isinstance(part, dict))
    return _parse_gemini_json(raw)


def extract_bytes(
    config: Any,
    secret: str,
    content: bytes,
    *,
    original_name: str,
    mime_type: str,
    document_type: str,
    session: requests.Session | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    cfg = normalize_config(config)
    env = environ if environ is not None else os.environ
    local = validate_local(cfg, env)
    if not local["ok"]:
        first = next((v for v in local["fields"].values() if v["status"] == "invalid"), None)
        raise OCRProviderError(first["code"] if first else "CONFIG_INVALID", first["message"] if first else "OCR configuration is invalid.", http_status=400)

    try:
        max_bytes = int(env.get("RIS_OCR_MAX_FILE_BYTES", str(15 * 1024 * 1024)) or 15 * 1024 * 1024)
    except (TypeError, ValueError):
        max_bytes = 15 * 1024 * 1024
    if not content:
        raise OCRProviderError("EMPTY_DOCUMENT", "Document is empty.", http_status=400)
    if len(content) > max_bytes:
        raise OCRProviderError("DOCUMENT_TOO_LARGE", f"Document exceeds the configured {max_bytes} byte OCR limit.", http_status=413)

    client = session or requests.Session()
    if cfg.provider_key == "GENERIC_OCR_REST":
        return _generic_extract(cfg, secret, content, original_name, mime_type, document_type, client)
    if cfg.provider_key == "GOOGLE_VISION":
        return _google_vision_extract(cfg, secret, content, mime_type, client)
    if cfg.provider_key == "GEMINI":
        return _gemini_extract(cfg, secret, content, mime_type, document_type, client)
    raise OCRProviderError("UNSUPPORTED_PROVIDER", "Unsupported OCR provider.", field="provider_key", http_status=400)


def extract_file(
    config: Any,
    secret: str,
    file_path: str,
    *,
    original_name: str,
    mime_type: str,
    document_type: str,
    session: requests.Session | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    with open(file_path, "rb") as handle:
        content = handle.read()
    return extract_bytes(
        config,
        secret,
        content,
        original_name=original_name,
        mime_type=mime_type,
        document_type=document_type,
        session=session,
        environ=environ,
    )


def _connection_check(cfg: OCRConfig, secret: str, session: requests.Session) -> str:
    if cfg.provider_key == "GENERIC_OCR_REST":
        headers = {"Authorization": f"Bearer {secret}"} if secret else {}
        response = _request(
            session,
            "GET",
            cfg.base_url.rstrip("/") + "/health",
            timeout=cfg.timeout_seconds,
            secret=secret,
            headers=headers,
        )
        try:
            body = response.json()
            return str(body.get("status") or body.get("message") or "Gateway reachable")[:120]
        except ValueError:
            return "Gateway reachable"

    if cfg.provider_key == "GEMINI":
        model = cfg.model_name if cfg.model_name.startswith("models/") else f"models/{cfg.model_name}"
        _request(
            session,
            "GET",
            cfg.base_url.rstrip("/") + "/" + model,
            timeout=cfg.timeout_seconds,
            secret=secret,
            params={"key": secret},
        )
        return "Credential accepted and model is accessible"

    content, name, mime = _sample_image()
    result = _google_vision_extract(cfg, secret, content, mime, session)
    if not result.get("text"):
        return "Credential accepted; sample returned no text"
    return "Credential accepted and DOCUMENT_TEXT_DETECTION succeeded"


def validate_remote(
    config: Any,
    *,
    mode: str = "connection",
    environ: Mapping[str, str] | None = None,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    cfg = normalize_config(config)
    result = validate_local(cfg, env)
    result["mode"] = mode
    result["checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if not cfg.enabled:
        result["ok"] = False
        result["overall"] = "DISABLED"
        result["message"] = "Enable OCR before running provider validation."
        return result
    if not result["ok"]:
        result["message"] = "Correct invalid fields before contacting the provider."
        return result

    secret = str(env.get(cfg.secret_env_name, "") or "")
    client = session or requests.Session()
    started = time.perf_counter()
    try:
        if mode == "ocr":
            content, name, mime = _sample_image()
            extracted = extract_bytes(
                cfg,
                secret,
                content,
                original_name=name,
                mime_type=mime,
                document_type="OTHER",
                session=client,
                environ=env,
            )
            sample_text = str(extracted.get("text") or "").upper()
            if not sample_text.strip():
                raise OCRProviderError("OCR_TEST_EMPTY", "Provider was reachable but returned no OCR text.", field="provider")
            sample_match = "RADBRIDGE" in sample_text or "OCR TEST" in sample_text
            message = "Safe OCR test passed." if sample_match else "OCR returned text, but the expected sample words were not detected."
            result["sample"] = {
                "text_detected": True,
                "expected_words_detected": sample_match,
                "confidence": float(extracted.get("confidence") or 0),
            }
            if not sample_match:
                result["fields"]["provider_key"] = _field("warning", message, "OCR_TEST_TEXT_MISMATCH")
        else:
            message = _connection_check(cfg, secret, client)

        result["remote_checked"] = True
        result["latency_ms"] = int((time.perf_counter() - started) * 1000)
        warnings = any(v["status"] == "warning" for v in result["fields"].values())
        result["overall"] = "READY_WITH_WARNINGS" if warnings else "READY"
        result["ok"] = True
        result["message"] = message
        result["fields"]["provider_key"] = result["fields"].get("provider_key") if result["fields"].get("provider_key", {}).get("status") == "warning" else _field("valid", "Provider adapter responded successfully.")
        result["fields"]["secret_env_name"] = _field("valid", "Credential was accepted; its value remains hidden.")
        if cfg.provider_key == "GEMINI":
            result["fields"]["model_name"] = _field("valid", "Configured Gemini model is accessible.")
        return result
    except OCRProviderError as exc:
        result["remote_checked"] = True
        result["latency_ms"] = int((time.perf_counter() - started) * 1000)
        result["ok"] = False
        result["overall"] = "FAILED"
        result["error_code"] = exc.code
        result["message"] = _safe_message(exc.message, secret)
        target = exc.field if exc.field in result["fields"] else "provider_key"
        result["fields"][target] = _field("invalid", result["message"], exc.code)
        return result
    except Exception:
        # Do not expose provider library internals, request URLs, or credentials
        # to the browser. Detailed tracebacks belong only in the application log.
        result["remote_checked"] = True
        result["latency_ms"] = int((time.perf_counter() - started) * 1000)
        result["ok"] = False
        result["overall"] = "FAILED"
        result["error_code"] = "VALIDATION_INTERNAL_ERROR"
        result["message"] = "Provider validation failed unexpectedly. Review the secured RIS application log."
        result["fields"]["provider_key"] = _field("invalid", result["message"], result["error_code"])
        return result
