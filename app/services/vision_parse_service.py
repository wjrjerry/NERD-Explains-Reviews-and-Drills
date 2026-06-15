from __future__ import annotations

import base64
import json
import logging
import mimetypes
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib import error, request

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")


class VisionParseServiceError(RuntimeError):
    """Raised when visual parsing is misconfigured or the provider call fails."""


@dataclass
class VisionParseResult:
    """Normalized visual parsing result.

    The parser still persists a plain `text` field for backward compatibility.
    Structured fields are currently folded into that text and metadata, so the
    existing material_sections/material_chunks builder can consume them.
    """

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class VisionParseService:
    """Optional multimodal visual parser for geometry problems and rich slides."""

    system_prompt = (
        "You are a document visual parsing engine for a study app. "
        "Read the uploaded page image carefully and return valid JSON only."
    )
    user_prompt = (
        "Parse this study material page. Preserve useful learning content, including titles, "
        "sections, formulas, tables, figure captions, key sentences, definitions, examples, "
        "and geometry relationships if present. Return JSON only. Use this schema: "
        "{"
        "\"title\": string|null, "
        "\"sections\": [{\"title\": string, \"content\": string}], "
        "\"formulas\": [{\"latex\": string, \"description\": string}], "
        "\"tables\": [{\"title\": string, \"markdown\": string}], "
        "\"figures\": [{\"caption\": string, \"description\": string}], "
        "\"key_sentences\": [string], "
        "\"definitions\": [string], "
        "\"examples\": [string], "
        "\"plain_text\": string, "
        "\"warnings\": [string]"
        "}."
    )

    @staticmethod
    def is_enabled() -> bool:
        return settings.vision_enabled

    @staticmethod
    def _chat_completions_url(base_url: str) -> str:
        normalized = base_url.rstrip("/")
        if normalized.endswith("/chat/completions"):
            return normalized
        return f"{normalized}/chat/completions"

    @staticmethod
    def _require_settings() -> tuple[str, str, str]:
        if settings.vision_provider != "openrouter":
            raise VisionParseServiceError("当前仅支持 OpenRouter 视觉解析提供方")
        if not settings.vision_api_key:
            raise VisionParseServiceError("VISION_API_KEY is required when VISION_ENABLED=true.")
        if not settings.vision_base_url:
            raise VisionParseServiceError("VISION_BASE_URL is required when VISION_ENABLED=true.")
        if not settings.vision_model:
            raise VisionParseServiceError("VISION_MODEL is required when VISION_ENABLED=true.")

        return settings.vision_api_key, settings.vision_base_url, settings.vision_model

    @staticmethod
    def _image_data_url(image_path: Path) -> str:
        image_size = image_path.stat().st_size
        if image_size > settings.vision_max_image_bytes:
            raise VisionParseServiceError(
                f"视觉解析图片超过 {settings.vision_max_image_bytes} 字节限制，请降低图片尺寸或拆分页"
            )

        mime_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    @staticmethod
    def _extract_json_object(content: str) -> dict[str, Any]:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise VisionParseServiceError("视觉模型返回内容不是有效 JSON")
            try:
                data = json.loads(content[start : end + 1])
            except json.JSONDecodeError as exc:
                raise VisionParseServiceError("视觉模型返回内容不是有效 JSON") from exc

        if not isinstance(data, dict):
            raise VisionParseServiceError("视觉模型返回 JSON 顶层不是对象")
        return data

    @staticmethod
    def _extract_message_content(message_content: Any) -> str:
        if isinstance(message_content, str):
            return message_content

        if isinstance(message_content, list):
            parts: list[str] = []
            for item in message_content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(parts)

        if isinstance(message_content, dict):
            text = message_content.get("text") or message_content.get("content")
            if isinstance(text, str):
                return text

        return ""

    @staticmethod
    def _stringify_items(items: Any) -> list[str]:
        if not isinstance(items, list):
            return []

        values: list[str] = []
        for item in items:
            if isinstance(item, str):
                values.append(item.strip())
            elif isinstance(item, dict):
                label = item.get("title") or item.get("name")
                text = (
                    item.get("text")
                    or item.get("content")
                    or item.get("description")
                    or item.get("caption")
                    or item.get("latex")
                    or item.get("equation")
                    or item.get("expression")
                    or item.get("markdown")
                )
                if isinstance(text, str):
                    if isinstance(label, str) and label.strip():
                        values.append(f"{label.strip()}：{text.strip()}")
                    else:
                        values.append(text.strip())
        return [value for value in values if value]

    @staticmethod
    def _build_text_from_payload(payload: dict[str, Any]) -> str:
        parts: list[str] = []

        title = payload.get("title")
        if isinstance(title, str) and title.strip():
            parts.append(title.strip())

        sections = payload.get("sections")
        if isinstance(sections, list):
            for index, section in enumerate(sections, start=1):
                if isinstance(section, str):
                    parts.append(section.strip())
                    continue
                if not isinstance(section, dict):
                    continue

                heading = section.get("title") or section.get("heading") or f"视觉解析章节 {index}"
                content = section.get("content") or section.get("text") or section.get("description")
                if isinstance(heading, str) and heading.strip():
                    parts.append(heading.strip())
                if isinstance(content, str) and content.strip():
                    parts.append(content.strip())

        plain_text = payload.get("plain_text")
        if isinstance(plain_text, str) and plain_text.strip():
            parts.append(plain_text.strip())

        labeled_fields = [
            ("公式", "formulas"),
            ("表格", "tables"),
            ("图片说明", "figures"),
            ("重点句", "key_sentences"),
            ("定义", "definitions"),
            ("例题", "examples"),
        ]
        for label, key in labeled_fields:
            values = VisionParseService._stringify_items(payload.get(key))
            if values:
                parts.append(f"{label}：\n" + "\n".join(values))

        return "\n\n".join(part for part in parts if part).strip()

    @staticmethod
    def parse_image_file(image_path: Path, *, context: str) -> VisionParseResult:
        """Call OpenRouter-compatible vision model and normalize its JSON output."""
        api_key, base_url, model = VisionParseService._require_settings()
        url = VisionParseService._chat_completions_url(base_url)
        started_at = time.perf_counter()

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": VisionParseService.system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VisionParseService.user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": VisionParseService._image_data_url(image_path),
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            "temperature": 0.1,
        }
        if settings.vision_response_format_json:
            payload["response_format"] = {"type": "json_object"}

        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        logger.info(
            "Vision parse started context=%s provider=%s model=%s image=%s",
            context,
            settings.vision_provider,
            model,
            image_path.name,
        )
        try:
            with request.urlopen(req, timeout=settings.vision_timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise VisionParseServiceError(f"视觉模型返回 HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise VisionParseServiceError(f"视觉模型连接失败: {exc.reason}") from exc
        except TimeoutError as exc:
            raise VisionParseServiceError("视觉模型请求超时") from exc

        try:
            data = json.loads(response_body)
            content = VisionParseService._extract_message_content(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise VisionParseServiceError("视觉模型返回结构不符合 chat completions 格式") from exc

        if not isinstance(content, str) or not content.strip():
            raise VisionParseServiceError("视觉模型返回空内容")

        try:
            payload_json = VisionParseService._extract_json_object(content)
            text = VisionParseService._build_text_from_payload(payload_json)
            warnings = VisionParseService._stringify_items(payload_json.get("warnings"))
            unstructured_response = False
        except VisionParseServiceError:
            payload_json = {"plain_text": content.strip()}
            text = content.strip()
            warnings = ["视觉模型未严格返回 JSON，已按纯文本保存"]
            unstructured_response = True

        if not text:
            raise VisionParseServiceError("视觉模型未解析出可用文本")

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            "Vision parse succeeded context=%s model=%s elapsed_ms=%s chars=%s",
            context,
            model,
            elapsed_ms,
            len(text),
        )
        return VisionParseResult(
            text=text,
            metadata={
                "method": "vision",
                "provider": settings.vision_provider,
                "model": model,
                "elapsed_ms": elapsed_ms,
                "unstructured_response": unstructured_response,
                "raw_payload": payload_json,
            },
            warnings=warnings,
        )
