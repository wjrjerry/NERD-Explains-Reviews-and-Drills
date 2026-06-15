import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services.parser_service import ParserService
from app.services.vision_parse_service import VisionParseService


TEST_IMAGE_PATH = Path(__file__).with_name("test_img.png")
OUTPUT_PATH = Path(__file__).parent / "outputs" / "test_img_ocr_vs_vision.md"


def _json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _format_block(title: str, text: str | None, metadata: object = None, warnings: object = None) -> str:
    lines = [
        f"## {title}",
        "",
        "### Text",
        text or "<empty>",
        "",
        "### Warnings",
        "```json",
        _json(warnings or []),
        "```",
        "",
        "### Metadata",
        "```json",
        _json(metadata or {}),
        "```",
        "",
    ]
    return "\n".join(lines)


def test_compare_ocr_and_multimodal_vision_output_file():
    """Write OCR and multimodal vision parse results to one local comparison file."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not TEST_IMAGE_PATH.exists():
        OUTPUT_PATH.write_text(f"test image not found: {TEST_IMAGE_PATH}\n", encoding="utf-8")
        pytest.skip("tests/test_img.png not found")

    sections = [
        "# OCR vs Multimodal Vision Parse Comparison",
        "",
        f"- Image: `{TEST_IMAGE_PATH}`",
        f"- Vision enabled: `{settings.vision_enabled}`",
        f"- Vision provider: `{settings.vision_provider}`",
        f"- Vision model: `{settings.vision_model}`",
        "",
    ]

    material = SimpleNamespace(file_path=str(TEST_IMAGE_PATH))

    try:
        ocr_result = ParserService._extract_image_ocr(material)
        sections.append(
            _format_block(
                "Tesseract OCR Result",
                ocr_result.text,
                metadata=ocr_result.metadata,
                warnings=ocr_result.warnings,
            )
        )
    except Exception as exc:
        sections.append(_format_block("Tesseract OCR Result", f"<failed: {exc}>"))

    if not settings.vision_enabled or not settings.vision_api_key:
        sections.append(
            _format_block(
                "Multimodal Vision Result",
                "<skipped: VISION_ENABLED or VISION_API_KEY is not configured>",
            )
        )
        OUTPUT_PATH.write_text("\n".join(sections), encoding="utf-8")
        pytest.skip("vision parser is not configured")

    try:
        vision_result = VisionParseService.parse_image_file(TEST_IMAGE_PATH, context="测试图片视觉解析")
        sections.append(
            _format_block(
                "Multimodal Vision Result",
                vision_result.text,
                metadata=vision_result.metadata,
                warnings=vision_result.warnings,
            )
        )
    except Exception as exc:
        sections.append(_format_block("Multimodal Vision Result", f"<failed: {exc}>"))
        OUTPUT_PATH.write_text("\n".join(sections), encoding="utf-8")
        raise

    OUTPUT_PATH.write_text("\n".join(sections), encoding="utf-8")
    assert OUTPUT_PATH.exists()
