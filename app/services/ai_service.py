import json
import re

from app.core.config import settings
from app.services import llm_service

KNOWLEDGE_INPUT_MAX_CHARS = 12000

ENGLISH_KEYWORD_STOPWORDS = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "also",
    "am",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "between",
    "both",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "doing",
    "during",
    "each",
    "few",
    "for",
    "from",
    "had",
    "has",
    "have",
    "having",
    "he",
    "her",
    "here",
    "hers",
    "him",
    "his",
    "how",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "itself",
    "just",
    "may",
    "might",
    "more",
    "most",
    "must",
    "no",
    "nor",
    "not",
    "of",
    "on",
    "once",
    "only",
    "or",
    "other",
    "our",
    "out",
    "over",
    "own",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "whether",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "will",
    "with",
    "would",
    "you",
    "your",
}


def _normalize_text(text: str) -> str:
    """Collapse whitespace so mock extraction is stable for different inputs."""
    return re.sub(r"\s+", " ", text).strip()


def _split_sentences(text: str) -> list[str]:
    """Split material text into short sentence-like fragments."""
    sentences = re.split(r"[。！？.!?\n]+", text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def _extract_mock_keywords(text: str) -> list[str]:
    """Pick deterministic keywords from the material text.

    This is not real NLP. It only gives the frontend a stable shape before the
    real LLM provider is connected.
    """
    known_terms = [
        "需求分析",
        "数据流图",
        "用例图",
        "状态图",
        "类图",
        "数据库",
        "接口",
        "权限",
        "错题",
        "复习计划",
        "知识提炼",
        "AI问答",
        "AI出题",
        "测试",
    ]
    seen: set[str] = set()
    keywords: list[str] = []

    for term in known_terms:
        if term in text:
            keywords.append(term)
            seen.add(term)

    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text)
    chinese_phrases = re.findall(r"[\u4e00-\u9fff]{2,8}", text)

    for word in words + chinese_phrases:
        normalized = word.lower() if word.isascii() else word
        if normalized in seen:
            continue
        if _is_noise_keyword(word):
            continue

        seen.add(normalized)
        keywords.append(word)
        if len(keywords) >= 6:
            break

    return keywords or ["知识点", "复习重点", "核心概念"]


_NOISE_KEYWORDS = {
    "pdf",
    "txt",
    "png",
    "jpg",
    "jpeg",
    "image",
    "text",
    "book",
    "ebook",
    "chapter",
    "chap",
    "file",
    "page",
    "pages",
    "资料",
    "文件",
}


def _is_noise_keyword(value: str) -> bool:
    """Return whether a term is likely file metadata instead of knowledge."""
    normalized = value.strip().strip("._-").casefold()
    if not normalized:
        return True
    if normalized in _NOISE_KEYWORDS:
        return True
    if re.fullmatch(r"\d+", normalized):
        return True
    if re.fullmatch(r"chapter\s*\d+", normalized):
        return True
    if re.fullmatch(r"ch\d+", normalized):
        return True
    if re.fullmatch(r"[a-z]{1,2}", normalized):
        return True
    return False


def _clean_knowledge_terms(value: object, *, limit: int = 8) -> list[str]:
    """Normalize model-returned knowledge terms and remove metadata noise."""
    if not isinstance(value, list):
        return []

    terms: list[str] = []
    seen: set[str] = set()
    for item in value:
        term = _normalize_text(str(item)).strip(" ，,。.；;：:")
        if _is_noise_keyword(term):
            continue
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)
        terms.append(term[:40])
        if len(terms) >= limit:
            break
    return terms


def generate_knowledge(
    parsed_text: str,
    *,
    target_name: str | None = None,
    scope: str = "material",
    subject: str | None = None,
    source_materials: list[dict[str, object]] | None = None,
) -> dict[str, str | list[str]]:
    """Call or mock AI to summarize material and extract learning points.

    This is the AI capability used by knowledge_service.extract_knowledge().
    The rest of the system should not care whether the result comes from mock
    data or a real LLM provider, as long as the returned structure matches
    KnowledgeExtractResponse.
    """
    if settings.ai_provider != "mock":
        return _generate_knowledge_with_real_ai(
            parsed_text=parsed_text,
            target_name=target_name,
            scope=scope,
            subject=subject,
            source_materials=source_materials,
        )

    text = _normalize_text(parsed_text)
    sentences = _split_sentences(text)
    keywords = _normalize_keywords(
        _extract_mock_keywords(text),
        fallback_text=text,
        limit=6,
    )

    if not text:
        summary = "当前资料暂无可用于知识提炼的文本内容。"
        outline = ["等待资料解析结果", "补充可分析文本", "重新生成知识提炼"]
    else:
        preview = text[:120]
        target_prefix = f"围绕「{target_name}」这一复习目标，" if target_name else ""
        summary = f"{target_prefix}本资料主要内容包括：{preview}"
        if len(text) > 120:
            summary += "..."

        outline = [
            "资料核心内容梳理",
            "重要概念与定义",
            "复习重点与可能考点",
        ]

    key_points = [
        f"理解「{keyword}」相关概念和使用场景。" for keyword in keywords[:3]
    ]
    while len(key_points) < 3:
        key_points.append("结合资料内容整理核心概念之间的关系。")

    exam_points = [
        f"关注「{keyword}」在题目中的定义、判断或应用。" for keyword in keywords[:3]
    ]
    if sentences:
        exam_points.append(f"能够解释资料中的关键表述：{sentences[0][:60]}")

    return {
        "summary": summary,
        "outline": outline,
        "keywords": keywords,
        "key_points": key_points,
        "exam_points": exam_points,
    }


def _material_blocks_for_knowledge(
    *,
    parsed_text: str,
    source_materials: list[dict[str, object]] | None,
) -> list[dict[str, object]]:
    """Build compact structured material blocks for knowledge extraction."""
    if source_materials:
        blocks: list[dict[str, object]] = []
        remaining_chars = KNOWLEDGE_INPUT_MAX_CHARS
        for item in source_materials:
            content = _normalize_text(str(item.get("content", "") or ""))
            if not content or remaining_chars <= 0:
                continue
            clipped = content[:remaining_chars]
            remaining_chars -= len(clipped)
            blocks.append(
                {
                    "material_id": item.get("material_id"),
                    "title": str(item.get("title", "") or "").strip(),
                    "content": clipped,
                }
            )
        return blocks

    text = _normalize_text(parsed_text)
    return (
        [{"material_id": None, "title": "", "content": text[:KNOWLEDGE_INPUT_MAX_CHARS]}]
        if text
        else []
    )


def _normalize_knowledge_response(data: dict[str, object]) -> dict[str, str | list[str]]:
    """Validate and clean the model response used by knowledge extraction."""
    summary = _normalize_text(str(data.get("summary", "") or ""))
    outline = _limit_string_list(
        data.get("outline"),
        fallback=["核心内容梳理", "重要概念与关系", "复习重点与考点"],
        min_items=3,
        max_items=8,
    )
    keywords = _normalize_keywords(data.get("keywords"), limit=8)
    key_points = _limit_string_list(
        data.get("key_points"),
        fallback=[],
        min_items=0,
        max_items=8,
    )
    exam_points = _limit_string_list(
        data.get("exam_points"),
        fallback=[],
        min_items=0,
        max_items=8,
    )

    if not summary:
        raise llm_service.LlmServiceError("LLM knowledge extraction summary is empty.")
    if not keywords:
        keywords = ["核心概念", "复习重点", "考点分析"]
    if not key_points:
        key_points = [f"理解「{keyword}」的定义、作用和适用场景。" for keyword in keywords[:3]]
    if not exam_points:
        exam_points = [f"关注「{keyword}」相关的判断、解释和应用题。" for keyword in keywords[:3]]

    return {
        "summary": summary[:800],
        "outline": outline,
        "keywords": keywords,
        "key_points": key_points,
        "exam_points": exam_points,
    }


def _generate_knowledge_with_real_ai(
    *,
    parsed_text: str,
    target_name: str | None,
    scope: str,
    subject: str | None,
    source_materials: list[dict[str, object]] | None,
) -> dict[str, str | list[str]]:
    """Use the configured real LLM to extract readable learning knowledge."""
    material_blocks = _material_blocks_for_knowledge(
        parsed_text=parsed_text,
        source_materials=source_materials,
    )
    if not material_blocks:
        raise llm_service.LlmServiceError("No parsed material text for knowledge extraction.")

    system_prompt = (
        "你是一个严谨的备考知识提炼助手。请只基于资料正文生成复习摘要，"
        "必须返回严格 JSON 对象，不要返回 Markdown、解释文字或代码块。"
    )
    user_prompt = (
        "提炼范围："
        f"{'目标级：综合该目标下所有资料' if scope == 'target' else '资料级：聚焦单份资料'}\n"
        f"目标或资料名称：{target_name or '未提供'}\n"
        f"科目：{subject or '未提供'}\n\n"
        "资料 JSON：\n"
        f"{json.dumps(material_blocks, ensure_ascii=False)}\n\n"
        "请生成适合学生复习使用的知识提炼结果。要求：\n"
        "1. summary 用 2-4 句话概括真正的课程内容，不要复述资料ID、文件名、作者、教材标题或格式信息。\n"
        "2. outline 是 3-6 个复习提纲条目，应是章节/主题/能力结构，不要写“资料核心内容梳理”这类空泛模板。\n"
        "3. keywords 是 4-8 个真实课程知识点；不要包含 pdf、txt、Chapter、Text、Book、文件名、纯数字等元信息。\n"
        "4. key_points 是 3-6 条具体复习重点，说明需要理解什么、为什么重要。\n"
        "5. exam_points 是 3-6 条可能考点，覆盖定义辨析、机制理解、应用分析或易错点。\n"
        "6. 如果资料中出现英文术语，应保留关键术语，但必须是课程概念。\n\n"
        "返回 JSON 对象，字段固定为：summary, outline, keywords, key_points, exam_points。"
    )
    content = llm_service.chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        task="knowledge_extraction",
        timeout_seconds=max(settings.ai_timeout_seconds, 60),
        max_tokens=1600,
        response_format_json=True,
    )
    return _normalize_knowledge_response(_extract_json_object(content))


def _select_reference_snippet(parsed_text: str, question: str) -> str:
    """Select a deterministic material snippet related to the question."""
    sentences = _split_sentences(_normalize_text(parsed_text))
    if not sentences:
        return ""

    question_terms = _extract_mock_keywords(question)
    for sentence in sentences:
        if any(term in sentence for term in question_terms):
            return sentence[:120]

    return sentences[0][:120]


def answer_question(
    parsed_text: str,
    question: str,
    *,
    material_id: int,
) -> dict[str, str | list[dict[str, int | str]]]:
    """Call or mock AI to answer one question using material text as context."""
    # TODO: Accept optional conversation history when multi-turn QA is needed.
    # TODO: Return answer text plus short source snippets from the material.
    # TODO: Later add prompt construction and real AI provider integration.
    snippet = _select_reference_snippet(parsed_text, question)

    if settings.ai_provider != "mock":
        answer = _answer_question_with_real_ai(
            parsed_text=parsed_text,
            question=question,
        )
        references = []
        if snippet:
            references.append(
                {
                    "material_id": material_id,
                    "snippet": snippet,
                }
            )
        return {
            "answer": answer,
            "references": references,
        }

    if snippet:
        answer = (
            f"根据资料内容，{snippet}。"
            f"针对你的问题「{question}」，可以先从这段内容理解核心概念，"
            "再结合资料中的相关章节进行复习。"
        )
        references = [
            {
                "material_id": material_id,
                "snippet": snippet,
            }
        ]
    else:
        answer = (
            f"当前资料没有可用于回答「{question}」的解析文本。"
            "请等待资料解析完成后再提问。"
        )
        references = []

    return {
        "answer": answer,
        "references": references,
    }


def _answer_question_with_real_ai(
    *,
    parsed_text: str,
    question: str,
) -> str:
    """Ask the configured real LLM to answer from the given material text."""
    system_prompt = (
        "你是一个备考复习助手。请只根据用户提供的资料回答问题。"
        "如果资料中没有足够信息，请明确说明资料中未提供足够依据。"
        "回答要简洁、准确，适合学生复习。"
    )
    user_prompt = (
        "资料：\n"
        f"{parsed_text}\n\n"
        "学生问题：\n"
        f"{question}\n\n"
        "请给出回答："
    )
    return llm_service.chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        task="qa",
    )


def _build_question_id(material_id: int, index: int) -> int:
    """Build a readable deterministic mock question ID."""
    return material_id * 1000 + index + 1


def _extract_json_array(text: str) -> list[object]:
    """Parse a JSON array from a model response.

    Some providers wrap JSON in ```json fences. This helper keeps the LLM prompt
    strict while still tolerating common formatting noise.
    """
    cleaned = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()

    try:
        data = _loads_llm_json(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start < 0 or end < start:
            raise llm_service.LlmServiceError(
                "LLM question generation did not return a JSON array."
            )
        data = _loads_llm_json(cleaned[start : end + 1])

    if not isinstance(data, list):
        raise llm_service.LlmServiceError(
            "LLM question generation response must be a JSON array."
        )
    return data


def _extract_json_object(text: str) -> dict[str, object]:
    """Parse a JSON object from a model response."""
    cleaned = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()

    try:
        data = _loads_llm_json(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end < start:
            raise llm_service.LlmServiceError(
                "LLM scoring did not return a JSON object."
            )
        data = _loads_llm_json(cleaned[start : end + 1])

    if not isinstance(data, dict):
        raise llm_service.LlmServiceError(
            "LLM scoring response must be a JSON object."
        )
    return data


def _loads_llm_json(text: str) -> object:
    """Load JSON with small repairs for common model formatting slips."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as original_exc:
        repaired = _repair_llm_json(text)
        if repaired == text:
            raise original_exc
        try:
            return json.loads(repaired)
        except json.JSONDecodeError as repaired_exc:
            raise repaired_exc from original_exc


_JSON_OBJECT_KEYS = (
    "points",
    "merges",
    "name",
    "existing_name",
    "description",
    "importance_weight",
    "parent_name",
    "level",
    "sort_order",
    "evidence",
    "material_id",
    "snippet",
    "relevance_score",
    "summary",
    "outline",
    "keywords",
    "key_points",
    "exam_points",
    "questions",
    "answer",
    "analysis",
    "options",
    "correct_answer",
)


def _repair_llm_json(text: str) -> str:
    """Repair conservative JSON issues that LLMs commonly emit."""
    repaired = text.strip().lstrip("\ufeff")
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
    repaired = re.sub(r"}\s*(?={)", "},", repaired)
    repaired = re.sub(r"]\s*(?={)", "],", repaired)
    repaired = re.sub(
        r'(?<=[}\]"\d])\s*\n\s*(?="(?:' + "|".join(_JSON_OBJECT_KEYS) + r')"\s*:)',
        ",\n",
        repaired,
    )
    return repaired


def _normalize_string_list(value: object) -> list[str]:
    """Normalize model-returned list-like values into a clean string list."""
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _is_meaningful_keyword(keyword: str) -> bool:
    """Reject filler words that are not useful learning keywords."""
    candidate = keyword.strip(" \t\r\n,.;:!?，。；：！？、()（）[]【】{}“”\"'")
    if not candidate or _is_noise_keyword(candidate):
        return False

    has_chinese = bool(re.search(r"[\u4e00-\u9fff]", candidate))
    if has_chinese:
        return len(candidate) >= 2

    if candidate.isascii():
        lowered = candidate.lower()
        tokens = re.findall(r"[a-z0-9]+", lowered)
        if not tokens:
            return False
        if len(tokens) == 1 and (
            len(tokens[0]) < 3 or tokens[0] in ENGLISH_KEYWORD_STOPWORDS
        ):
            return False
        return any(
            len(token) >= 3
            and token not in ENGLISH_KEYWORD_STOPWORDS
            and not token.isdigit()
            for token in tokens
        )

    return len(candidate) >= 2


def _dedupe_and_filter_keywords(items: list[str], *, limit: int) -> list[str]:
    """Keep stable keyword order while removing duplicates and filler words."""
    keywords: list[str] = []
    seen: set[str] = set()
    for item in items:
        keyword = item.strip(" \t\r\n,.;:!?，。；：！？、()（）[]【】{}“”\"'")
        if not _is_meaningful_keyword(keyword):
            continue

        dedupe_key = keyword.lower() if keyword.isascii() else keyword
        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)
        keywords.append(keyword)
        if len(keywords) >= limit:
            break
    return keywords


def _normalize_keywords(
    value: object,
    *,
    fallback_text: str | None = None,
    limit: int = 10,
) -> list[str]:
    """Normalize knowledge keywords and fall back to deterministic extraction."""
    keywords = _dedupe_and_filter_keywords(_normalize_string_list(value), limit=limit)
    if keywords or not fallback_text:
        return keywords

    fallback = _dedupe_and_filter_keywords(
        _extract_mock_keywords(fallback_text),
        limit=limit,
    )
    return fallback or ["知识点", "复习重点", "核心概念"][:limit]


def _limit_string_list(
    value: object,
    *,
    fallback: list[str],
    min_items: int,
    max_items: int,
) -> list[str]:
    """Normalize a list field and top it up with fallback items when needed."""
    items = _normalize_string_list(value)
    for item in fallback:
        if len(items) >= min_items:
            break
        if item not in items:
            items.append(item)
    return items[:max_items]


def _fallback_question_hints(
    *,
    stem: str,
    knowledge_points: list[str],
) -> list[str]:
    """Build non-answer-revealing hints when the model omits them."""
    focus = "、".join(knowledge_points[:2]) if knowledge_points else "题干中的核心概念"
    return [
        f"先回到「{focus}」的定义或适用场景，确认题目考查的概念边界。",
        "再比较题干关键词与各选项/作答要点之间的关系，排除与资料依据不一致的表述。",
        f"最后用资料中的原句或例子验证你的判断，但不要只凭直觉作答：{stem[:40]}",
    ]


def _normalize_question_hints(
    value: object,
    *,
    stem: str,
    knowledge_points: list[str],
) -> list[str]:
    """Normalize three progressive hints without exposing full answers."""
    hints = _normalize_string_list(value)
    if len(hints) < 3:
        hints.extend(
            hint
            for hint in _fallback_question_hints(
                stem=stem,
                knowledge_points=knowledge_points,
            )
            if hint not in hints
        )
    return hints[:3]


def _normalize_generated_question(
    raw: object,
    *,
    index: int,
    difficulty: str,
    requested_types: list[str],
) -> dict[str, object]:
    """Validate and normalize one LLM-generated question."""
    if not isinstance(raw, dict):
        raise llm_service.LlmServiceError("Generated question item must be an object.")

    question_type = str(raw.get("type", "")).strip()
    if question_type not in requested_types:
        raise llm_service.LlmServiceError(
            f"Generated question has unsupported type: {question_type}"
        )

    is_subjective = question_type == "subjective"
    options = raw.get("options", [])
    if not isinstance(options, list) or (not options and not is_subjective):
        raise llm_service.LlmServiceError("Generated question options must be a list.")

    normalized_options: list[dict[str, str]] = []
    for option in options:
        if not isinstance(option, dict):
            raise llm_service.LlmServiceError("Generated option must be an object.")
        key = str(option.get("key", "")).strip()
        text = str(option.get("text", "")).strip()
        option_analysis = str(option.get("analysis", "")).strip()
        if not key or not text or not option_analysis:
            raise llm_service.LlmServiceError(
                "Generated option key/text/analysis is empty."
            )
        normalized_options.append(
            {"key": key, "text": text, "analysis": option_analysis}
        )

    if is_subjective and options:
        raise llm_service.LlmServiceError(
            "Generated subjective question options must be empty."
        )

    correct_answer = raw.get("correct_answer")
    if not isinstance(correct_answer, list) or not correct_answer:
        raise llm_service.LlmServiceError(
            "Generated question correct_answer must be a non-empty list."
        )

    knowledge_points = raw.get("knowledge_points", [])
    if not isinstance(knowledge_points, list):
        knowledge_points = []
    normalized_points = [
        str(point).strip() for point in knowledge_points if str(point).strip()
    ]

    stem = str(raw.get("stem", "")).strip()
    analysis = str(raw.get("analysis", "")).strip()
    if not stem or not analysis:
        raise llm_service.LlmServiceError("Generated question stem/analysis is empty.")

    return {
        "id": index + 1,
        "type": question_type,
        "stem": stem,
        "options": normalized_options,
        "correct_answer": [str(answer).strip() for answer in correct_answer],
        "analysis": analysis,
        "hints": _normalize_question_hints(
            raw.get("hints", []),
            stem=stem,
            knowledge_points=normalized_points,
        ),
        "knowledge_points": normalized_points,
        "difficulty": str(raw.get("difficulty") or difficulty),
    }


def _infer_knowledge_point_ids_from_text(
    *,
    text: str,
    candidate_points: list[dict[str, object]],
    max_points: int = 3,
) -> list[int]:
    """Infer relevant knowledge point IDs from text and candidate point metadata."""
    normalized_text = _normalize_text(text)
    scored: list[tuple[float, int]] = []
    for point in candidate_points:
        try:
            point_id = int(point.get("id"))
        except (TypeError, ValueError):
            continue
        name = str(point.get("name", "")).strip()
        description = str(point.get("description", "") or "").strip()
        try:
            importance = float(point.get("importance_weight", 0.0) or 0.0)
        except (TypeError, ValueError):
            importance = 0.0

        score = importance * 0.2
        if name and name in normalized_text:
            score += 2.0
        for token in _extract_mock_keywords(f"{name} {description}")[:5]:
            if token and token in normalized_text:
                score += 0.4
        if score > 0:
            scored.append((score, point_id))

    scored.sort(reverse=True)
    return [point_id for _, point_id in scored[:max_points]]


def infer_question_knowledge_points(
    question: dict[str, object],
    candidate_points: list[dict[str, object]],
) -> list[int]:
    """Infer graph knowledge points covered by one generated question."""
    text = " ".join(
        [
            str(question.get("stem", "")),
            str(question.get("analysis", "")),
            " ".join(str(item) for item in question.get("knowledge_points", []) if item),
        ]
    )
    return _infer_knowledge_point_ids_from_text(
        text=text,
        candidate_points=candidate_points,
        max_points=3,
    )


def infer_qa_knowledge_points(
    *,
    question: str,
    answer: str,
    candidate_points: list[dict[str, object]],
) -> list[int]:
    """Infer graph knowledge points involved in one QA interaction."""
    return _infer_knowledge_point_ids_from_text(
        text=f"{question}\n{answer}",
        candidate_points=candidate_points,
        max_points=3,
    )


def _single_choice_question(
    *,
    question_id: int,
    keyword: str,
    difficulty: str,
) -> dict[str, object]:
    """Build one mock single-choice question."""
    return {
        "id": question_id,
        "type": "single_choice",
        "stem": f"关于「{keyword}」，下列说法最符合资料内容的是哪一项？",
        "options": [
            {
                "key": "A",
                "text": f"「{keyword}」是资料中的重要复习点。",
                "analysis": f"资料中直接或间接围绕「{keyword}」展开，因此该项符合资料。",
            },
            {
                "key": "B",
                "text": f"「{keyword}」与本资料完全无关。",
                "analysis": f"资料已涉及「{keyword}」，所以该项与资料不符。",
            },
            {
                "key": "C",
                "text": "该内容只适用于管理员后台配置。",
                "analysis": "资料没有把该知识点限定为管理员后台配置场景。",
            },
            {
                "key": "D",
                "text": "该内容不需要在复习中理解。",
                "analysis": "该知识点由资料提取而来，属于需要理解的复习内容。",
            },
        ],
        "correct_answer": ["A"],
        "analysis": f"资料中围绕「{keyword}」展开了说明，因此 A 项正确。",
        "hints": _fallback_question_hints(
            stem=f"关于「{keyword}」的资料理解题",
            knowledge_points=[keyword],
        ),
        "knowledge_points": [keyword],
        "difficulty": difficulty,
    }


def _multiple_choice_question(
    *,
    question_id: int,
    keywords: list[str],
    difficulty: str,
) -> dict[str, object]:
    """Build one mock multiple-choice question."""
    first = keywords[0]
    second = keywords[1] if len(keywords) > 1 else "复习重点"
    return {
        "id": question_id,
        "type": "multiple_choice",
        "stem": "根据资料内容，下列哪些属于需要重点理解的内容？",
        "options": [
            {
                "key": "A",
                "text": first,
                "analysis": f"资料中出现或强调了「{first}」，因此应作为复习点。",
            },
            {
                "key": "B",
                "text": second,
                "analysis": f"资料中出现或强调了「{second}」，因此应作为复习点。",
            },
            {
                "key": "C",
                "text": "与资料无关的随机概念",
                "analysis": "该选项不是从当前资料中提取出的知识点。",
            },
            {
                "key": "D",
                "text": "不需要掌握的边缘信息",
                "analysis": "资料生成的题目关注复习重点，该项表述缺少资料依据。",
            },
        ],
        "correct_answer": ["A", "B"],
        "analysis": f"资料中明确涉及「{first}」和「{second}」，因此 A、B 正确。",
        "hints": _fallback_question_hints(
            stem="根据资料内容判断重点理解内容",
            knowledge_points=[first, second],
        ),
        "knowledge_points": [first, second],
        "difficulty": difficulty,
    }


def _true_false_question(
    *,
    question_id: int,
    sentence: str,
    difficulty: str,
) -> dict[str, object]:
    """Build one mock true/false question."""
    statement = sentence or "资料解析文本可用于 AI 知识提炼、问答和出题。"
    return {
        "id": question_id,
        "type": "true_false",
        "stem": f"判断题：{statement}",
        "options": [
            {
                "key": "T",
                "text": "正确",
                "analysis": "题干表述来自资料片段，与资料内容一致。",
            },
            {
                "key": "F",
                "text": "错误",
                "analysis": "题干表述依据资料生成，因此不能判断为错误。",
            },
        ],
        "correct_answer": ["T"],
        "analysis": "该判断题直接依据资料片段生成，因此应选择正确。",
        "hints": _fallback_question_hints(
            stem=statement,
            knowledge_points=_extract_mock_keywords(statement)[:2],
        ),
        "knowledge_points": _extract_mock_keywords(statement)[:2],
        "difficulty": difficulty,
    }


def _subjective_question(
    *,
    question_id: int,
    keyword: str,
    sentence: str,
    difficulty: str,
) -> dict[str, object]:
    """Build one mock subjective question."""
    reference = sentence or f"应围绕「{keyword}」结合资料说明其含义、作用和适用场景。"
    return {
        "id": question_id,
        "type": "subjective",
        "stem": f"请结合资料，简要说明「{keyword}」的核心含义和复习价值。",
        "options": [],
        "correct_answer": [reference],
        "analysis": f"回答应结合资料中关于「{keyword}」的描述，说明其含义和学习价值。",
        "hints": _fallback_question_hints(
            stem=f"说明「{keyword}」的核心含义和复习价值",
            knowledge_points=[keyword],
        ),
        "knowledge_points": [keyword],
        "difficulty": difficulty,
    }


def generate_questions(
    parsed_text: str,
    *,
    material_id: int,
    question_types: list[str],
    difficulty: str,
    count: int,
    target_title: str | None = None,
    extra_requirement: str | None = None,
    knowledge_points: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    """Call or mock AI to generate objective and subjective questions."""
    requested_types = question_types or ["single_choice"]
    focus_points = knowledge_points or []
    if settings.ai_provider != "mock":
        return _generate_questions_with_real_ai(
            parsed_text=parsed_text,
            question_types=requested_types,
            difficulty=difficulty,
            count=count,
            target_title=target_title,
            extra_requirement=extra_requirement,
            knowledge_points=focus_points,
        )

    text = _normalize_text(parsed_text)
    sentences = _split_sentences(text)
    focused_names = [
        str(point.get("name", "")).strip()
        for point in focus_points
        if str(point.get("name", "")).strip()
    ]
    keywords = focused_names or _extract_mock_keywords(text)
    questions: list[dict[str, object]] = []

    for index in range(count):
        question_type = requested_types[index % len(requested_types)]
        question_id = _build_question_id(material_id, index)
        keyword = keywords[index % len(keywords)]

        if question_type == "multiple_choice":
            question = _multiple_choice_question(
                question_id=question_id,
                keywords=keywords[index % len(keywords) :] + keywords[: index % len(keywords)],
                difficulty=difficulty,
            )
        elif question_type == "true_false":
            question = _true_false_question(
                question_id=question_id,
                sentence=sentences[index % len(sentences)] if sentences else "",
                difficulty=difficulty,
            )
        elif question_type == "subjective":
            question = _subjective_question(
                question_id=question_id,
                keyword=keyword,
                sentence=sentences[index % len(sentences)] if sentences else "",
                difficulty=difficulty,
            )
        else:
            question = _single_choice_question(
                question_id=question_id,
                keyword=keyword,
                difficulty=difficulty,
            )

        questions.append(question)

    return questions


def _generate_questions_with_real_ai(
    *,
    parsed_text: str,
    question_types: list[str],
    difficulty: str,
    count: int,
    target_title: str | None = None,
    extra_requirement: str | None = None,
    knowledge_points: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    """Ask the configured real LLM to generate structured questions."""
    allowed_types = ", ".join(question_types)
    focus_points = knowledge_points or []
    focus_lines = []
    for point in focus_points:
        point_id = str(point.get("id", "")).strip()
        name = str(point.get("name", "")).strip()
        description = str(point.get("description", "") or "").strip()
        weight = str(point.get("importance_weight", "")).strip()
        if name:
            focus_lines.append(
                f"- id={point_id}; name={name}; importance={weight}; description={description}"
            )

    system_prompt = (
        "你是一个软件工程备考出题助手。请只根据用户提供的资料出题。"
        "必须返回严格 JSON 数组，不要返回 Markdown、解释文字或代码块。"
        "每道题必须包含 type, stem, options, correct_answer, analysis, "
        "hints, knowledge_points, difficulty 字段。"
        "选择/判断题的每个 options 元素必须包含 key, text, analysis 字段。"
        "主观题的 options 必须为空数组。"
    )
    user_prompt = (
        f"复习目标：{target_title or '未指定'}\n\n"
        "优先覆盖的知识点：\n"
        f"{chr(10).join(focus_lines) if focus_lines else '未指定，请从资料中自动提取。'}\n\n"
        "资料：\n"
        f"{_normalize_text(parsed_text)[:6000]}\n\n"
        "用户补充出题要求：\n"
        f"{_normalize_text(extra_requirement or '') or '无'}\n\n"
        "出题要求：\n"
        f"- 题目数量：{count}\n"
        f"- 允许题型：{allowed_types}\n"
        f"- 难度：{difficulty}\n"
        "- single_choice 只有一个正确答案，选项 key 使用 A/B/C/D。\n"
        "- multiple_choice 至少两个正确答案，选项 key 使用 A/B/C/D。\n"
        "- true_false 使用两个选项：T=正确，F=错误。\n"
        "- subjective 是主观题，不提供选项，options 必须为 []。\n"
        "- 客观题 correct_answer 必须是选项 key 数组。\n"
        "- 主观题 correct_answer 必须是参考答案或评分要点字符串数组。\n"
        "- 客观题每个选项的 analysis 必须说明该选项为什么正确或错误。\n"
        "- 题目级 analysis 需要综合说明正确答案依据。\n"
        "- hints 必须是 3 个字符串，按“概念提示、思路提示、接近答案但不直接给出答案”的顺序生成。\n"
        "- hints 不能直接出现正确选项 key、不能直接写出“答案是...”，也不要完整复述 correct_answer。\n"
        "- knowledge_points 是字符串数组，必须优先使用上方知识点名称。\n"
        "- 如果给定了优先覆盖的知识点，不要生成与这些知识点无关的题目。\n\n"
        "返回示例格式：\n"
        "[{\"type\":\"single_choice\",\"stem\":\"...\","
        "\"options\":[{\"key\":\"A\",\"text\":\"...\",\"analysis\":\"该项正确，因为...\"}],"
        "\"correct_answer\":[\"A\"],\"analysis\":\"...\",\"knowledge_points\":[\"...\"],"
        "\"hints\":[\"先回忆概念边界。\",\"比较题干和选项关键词。\",\"回到资料中的对应描述验证判断。\"],"
        "\"difficulty\":\"medium\"}]"
    )
    content = llm_service.chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        task="question_generation",
    )
    items = _extract_json_array(content)
    if len(items) != count:
        raise llm_service.LlmServiceError(
            f"LLM generated {len(items)} questions, expected {count}."
        )

    return [
        _normalize_generated_question(
            item,
            index=index,
            difficulty=difficulty,
            requested_types=question_types,
        )
        for index, item in enumerate(items)
    ]


def analyze_wrong_reason(
    *,
    stem: str,
    options: list[dict[str, str]],
    user_answer: list[str],
    correct_answer: list[str],
    analysis: str,
    knowledge_points: list[str],
) -> str:
    """Explain why an objective answer is wrong.

    The wrong-question book only stores one text field for the reason, so this
    function returns a concise student-facing paragraph that combines the likely
    misconception and a short review suggestion.
    """
    selected = "、".join(user_answer) if user_answer else "未作答"
    correct = "、".join(correct_answer) if correct_answer else "未提供"

    if settings.ai_provider == "mock":
        return (
            f"本题选择为 {selected}，正确答案为 {correct}。"
            "请结合题目解析复习相关知识点。"
        )

    option_lines = []
    for option in options:
        key = str(option.get("key", "")).strip()
        text = str(option.get("text", "")).strip()
        option_analysis = str(option.get("analysis", "")).strip()
        if key and text:
            option_lines.append(f"{key}. {text}；选项解析：{option_analysis}")

    system_prompt = (
        "你是一个软件工程课程错题分析助手。请根据题干、选项解析、正确答案和学生答案，"
        "解释学生错在哪里，并给出简短复习建议。回答必须简洁，适合放入错题本。"
    )
    user_prompt = (
        "题干：\n"
        f"{stem}\n\n"
        "选项：\n"
        f"{chr(10).join(option_lines)}\n\n"
        "学生答案：\n"
        f"{selected}\n\n"
        "正确答案：\n"
        f"{correct}\n\n"
        "题目解析：\n"
        f"{analysis}\n\n"
        "关联知识点：\n"
        f"{', '.join(knowledge_points)}\n\n"
        "请用 1 到 3 句话说明错误原因和复习建议，不要输出 JSON。"
    )
    return llm_service.chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        task="wrong_reason_analysis",
    )


def score_subjective_answer(
    *,
    stem: str,
    reference_answer: list[str],
    analysis: str,
    knowledge_points: list[str],
    user_answer: str,
) -> dict[str, object]:
    """Score a subjective answer with the configured AI provider."""
    normalized_answer = _normalize_text(user_answer)
    if not normalized_answer:
        return {
            "score": 0.0,
            "is_correct": False,
            "analysis": "未提交文字答案，暂无法进行主观题评分。",
            "wrong_reason": "本题未提交可评分文本，请补充作答内容。",
            "matched_points": [],
            "missing_points": reference_answer,
            "misconceptions": [],
        }

    if settings.ai_provider == "mock":
        reference_text = _normalize_text(" ".join(reference_answer))
        hits = sum(
            1 for point in knowledge_points if point and point in normalized_answer
        )
        reference_hit = bool(reference_text and reference_text[:12] in normalized_answer)
        score = 1.0 if reference_hit or hits >= 2 else 0.6 if hits else 0.3
        is_correct = score >= 0.6
        return {
            "score": score,
            "is_correct": is_correct,
            "analysis": "本地模拟评分：根据答案与知识点/参考答案的匹配程度给出分数。",
            "wrong_reason": "" if is_correct else "答案与参考要点匹配较少，请补充关键概念。",
            "matched_points": [
                point for point in knowledge_points if point and point in normalized_answer
            ],
            "missing_points": [
                point for point in knowledge_points if point and point not in normalized_answer
            ],
            "misconceptions": [],
        }

    system_prompt = (
        "你是一个严谨的软件工程课程助教。请只根据题干、参考答案和评分要点评分。"
        "必须返回严格 JSON 对象，不要返回 Markdown、解释文字或代码块。"
    )
    user_prompt = (
        "题干：\n"
        f"{stem}\n\n"
        "参考答案/评分要点：\n"
        f"{'; '.join(reference_answer)}\n\n"
        "题目解析：\n"
        f"{analysis}\n\n"
        "关联知识点：\n"
        f"{', '.join(knowledge_points)}\n\n"
        "学生答案：\n"
        f"{normalized_answer}\n\n"
        "请返回 JSON 对象，字段包括：\n"
        "- score: 0 到 1 之间的小数，表示本题得分。\n"
        "- is_correct: 布尔值，score >= 0.6 时为 true。\n"
        "- analysis: 面向学生的简短评分反馈。\n"
        "- wrong_reason: 若得分不足，说明主要缺漏；若得分较好可为空字符串。\n"
        "- matched_points: 字符串数组，列出学生答案已覆盖的要点。\n"
        "- missing_points: 字符串数组，列出学生答案缺失的要点。\n"
        "- misconceptions: 字符串数组，列出学生答案中的概念误区。\n"
        "评分要鼓励部分正确：只要覆盖部分关键点，就应给出 0 到 1 之间的合理部分分，"
        "不要轻易给 0 分。\n"
        "返回示例："
        "{\"score\":0.35,\"is_correct\":false,\"analysis\":\"...\","
        "\"wrong_reason\":\"...\",\"matched_points\":[\"...\"],"
        "\"missing_points\":[\"...\"],\"misconceptions\":[\"...\"]}"
    )
    content = llm_service.chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        task="subjective_scoring",
        response_format_json=True,
    )
    data = _extract_json_object(content)
    try:
        score = float(data.get("score", 0))
    except (TypeError, ValueError) as exc:
        raise llm_service.LlmServiceError("LLM scoring score must be a number.") from exc

    score = min(max(score, 0.0), 1.0)
    is_correct = bool(data.get("is_correct", score >= 0.6))
    return {
        "score": score,
        "is_correct": is_correct,
        "analysis": str(data.get("analysis", "")).strip() or "AI 已完成主观题评分。",
        "wrong_reason": str(data.get("wrong_reason", "")).strip(),
        "matched_points": _normalize_string_list(data.get("matched_points", [])),
        "missing_points": _normalize_string_list(data.get("missing_points", [])),
        "misconceptions": _normalize_string_list(data.get("misconceptions", [])),
    }


def _normalize_graph_item(raw: object, *, index: int) -> dict[str, object]:
    """Validate and normalize one AI-generated knowledge graph item."""
    if not isinstance(raw, dict):
        raise llm_service.LlmServiceError("Knowledge graph point must be an object.")

    name = str(raw.get("name", "")).strip()
    if not name:
        raise llm_service.LlmServiceError("Knowledge graph point name is empty.")

    try:
        importance_weight = float(raw.get("importance_weight", 0.5))
    except (TypeError, ValueError) as exc:
        raise llm_service.LlmServiceError(
            "Knowledge graph importance_weight must be a number."
        ) from exc

    evidence = raw.get("evidence", [])
    if not isinstance(evidence, list):
        evidence = []

    normalized_evidence: list[dict[str, object]] = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        normalized_evidence.append(
            {
                "material_id": item.get("material_id"),
                "snippet": str(item.get("snippet", "") or "").strip(),
                "relevance_score": item.get("relevance_score", 1.0),
            }
        )

    try:
        level = int(raw.get("level", 1) or 1)
        sort_order = int(raw.get("sort_order", index + 1) or index + 1)
    except (TypeError, ValueError) as exc:
        raise llm_service.LlmServiceError(
            "Knowledge graph level/sort_order must be integers."
        ) from exc

    return {
        "name": name,
        "existing_name": str(raw.get("existing_name", "") or "").strip() or None,
        "description": str(raw.get("description", "") or "").strip(),
        "importance_weight": min(max(importance_weight, 0.0), 1.0),
        "parent_name": str(raw.get("parent_name", "") or "").strip() or None,
        "level": min(max(level, 1), 4),
        "sort_order": sort_order,
        "evidence": normalized_evidence,
    }


def _normalize_graph_merges(raw_merges: object) -> list[dict[str, str]]:
    """Normalize AI-suggested graph merge mappings."""
    if not isinstance(raw_merges, list):
        return []

    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in raw_merges:
        if not isinstance(item, dict):
            continue
        from_name = str(item.get("from_name", "") or "").strip()
        to_name = str(item.get("to_name", "") or "").strip()
        if not from_name or not to_name or from_name == to_name:
            continue
        key = (from_name, to_name)
        if key in seen:
            continue
        seen.add(key)
        normalized.append({"from_name": from_name, "to_name": to_name})
    return normalized


def generate_knowledge_graph(
    *,
    target_title: str,
    subject: str | None,
    materials: list[dict[str, object]],
    max_points: int,
    existing_points: list[dict[str, object]] | None = None,
) -> dict[str, list[dict[str, object]]]:
    """Generate or update a target-level graph from parsed materials."""
    if settings.ai_provider != "mock":
        if len(materials) == 1 and existing_points:
            return _generate_incremental_knowledge_graph_with_real_ai(
                target_title=target_title,
                subject=subject,
                material=materials[0],
                existing_points=existing_points,
                max_points=max_points,
            )
        return _generate_knowledge_graph_with_real_ai(
            target_title=target_title,
            subject=subject,
            materials=materials,
            existing_points=existing_points or [],
            max_points=max_points,
        )

    joined_text = _normalize_text(
        " ".join(str(material.get("parsed_text", "")) for material in materials)
    )
    existing_names = [
        str(point.get("name", "")).strip()
        for point in (existing_points or [])
        if str(point.get("name", "")).strip()
    ]
    extracted_keywords = _extract_mock_keywords(joined_text)
    if len(materials) == 1 and existing_names:
        keywords = extracted_keywords
    else:
        keywords = extracted_keywords + [
            name for name in existing_names if name not in extracted_keywords
        ]
    keywords = keywords[:max_points]
    if not keywords:
        keywords = [target_title or subject or "复习重点"]

    points: list[dict[str, object]] = []
    for index, keyword in enumerate(keywords):
        material = next(
            (
                item
                for item in materials
                if keyword.casefold() in str(item.get("parsed_text", "")).casefold()
            ),
            materials[index % len(materials)],
        )
        material_id = int(material["material_id"])
        snippet = _select_reference_snippet(
            str(material.get("parsed_text", "")),
            keyword,
        )
        existing = next(
            (
                point
                for point in (existing_points or [])
                if str(point.get("name", "")).strip() == keyword
            ),
            {},
        )
        points.append(
            {
                "name": keyword,
                "description": existing.get("description")
                or f"围绕「{keyword}」整理定义、应用场景和常见考法。",
                "importance_weight": existing.get(
                    "importance_weight",
                    max(0.35, 1.0 - index * 0.08),
                ),
                "parent_name": existing.get("parent_name"),
                "level": existing.get("level", 1),
                "sort_order": index + 1,
                "evidence": [
                    {
                        "material_id": material_id,
                        "snippet": snippet or str(material.get("parsed_text", ""))[:120],
                        "relevance_score": 1.0,
                    }
                ],
            }
        )

    return {"points": points, "merges": []}


def _generate_incremental_knowledge_graph_with_real_ai(
    *,
    target_title: str,
    subject: str | None,
    material: dict[str, object],
    existing_points: list[dict[str, object]],
    max_points: int,
) -> dict[str, list[dict[str, object]]]:
    """Extract current-material candidates first, then align them to the graph."""
    material_block = {
        "material_id": material.get("material_id"),
        "title": material.get("title"),
        "parsed_text": _normalize_text(str(material.get("parsed_text", "")))[:4500],
    }
    candidate_system_prompt = (
        "你是一个资料知识点抽取助手。请只根据当前资料抽取知识点，"
        "不要参考已有图谱，也不要为了合并而省略当前资料中的概念。"
        "必须返回严格 JSON 对象，不要返回 Markdown、解释文字或代码块。"
    )
    candidate_user_prompt = (
        "学习目标：\n"
        f"- 标题：{target_title}\n"
        f"- 科目：{subject or '未提供'}\n\n"
        "当前资料 JSON：\n"
        f"{json.dumps(material_block, ensure_ascii=False)}\n\n"
        "请先完整抽取当前资料自己的候选知识点，最多 "
        f"{max_points} 个。返回 JSON 对象，字段为 points。"
        "points 是数组，每个元素包含 name, description, importance_weight, "
        "parent_name, level, sort_order, evidence。"
        "evidence 必须引用当前资料 material_id，snippet 必须来自当前资料内容。"
    )
    candidate_content = llm_service.chat_completion(
        system_prompt=candidate_system_prompt,
        user_prompt=candidate_user_prompt,
        task="knowledge_graph_candidate_extraction",
        timeout_seconds=max(settings.ai_timeout_seconds, 60),
        max_tokens=1800,
        response_format_json=True,
    )
    candidate_data = _extract_json_object(candidate_content)
    raw_candidates = candidate_data.get("points")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise llm_service.LlmServiceError("LLM candidate graph points must be a non-empty list.")
    candidates = [
        _normalize_graph_item(item, index=index)
        for index, item in enumerate(raw_candidates[:max_points])
    ]

    align_system_prompt = (
        "你是一个知识图谱对齐助手。请把当前资料候选知识点与已有图谱对齐，"
        "保留候选知识点覆盖度，同时避免重复节点。必须返回严格 JSON 对象。"
    )
    align_user_prompt = (
        "已有知识图谱 JSON：\n"
        f"{json.dumps(existing_points, ensure_ascii=False)}\n\n"
        "当前资料候选知识点 JSON：\n"
        f"{json.dumps(candidates, ensure_ascii=False)}\n\n"
        "请逐一处理候选知识点："
        "若候选点与已有知识点语义相同，返回该候选点时填写 existing_name 为已有图谱原始 name；"
        "若候选点是新概念，existing_name 为 null 并保留为新增点；"
        "若候选点只是已有知识点的新命名，可在 merges 中声明 from_name 到 to_name。"
        "不得因为候选点可归入某个大类就丢弃它；只有语义相同才合并。"
        "返回 JSON 对象，字段为 points 和 merges。points 最多 "
        f"{max_points} 个，元素字段与候选点一致，并保留当前资料 evidence。"
    )
    align_content = llm_service.chat_completion(
        system_prompt=align_system_prompt,
        user_prompt=align_user_prompt,
        task="knowledge_graph_candidate_alignment",
        timeout_seconds=max(settings.ai_timeout_seconds, 60),
        max_tokens=2200,
        response_format_json=True,
    )
    align_data = _extract_json_object(align_content)
    raw_points = align_data.get("points")
    if not isinstance(raw_points, list) or not raw_points:
        raise llm_service.LlmServiceError("LLM aligned graph points must be a non-empty list.")

    return {
        "points": [
            _normalize_graph_item(item, index=index)
            for index, item in enumerate(raw_points[:max_points])
        ],
        "merges": _normalize_graph_merges(align_data.get("merges", [])),
    }


def _generate_knowledge_graph_with_real_ai(
    *,
    target_title: str,
    subject: str | None,
    materials: list[dict[str, object]],
    max_points: int,
    existing_points: list[dict[str, object]],
) -> dict[str, list[dict[str, object]]]:
    """Ask the configured real LLM to update a target-level knowledge graph."""
    material_blocks = []
    for material in materials:
        material_blocks.append(
            {
                "material_id": material.get("material_id"),
                "title": material.get("title"),
                "parsed_text": _normalize_text(str(material.get("parsed_text", "")))[:2500],
            }
        )
    is_incremental_material = len(material_blocks) == 1 and bool(existing_points)

    system_prompt = (
        "你是一个备考知识图谱维护助手。请根据已有图谱和多份课程资料，更新目标级知识点。"
        "必须返回严格 JSON 对象，不要返回 Markdown、解释文字或代码块。"
    )
    user_prompt = (
        "学习目标：\n"
        f"- 标题：{target_title}\n"
        f"- 科目：{subject or '未提供'}\n\n"
        "已有知识图谱 JSON：\n"
        f"{json.dumps(existing_points, ensure_ascii=False)}\n\n"
        "资料列表 JSON：\n"
        f"{json.dumps(material_blocks, ensure_ascii=False)}\n\n"
        f"刷新模式：{'单资料增量刷新' if is_incremental_material else '目标级资料刷新'}。\n"
        "请在已有知识图谱基础上更新，而不是从零重建。"
        "已有知识点仍然成立时必须复用其原 name，不要仅因措辞不同创建重复节点；"
        + (
            "本轮资料列表只包含当前新/当前资料。请重点判断已有知识点是否被这份资料覆盖："
            "凡是与当前资料实际相关的已有知识点，都应作为 points 返回，并在 evidence 中加入当前资料的 snippet；"
            "只有当前资料确实引入已有图谱没有覆盖的新概念时，才新增知识点。"
            if is_incremental_material
            else ""
        )
        + "可以根据新资料补充新知识点、更新描述、重要度、层级和资料证据。"
        "请优先返回新资料引入的新知识点，以及资料证据或属性需要更新的已有知识点，"
        "不需要机械重复所有没有变化的旧知识点。"
        "如果返回项对应已有知识点，必须增加 existing_name 字段并填写已有图谱中的原始 name；"
        "真正新增的知识点 existing_name 必须为 null。"
        "如果你判断一个旧知识点应被重命名并合并到新名称，请把新名称作为新增/保留点返回，"
        "并在 merges 中声明旧名称到新名称的映射，不要在该新名称 points 项里填写旧 existing_name。"
        "对每个返回知识点都要重新检查资料列表中的每一份资料，"
        "evidence 应列出所有实际相关的资料，而不只是最近上传的资料。"
        "返回的 points 应包含需要新增或更新的知识点，最多 "
        f"{max_points} 个节点。返回 JSON 对象，字段为 points 和 merges。"
        "points 是数组，每个元素包含：\n"
        "- name: 知识点名称。\n"
        "- existing_name: 对应已有知识点的原始名称；新增知识点为 null。\n"
        "- description: 简短说明。\n"
        "- importance_weight: 0 到 1 的重要程度，综合考虑考试常见度、基础依赖关系、资料覆盖篇幅和对后续知识的支撑程度。\n"
        "- parent_name: 父知识点名称，没有则为 null。\n"
        "- level: 层级，一级核心知识为 1，子知识依次递增，最多 4 层。\n"
        "- sort_order: 排序，从 1 开始。\n"
        "- evidence: 数组，每个元素包含 material_id, snippet, relevance_score。\n"
        "evidence 的 material_id 必须来自资料列表，snippet 必须来自资料内容。"
        "merges 是数组，用于声明语义确认相同、需要合并的旧知识点到新知识点映射；"
        "每个元素包含 from_name 和 to_name。from_name 必须来自已有知识图谱，"
        "to_name 必须是本次刷新后应保留的知识点名称。只有在确认二者是同一知识点、"
        "只是命名粒度或措辞变化时才输出；不要把上下位概念、相关但不同的概念合并。"
    )
    content = llm_service.chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        task="knowledge_graph_generation",
        timeout_seconds=max(settings.ai_timeout_seconds, 60),
        max_tokens=2200,
        response_format_json=True,
    )
    data = _extract_json_object(content)
    raw_points = data.get("points")
    if not isinstance(raw_points, list) or not raw_points:
        raise llm_service.LlmServiceError("LLM knowledge graph points must be a non-empty list.")

    return {
        "points": [
            _normalize_graph_item(item, index=index)
            for index, item in enumerate(raw_points[:max_points])
        ],
        "merges": _normalize_graph_merges(data.get("merges", [])),
    }


def generate_review_plan(
    *,
    target_title: str,
    subject: str | None,
    exam_date: str | None,
    review_goal: str | None,
    start_date: str,
    end_date: str,
    dates: list[str],
    focus_items: list[dict[str, object]],
) -> dict[str, object]:
    """Call real AI to generate a review plan from target and wrong-question data."""
    system_prompt = (
        "你是一个备考复习计划助手。请根据课程/考试目标、日期范围和错题薄弱点，"
        "生成可执行的每日复习计划。必须返回严格 JSON 对象，不要返回 Markdown、"
        "解释文字或代码块。"
    )
    user_prompt = (
        "目标信息：\n"
        f"- 标题：{target_title}\n"
        f"- 科目：{subject or '未提供'}\n"
        f"- 考试日期：{exam_date or '未提供'}\n"
        f"- 复习目标：{review_goal or '未提供'}\n\n"
        "计划日期：\n"
        f"- 开始日期：{start_date}\n"
        f"- 结束日期：{end_date}\n"
        f"- 必须覆盖这些日期：{', '.join(dates)}\n\n"
        "薄弱知识点、掌握度和可关联资源：\n"
        f"{json.dumps(focus_items, ensure_ascii=False)}\n\n"
        "返回 JSON 对象，字段包括：\n"
        "- title: 计划标题。\n"
        "- summary: 计划依据摘要，说明如何根据错题/薄弱点安排。\n"
        "- tasks: 数组，长度必须等于日期数量，每个日期必须有且只有一个任务。\n"
        "每个 task 包含 date, title, content, knowledge_point_id, material_id, wrong_question_id。\n"
        "knowledge_point_id、material_id 和 wrong_question_id 只能使用薄弱点列表中已有的值，没有则为 null。\n"
        "content 要具体说明当天怎么复习、看什么、做什么检查。\n"
        "返回示例："
        "{\"title\":\"...\",\"summary\":\"...\",\"tasks\":["
        "{\"date\":\"2026-06-12\",\"title\":\"复习需求分析\","
        "\"content\":\"...\",\"knowledge_point_id\":3,\"material_id\":2,\"wrong_question_id\":1}]}"
    )
    content = llm_service.chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        task="review_plan_generation",
        response_format_json=True,
    )
    data = _extract_json_object(content)
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        raise llm_service.LlmServiceError("LLM review plan tasks must be a list.")

    return {
        "title": str(data.get("title", "")).strip(),
        "summary": str(data.get("summary", "")).strip(),
        "tasks": tasks,
    }
