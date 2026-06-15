import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material import Material
from app.models.material_structure import (
    MaterialChunk,
    MaterialChunkType,
    MaterialFigure,
    MaterialFormula,
    MaterialSection,
    MaterialTable,
)
from app.models.user import User
from app.repositories.material_structure_repository import MaterialStructureRepository
from app.services.material_service import MaterialService


class MaterialStructureService:
    """从 parsed_text 生成章节和 chunks 的 MVP 结构化解析服务。"""

    max_chunk_chars = 1200
    default_section_title = "全文"
    section_patterns = [
        re.compile(r"^#{1,6}\s+(.+)$"),
        re.compile(r"^(第[一二三四五六七八九十百千万0-9]+[章节篇单元][：:\s]?.*)$"),
        re.compile(r"^(\d+(?:\.\d+){0,3}[、.)\s]+.{2,80})$"),
        re.compile(r"^(\d+(?:\.\d+){1,3}\s*[A-Z][A-Za-z0-9 _:/-]{2,80})$"),
    ]
    formula_label_pattern = re.compile(r"^(公式|方程|表达式|推导)[：:]")
    formula_symbol_pattern = re.compile(r"(≈|≤|≥|≠|√|∑|∫|\^|\\frac|\\sqrt)")
    formula_operator_pattern = re.compile(r"([A-Za-z0-9)\]}]\s*[+\-*/=]\s*[A-Za-z0-9({\[])")
    grammar_production_pattern = re.compile(r"^\s*\S{1,20}\s*(->|→|⇒|::=)\s*\S+")
    definition_keywords = ("定义", "概念", "称为", "是指", "叫做")
    example_keywords = ("例题", "例 ", "例：", "例:", "练习", "题目", "解：")
    key_sentence_keywords = ("重点", "注意", "必须", "核心", "关键", "考点", "结论")
    labeled_block_pattern = re.compile(
        r"(?ms)^(图片说明|图形说明|表格|公式)：\s*\n?(.*?)(?=^\S+：\s*$|\Z)"
    )

    @staticmethod
    def _normalize_lines(parsed_text: str) -> list[str]:
        return [line.strip() for line in parsed_text.replace("\r\n", "\n").split("\n")]

    @staticmethod
    def _match_section_title(line: str) -> tuple[str, int] | None:
        if not line or len(line) > 120:
            return None

        markdown_match = MaterialStructureService.section_patterns[0].match(line)
        if markdown_match:
            level = min(line.count("#", 0, line.find(" ")), 6)
            return markdown_match.group(1).strip(), level

        for pattern in MaterialStructureService.section_patterns[1:]:
            match = pattern.match(line)
            if match:
                title = match.group(1).strip()
                level = 1 if title.startswith("第") else title.split()[0].count(".") + 1
                return title, level

        return None

    @staticmethod
    def _split_long_text(text: str) -> list[str]:
        if len(text) <= MaterialStructureService.max_chunk_chars:
            return [text]

        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + MaterialStructureService.max_chunk_chars, len(text))
            if end < len(text):
                boundary = text.rfind("。", start, end)
                if boundary <= start:
                    boundary = text.rfind("\n", start, end)
                if boundary > start:
                    end = boundary + 1
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end

        return chunks

    @staticmethod
    def _classify_chunk(text: str) -> MaterialChunkType:
        compact = text.strip()
        if any(keyword in compact for keyword in MaterialStructureService.example_keywords):
            return MaterialChunkType.example
        if any(keyword in compact for keyword in MaterialStructureService.definition_keywords):
            return MaterialChunkType.definition
        if MaterialStructureService._is_formula_like(compact):
            return MaterialChunkType.formula
        if any(keyword in compact for keyword in MaterialStructureService.key_sentence_keywords):
            return MaterialChunkType.key_sentence
        return MaterialChunkType.text

    @staticmethod
    def _is_formula_like(text: str) -> bool:
        """Heuristically detect standalone formulas without tagging mixed prose.

        A pure regex cannot fully understand slides, code snippets, grammar rules,
        and math. This intentionally favors precision over recall: long prose that
        merely contains an operator stays text, while short symbolic blocks and
        labeled formulas become formula chunks.
        """
        compact = text.strip()
        if not compact:
            return False
        if MaterialStructureService.formula_label_pattern.match(compact):
            return True

        lines = [line.strip() for line in compact.splitlines() if line.strip()]
        if not lines:
            return False

        formula_lines = sum(
            1 for line in lines if MaterialStructureService._is_formula_line(line)
        )
        if len(lines) >= 2:
            return formula_lines / len(lines) >= 0.6

        return len(compact) <= 260 and formula_lines == 1

    @staticmethod
    def _is_formula_line(line: str) -> bool:
        if MaterialStructureService.formula_symbol_pattern.search(line):
            return True
        if MaterialStructureService.grammar_production_pattern.search(line):
            return True
        if not MaterialStructureService.formula_operator_pattern.search(line):
            return False

        words = re.findall(r"[A-Za-z\u4e00-\u9fff]{2,}", line)
        symbol_chars = sum(1 for char in line if char in "=+-*/^()[]{}<>→⇒≈≤≥≠√∑∫|")
        symbolic_ratio = symbol_chars / max(len(line), 1)

        return len(line) <= 180 and len(words) <= 12 and symbolic_ratio >= 0.05

    @staticmethod
    def _split_labeled_items(text: str) -> list[str]:
        return [
            item.strip(" \n-•*")
            for item in text.splitlines()
            if item.strip(" \n-•*")
        ]

    @staticmethod
    def _extract_structured_items(
        material: Material,
        default_section: MaterialSection | None,
    ) -> tuple[list[MaterialFigure], list[MaterialTable], list[MaterialFormula]]:
        parsed_text = material.parsed_text or ""
        figures: list[MaterialFigure] = []
        tables: list[MaterialTable] = []
        formulas: list[MaterialFormula] = []

        for match in MaterialStructureService.labeled_block_pattern.finditer(parsed_text):
            label = match.group(1)
            content = match.group(2).strip()
            if not content:
                continue

            section = default_section
            section_id = section.id if section is not None and section.id is not None else None
            if label in {"图片说明", "图形说明"}:
                for item in MaterialStructureService._split_labeled_items(content):
                    figures.append(
                        MaterialFigure(
                            material_id=material.id,
                            section_id=section_id,
                            title=label,
                            description=item,
                            order_index=len(figures) + 1,
                        )
                    )
            elif label == "表格":
                tables.append(
                    MaterialTable(
                        material_id=material.id,
                        section_id=section_id,
                        title=label,
                        content=content,
                        order_index=len(tables) + 1,
                    )
                )
            elif label == "公式":
                for item in MaterialStructureService._split_labeled_items(content):
                    formulas.append(
                        MaterialFormula(
                            material_id=material.id,
                            section_id=section_id,
                            expression=item,
                            explanation=None,
                            order_index=len(formulas) + 1,
                        )
                    )

        return figures, tables, formulas

    @staticmethod
    def _build_structure(
        material: Material,
    ) -> tuple[list[MaterialSection], list[MaterialChunk], list[MaterialFigure], list[MaterialTable], list[MaterialFormula]]:
        parsed_text = (material.parsed_text or "").strip()
        if not parsed_text:
            return [], [], [], [], []

        sections: list[MaterialSection] = []
        chunk_specs: list[tuple[MaterialSection, str, int]] = []
        current_section: MaterialSection | None = None
        paragraph_lines: list[str] = []
        section_order = 0

        def ensure_default_section() -> MaterialSection:
            nonlocal current_section, section_order
            if current_section is None:
                section_order += 1
                current_section = MaterialSection(
                    material_id=material.id,
                    title=MaterialStructureService.default_section_title,
                    level=1,
                    order_index=section_order,
                )
                sections.append(current_section)
            return current_section

        def flush_paragraph() -> None:
            if not paragraph_lines:
                return
            section = ensure_default_section()
            paragraph = "\n".join(paragraph_lines).strip()
            paragraph_lines.clear()
            if paragraph:
                for text in MaterialStructureService._split_long_text(paragraph):
                    chunk_specs.append((section, text, len(chunk_specs) + 1))

        for line in MaterialStructureService._normalize_lines(parsed_text):
            title_match = MaterialStructureService._match_section_title(line)
            if title_match is not None:
                flush_paragraph()
                section_order += 1
                title, level = title_match
                current_section = MaterialSection(
                    material_id=material.id,
                    title=title,
                    level=level,
                    order_index=section_order,
                )
                sections.append(current_section)
                continue

            if not line:
                flush_paragraph()
                continue

            paragraph_lines.append(line)

        flush_paragraph()

        if not chunk_specs and parsed_text:
            section = ensure_default_section()
            for text in MaterialStructureService._split_long_text(parsed_text):
                chunk_specs.append((section, text, len(chunk_specs) + 1))

        chunks = [
            MaterialChunk(
                material_id=material.id,
                section=section,
                chunk_type=MaterialStructureService._classify_chunk(text),
                title=MaterialStructureService._chunk_title(section),
                text=text,
                order_index=order_index,
            )
            for section, text, order_index in chunk_specs
        ]
        default_section = sections[0] if sections else None
        figures, tables, formulas = MaterialStructureService._extract_structured_items(
            material,
            default_section,
        )
        return sections, chunks, figures, tables, formulas

    @staticmethod
    def _chunk_title(section: MaterialSection) -> str | None:
        if section.title == MaterialStructureService.default_section_title:
            return None
        return section.title

    @staticmethod
    async def rebuild_for_material(
        db: AsyncSession,
        *,
        material: Material,
    ) -> tuple[
        list[MaterialSection],
        list[MaterialChunk],
        list[MaterialFigure],
        list[MaterialTable],
        list[MaterialFormula],
    ]:
        sections, chunks, figures, tables, formulas = MaterialStructureService._build_structure(material)
        return await MaterialStructureRepository.replace_for_material(
            db,
            material_id=material.id,
            sections=sections,
            chunks=chunks,
            figures=figures,
            tables=tables,
            formulas=formulas,
        )

    @staticmethod
    async def clear_for_material(
        db: AsyncSession,
        *,
        material_id: int,
    ) -> None:
        await MaterialStructureRepository.clear_for_material(db, material_id=material_id)

    @staticmethod
    async def list_sections(
        db: AsyncSession,
        *,
        current_user: User,
        material_id: int,
    ) -> list[MaterialSection]:
        await MaterialService.get_detail(db, current_user=current_user, material_id=material_id)
        return await MaterialStructureRepository.list_sections_by_material(db, material_id=material_id)

    @staticmethod
    async def list_chunks(
        db: AsyncSession,
        *,
        current_user: User,
        material_id: int,
        section_id: int | None = None,
    ) -> list[MaterialChunk]:
        await MaterialService.get_detail(db, current_user=current_user, material_id=material_id)
        return await MaterialStructureRepository.list_chunks_by_material(
            db,
            material_id=material_id,
            section_id=section_id,
        )

    @staticmethod
    async def list_figures(
        db: AsyncSession,
        *,
        current_user: User,
        material_id: int,
    ) -> list[MaterialFigure]:
        await MaterialService.get_detail(db, current_user=current_user, material_id=material_id)
        return await MaterialStructureRepository.list_figures_by_material(db, material_id=material_id)

    @staticmethod
    async def list_tables(
        db: AsyncSession,
        *,
        current_user: User,
        material_id: int,
    ) -> list[MaterialTable]:
        await MaterialService.get_detail(db, current_user=current_user, material_id=material_id)
        return await MaterialStructureRepository.list_tables_by_material(db, material_id=material_id)

    @staticmethod
    async def list_formulas(
        db: AsyncSession,
        *,
        current_user: User,
        material_id: int,
    ) -> list[MaterialFormula]:
        await MaterialService.get_detail(db, current_user=current_user, material_id=material_id)
        return await MaterialStructureRepository.list_formulas_by_material(db, material_id=material_id)

    @staticmethod
    async def list_target_chunks(
        db: AsyncSession,
        *,
        current_user: User,
        target_id: int,
        limit: int,
    ) -> list[MaterialChunk]:
        from app.services.study_target_service import StudyTargetService

        await StudyTargetService.get_detail(db, current_user=current_user, target_id=target_id)
        return await MaterialStructureRepository.list_chunks_by_target(
            db,
            user_id=current_user.id,
            target_id=target_id,
            limit=limit,
        )
