from app.core.config import settings
from app.services.parser_service import ExtractResult, ParserService
from app.services.material_structure_service import MaterialStructureService
from app.services.vision_parse_service import VisionParseService


def test_image_parse_does_not_call_vision_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "vision_enabled", False)
    monkeypatch.setattr(settings, "vision_fallback_on_low_quality", True)

    monkeypatch.setattr(
        ParserService,
        "_extract_image_ocr",
        staticmethod(
            lambda material: ExtractResult(
                text="OCR text",
                metadata={"method": "image_ocr"},
                warnings=["图片 OCR 识别文本较短，可能需要人工校对或视觉解析"],
            )
        ),
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("vision parser should not be called when disabled")

    monkeypatch.setattr(VisionParseService, "parse_image_file", staticmethod(fail_if_called))

    result = ParserService._extract_image(object())

    assert result.text == "OCR text"
    assert result.metadata["method"] == "image_ocr"


def test_vision_payload_can_be_folded_into_text():
    text = VisionParseService._build_text_from_payload(
        {
            "title": "第一章 平面几何",
            "sections": [
                {"title": "三角形", "content": "三角形内角和为 180 度。"},
            ],
            "formulas": ["a^2 + b^2 = c^2"],
            "figures": [{"caption": "图中 AB 平行 CD。"}],
            "key_sentences": ["辅助线通常用于构造全等三角形。"],
        }
    )

    assert "第一章 平面几何" in text
    assert "三角形内角和" in text
    assert "公式" in text
    assert "a^2 + b^2 = c^2" in text
    assert "图中 AB 平行 CD" in text


def test_unstructured_vision_content_can_be_extracted():
    content = VisionParseService._extract_message_content(
        [
            {"type": "text", "text": "第一段"},
            {"type": "text", "text": "第二段"},
        ]
    )

    assert content == "第一段\n第二段"


def test_visual_labeled_blocks_build_structured_items():
    material = type(
        "MaterialStub",
        (),
        {
            "id": 7,
            "parsed_text": (
                "Kinds of Expressions\n\n"
                "图片说明：\nA tree diagram with SEQ and CJUMP nodes.\n\n"
                "公式：\na^2 + b^2 = c^2\n\n"
                "表格：\n| A | B |\n|---|---|\n| 1 | 2 |"
            ),
        },
    )()

    sections, chunks, figures, tables, formulas = MaterialStructureService._build_structure(material)

    assert sections
    assert chunks
    assert len(figures) == 1
    assert "SEQ" in figures[0].description
    assert len(formulas) == 1
    assert formulas[0].expression == "a^2 + b^2 = c^2"
    assert len(tables) == 1
    assert "| A | B |" in tables[0].content


def test_default_section_chunks_do_not_repeat_full_text_title():
    material = type(
        "MaterialStub",
        (),
        {
            "id": 8,
            "parsed_text": "AbstractSyntaxChapter4\n\nA parser recognizes whether a sentence belongs to the language.",
        },
    )()

    sections, chunks, _, _, _ = MaterialStructureService._build_structure(material)

    assert sections[0].title == "全文"
    assert chunks
    assert all(chunk.title is None for chunk in chunks)


def test_slide_heading_and_mixed_prose_are_not_overclassified_as_formula():
    material = type(
        "MaterialStub",
        (),
        {
            "id": 9,
            "parsed_text": (
                "4.1SemanticActions\n\n"
                "A parser recognizes whether a sentence belongs to the language of a grammar.\n"
                "A compiler must do useful things with that sentence:\n"
                "constructing abstract syntax tree\n"
                "S → E $ E → T E′ E′ → + T E′\n"
            ),
        },
    )()

    sections, chunks, _, _, _ = MaterialStructureService._build_structure(material)

    assert sections[0].title == "4.1SemanticActions"
    assert chunks[0].title == "4.1SemanticActions"
    assert chunks[0].chunk_type.value == "text"


def test_standalone_formula_block_is_classified_as_formula():
    material = type(
        "MaterialStub",
        (),
        {
            "id": 10,
            "parsed_text": "公式：\na^2 + b^2 = c^2",
        },
    )()

    _, chunks, _, _, formulas = MaterialStructureService._build_structure(material)

    assert chunks[0].chunk_type.value == "formula"
    assert formulas[0].expression == "a^2 + b^2 = c^2"
