"""Offline report export. No Office, Node, file inclusions or network requests."""
from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from markdown_it import MarkdownIt


def _inline(paragraph, tokens):
    bold = italic = False
    for token in tokens or []:
        if token.type == "strong_open":
            bold = True
        elif token.type == "strong_close":
            bold = False
        elif token.type == "em_open":
            italic = True
        elif token.type == "em_close":
            italic = False
        elif token.type in {"softbreak", "hardbreak"}:
            paragraph.add_run().add_break()
        elif token.type in {"text", "code_inline", "image"}:
            # Image alt text only; never load a path or URL from model output.
            clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", token.content)
            if not clean:
                continue
            run = paragraph.add_run(clean)
            run.bold, run.italic = (True if bold else None), (True if italic else None)
            if token.type == "code_inline":
                run.font.name = "Consolas"
        # Links retain their visible label, never external relationships.


def build(markdown: str, output: Path, *, header: str = "") -> None:
    if len(markdown) > 2_000_000:
        raise ValueError("отчёт слишком большой для DOCX")
    # Sanitize all fields before parsing, including fences and the running header.
    invalid_xml = r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]"
    markdown = re.sub(invalid_xml, "", markdown)
    header = re.sub(invalid_xml, "", header)
    doc = Document()
    props = doc.core_properties
    props.author = "Blatero"
    props.last_modified_by = "Blatero"
    props.comments = ""
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin = section.bottom_margin = Cm(2)
    section.left_margin = section.right_margin = Cm(2)
    for name in ("Normal", "Title", "Heading 1", "Heading 2", "Heading 3",
                 "Heading 4", "Heading 5", "Heading 6", "Header", "Footer"):
        style = doc.styles[name]
        style.font.name = "Arial"
        style.font.color.rgb = RGBColor(0, 0, 0)
        for border in list(style.element.iter(qn("w:pBdr"))):
            border.getparent().remove(border)
    normal = doc.styles["Normal"]
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.1
    section.header.paragraphs[0].text = header
    footer = section.footer.paragraphs[0]
    footer.alignment = 2
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    tokens = MarkdownIt("commonmark", {"html": False}).enable("table").parse(markdown)
    paragraph = None
    table = row = cell = None
    in_head = False
    lists = []
    list_pending = False
    title_seen = False
    for token in tokens:
        kind = token.type
        if kind in {"bullet_list_open", "ordered_list_open"}:
            lists.append((token.attrGet("start") or 1) if kind == "ordered_list_open" else None)
        elif kind in {"bullet_list_close", "ordered_list_close"}:
            lists.pop()
        elif kind == "list_item_open":
            list_pending = True
        elif kind == "heading_open":
            level = int(token.tag[1])
            style = "Title" if level == 1 and not title_seen else f"Heading {level}"
            paragraph = doc.add_paragraph(style=style)
            title_seen = True
        elif kind == "paragraph_open":
            paragraph = cell.paragraphs[0] if cell is not None else doc.add_paragraph()
            if lists:
                paragraph.paragraph_format.left_indent = Cm(min(len(lists), 8) * .5)
                if list_pending:
                    number = lists[-1]
                    paragraph.add_run("• " if number is None else f"{number}. ")
                    if number is not None:
                        lists[-1] += 1
                    list_pending = False
        elif kind == "inline" and paragraph is not None:
            _inline(paragraph, token.children)
        elif kind in {"fence", "code_block"}:
            paragraph = doc.add_paragraph()
            run = paragraph.add_run(token.content.rstrip())
            run.font.name, run.font.size = "Consolas", Pt(10)
        elif kind == "table_open":
            table = doc.add_table(rows=0, cols=0)
            table.style = "Table Grid"
        elif kind == "thead_open":
            in_head = True
        elif kind == "thead_close":
            in_head = False
        elif kind == "tr_open":
            row = table.add_row()
            if in_head:
                row._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
            index = 0
        elif kind in {"th_open", "td_open"}:
            if index >= len(table.columns):
                table.add_column(Cm(3))
            cell = row.cells[index]
            paragraph = cell.paragraphs[0]
            index += 1
        elif kind in {"th_close", "td_close"}:
            if in_head:
                for run in cell.paragraphs[0].runs:
                    run.bold = True
            cell = None
        elif kind == "table_close":
            columns = len(table.columns)
            if columns:
                table.autofit = False
                for column in table.columns:
                    column.width = Cm(17 / columns)
                for table_row in table.rows:
                    for table_cell in table_row.cells:
                        table_cell.width = Cm(17 / columns)
                        margins = OxmlElement("w:tcMar")
                        for side in ("top", "left", "bottom", "right"):
                            margin = OxmlElement("w:" + side)
                            margin.set(qn("w:w"), "100")
                            margin.set(qn("w:type"), "dxa")
                            margins.append(margin)
                        table_cell._tc.get_or_add_tcPr().append(margins)
            doc.add_paragraph()
            table = None
    output = Path(output)
    doc.save(output)
