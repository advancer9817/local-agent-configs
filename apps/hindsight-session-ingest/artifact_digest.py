"""Convert agent document artifacts into compact Markdown before Hindsight retain.

Generated HTML, Office files and PDFs carry UI chrome, layout XML and repeated
page furniture. Uploading them as-is buries the useful content, so artifacts are
reduced locally to readable Markdown first. Everything here is deterministic:
no model calls and no network. The only derived text is row counts and
min/max/sum or value counts for spreadsheet rows that are not listed.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from html.parser import HTMLParser
import csv
import io
import posixpath
import re
import subprocess
import zipfile
import xml.etree.ElementTree as ET

# Version 2: originals are uploaded and the server parses them, then condenses with an LLM.
DIGEST_VERSION = 2
ARTIFACT_PIPELINE = "server-refine"
MAX_TEXT = 160_000
MAX_EXPANDED = 8_000_000
MAX_TABLE_ROWS = 30
# Generated pages that render content client-side reduce to a few UI words.
MIN_HTML_USEFUL_CHARS = 20
PLAIN_SUFFIXES = {".md", ".txt", ".rst"}
CONVERTED_SUFFIXES = {".html", ".htm", ".pdf", ".docx", ".pptx", ".xlsx", ".csv"}


# ---------------------------------------------------------------- shared helpers

def useful_chars(text):
    return len(re.findall(r"[0-9A-Za-z\u3400-\u9fff]", text))


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _number(value):
    try:
        number = float(str(value).replace(",", ""))
    except ValueError:
        return None
    return number if number == number and abs(number) != float("inf") else None


def _format_number(number):
    if number.is_integer() and abs(number) < 1e15:
        return str(int(number))
    return format(number, ".10g")


def _column_summary(header, body):
    lines = []
    for index, name in enumerate(header):
        values = [row[index] for row in body if row[index]]
        if not values:
            continue
        numbers = [n for n in map(_number, values) if n is not None]
        if len(numbers) >= max(2, 0.8 * len(values)):
            lines.append(f"- {name}：数值 {len(numbers)} 个，最小 {_format_number(min(numbers))}，"
                         f"最大 {_format_number(max(numbers))}，合计 {_format_number(sum(numbers))}")
            continue
        counts = Counter(values)
        if all(re.fullmatch(r"\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2})?", value) for value in values):
            lines.append(f"- {name}：{min(values)} 至 {max(values)}，{len(counts)} 个不同日期")
        elif len(counts) <= 12:
            lines.append(f"- {name}：" + "、".join(f"{key}（{count}）" for key, count in counts.most_common()))
        else:
            lines.append(f"- {name}：{len(counts)} 个不同取值")
    return lines


def table_lines(rows, caption=None, limit=MAX_TABLE_ROWS):
    """Render rows as a Markdown table; long tables keep the head plus column summaries."""
    rows = [[_clean(value).replace("|", "\\|") for value in row] for row in rows]
    rows = [row for row in rows if any(row)]
    if not rows:
        return []
    width = max(len(row) for row in rows)
    used = [i for i in range(width) if any(i < len(row) and row[i] for row in rows)]
    rows = [[row[i] if i < len(row) else "" for i in used] for row in rows]
    lines = ["", caption] if caption else [""]
    if len(used) == 1:
        lines += ["- " + row[0] for row in rows[:limit]]
        if len(rows) > limit:
            lines.append(f"（共 {len(rows)} 行，以上列出前 {limit} 行）")
        return lines + [""]
    header, body = rows[0], rows[1:]
    header = [name or f"列{i + 1}" for i, name in enumerate(header)]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + " --- |" * len(header))
    lines += ["| " + " | ".join(row) + " |" for row in body[:limit]]
    if len(body) > limit:
        lines += ["", f"共 {len(body)} 行数据，以上列出前 {limit} 行。全部行的列摘要："]
        lines += _column_summary(header, body)
    return lines + [""]


def tidy(lines, dedupe=False):
    """Normalize blank lines and drop repeated lines (generated pages repeat labels)."""
    out, seen, fenced = [], set(), False
    for line in lines:
        line = line.rstrip()
        if line.startswith("```"):
            fenced = not fenced
            out.append(line)
            continue
        if fenced:
            out.append(line)
            continue
        if not line.strip():
            if out and out[-1] != "":
                out.append("")
            continue
        table = line.lstrip().startswith("|")
        if not table and out and out[-1] == line:
            continue
        key = re.sub(r"^[#>\-*\s]+", "", line).strip()
        if dedupe and not table and len(key) >= 6:
            if key in seen:
                continue
            seen.add(key)
        if line.startswith("#") and out and out[-1] != "":
            out.append("")
        out.append(line)
    return "\n".join(out).strip()


# ------------------------------------------------------------------------- HTML

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
             "param", "source", "track", "wbr"}
SKIP_TAGS = {"head", "script", "style", "noscript", "template", "button", "select", "option",
             "textarea", "input", "form", "nav", "menu", "dialog", "iframe", "canvas", "object",
             "embed", "footer"}
SKIP_ROLES = {"toolbar", "menu", "menubar", "menuitem", "menuitemradio", "menuitemcheckbox",
              "dialog", "alertdialog", "navigation", "button", "status", "tab", "tablist",
              "search", "tooltip", "contentinfo"}
SKIP_CLASSES = {"no-print", "sr-only", "visually-hidden", "toolbar", "navbar", "breadcrumb",
                "breadcrumbs"}
BLOCK_TAGS = {"p", "div", "section", "article", "main", "header", "aside", "blockquote", "dl",
              "dt", "dd", "figure", "figcaption", "address", "details", "summary", "hr", "body",
              "html", "center", "fieldset", "legend", "caption"}
SVG_IGNORED = {"defs", "marker", "pattern", "clippath", "mask", "symbol", "style", "script",
               "lineargradient", "radialgradient", "filter"}


class _Node:
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = {key: value or "" for key, value in attrs}
        self.children = []


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("#root", [])
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(_Node(tag, attrs))

    def handle_endtag(self, tag):
        # Tolerate unclosed elements: close back to the nearest matching ancestor.
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def _skipped(node):
    attrs = node.attrs
    if node.tag in SKIP_TAGS or attrs.get("aria-hidden") == "true":
        return True
    if set(attrs.get("role", "").split()) & SKIP_ROLES:
        return True
    classes = attrs.get("class", "")
    if set(classes.split()) & SKIP_CLASSES:
        return True
    style = re.sub(r"\s+", "", attrs.get("style", "").lower())
    hidden = "hidden" in attrs or "display:none" in style or "visibility:hidden" in style
    # Inactive tab panels are hidden but still hold real content.
    return hidden and attrs.get("role") != "tabpanel" and not re.search(r"tab|panel|pane", classes)


def _text(node, raw=False):
    if isinstance(node, str):
        return node
    if _skipped(node):
        return ""
    text = "".join(_text(child, raw) for child in node.children)
    return text if raw else _clean(text)


def _find(node, tag, stop=()):
    for child in node.children:
        if isinstance(child, str):
            continue
        if child.tag == tag:
            yield child
        elif child.tag not in stop:
            yield from _find(child, tag, stop)


def _html_rows(table):
    rows = []
    for row in _find(table, "tr", stop=("table",)):
        cells = []
        for cell in row.children:
            if not isinstance(cell, str) and cell.tag in ("td", "th"):
                cells.append(_text(cell))
                span = cell.attrs.get("colspan", "1")
                cells += [""] * (min(int(span), 50) - 1 if span.isdigit() and int(span) > 1 else 0)
        rows.append(cells)
    return rows


def _svg_lines(svg):
    """Keep diagram labels and, when nodes/edges are annotated, the graph itself."""
    texts, captions, nodes, edges = [], [], {}, []

    def walk(node):
        if isinstance(node, str) or node.tag in SVG_IGNORED or node.attrs.get("aria-hidden") == "true":
            return
        attrs = node.attrs
        if attrs.get("data-node-id") and attrs.get("data-node-label"):
            nodes.setdefault(attrs["data-node-id"], (attrs["data-node-label"], attrs.get("data-node-sublabel", "")))
            return
        if attrs.get("data-edge-from") and attrs.get("data-edge-to"):
            edge = (attrs["data-edge-from"], attrs["data-edge-to"], attrs.get("data-edge-label", ""))
            if edge not in edges:
                edges.append(edge)
        if node.tag in ("text", "title", "desc"):
            value = _clean("".join(_text(child, raw=True) for child in node.children))
            if value:
                (texts if node.tag == "text" else captions).append(value)
            return
        for child in node.children:
            walk(child)

    walk(svg)
    # With an annotated graph, loose labels (edge captions, legends) are redundant.
    lines = list(dict.fromkeys(captions + ([] if nodes else texts)))
    if nodes:
        lines += ["", "图中组件："]
        lines += [f"- {label}" + (f"：{sub}" if sub else "") for label, sub in nodes.values()]
    if edges:
        name = lambda key: nodes.get(key, (key, ""))[0]
        lines += ["", "图中关系："]
        lines += [f"- {name(a)} → {name(b)}" + (f"：{label}" if label else "") for a, b, label in edges]
    return lines + [""]


class _HTMLRenderer:
    def __init__(self):
        self.lines, self.inline, self.prefix, self.depth = [], [], "", 0

    def flush(self):
        text = _clean("".join(self.inline))
        self.inline = []
        if text:
            self.lines.append(self.prefix + text)
            self.prefix = ""

    def children(self, node):
        for child in node.children:
            self.render(child)

    def render(self, node):
        if isinstance(node, str):
            self.inline.append(node)
            return
        if _skipped(node):
            return
        tag = node.tag
        if tag == "svg":
            self.flush()
            self.lines += _svg_lines(node)
        elif re.fullmatch(r"h[1-6]", tag):
            self.flush()
            text = _text(node)
            if text:
                self.lines.append("#" * int(tag[1]) + " " + text)
        elif tag == "table":
            self.flush()
            self.lines += table_lines(_html_rows(node))
        elif tag == "pre":
            self.flush()
            text = _text(node, raw=True).strip("\n")
            if text.strip():
                self.lines += ["```", *text.splitlines(), "```"]
        elif tag == "br":
            self.flush()
        elif tag == "img":
            alt = _clean(node.attrs.get("alt"))
            if alt:
                self.inline.append(f"[图片：{alt}]")
        elif tag == "li":
            self.flush()
            self.prefix = "  " * max(self.depth - 1, 0) + "- "
            self.children(node)
            self.flush()
            self.prefix = ""
        elif tag in ("ul", "ol"):
            self.flush()
            self.depth += 1
            self.children(node)
            self.flush()
            self.depth -= 1
        elif tag in BLOCK_TAGS:
            self.flush()
            self.children(node)
            self.flush()
        else:
            self.children(node)


def html_lines(text):
    builder = _TreeBuilder()
    builder.feed(text)
    builder.close()
    title = next((_text(node) for node in _find(builder.root, "title", stop=("svg", "body"))), "")
    renderer = _HTMLRenderer()
    renderer.render(builder.root)
    renderer.flush()
    return (["# " + title] if title else []) + renderer.lines


# ------------------------------------------------------------------ Office XML

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
}
A, P, R, W, S = ("{%s}" % NS[key] for key in ("a", "p", "r", "w", "s"))


class _Package:
    """Bounded reader for an OOXML zip package."""

    def __init__(self, path):
        self.archive = zipfile.ZipFile(path)
        self.names = set(self.archive.namelist())
        self.used = 0

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.archive.close()

    def xml(self, name):
        if name not in self.names:
            return None
        info = self.archive.getinfo(name)
        self.used += info.file_size
        if self.used > MAX_EXPANDED:
            raise ValueError("Expanded document too large")
        with self.archive.open(info) as handle:
            data = handle.read(MAX_EXPANDED + 1)
        if len(data) > MAX_EXPANDED:
            raise ValueError("Expanded document too large")
        return ET.fromstring(data)

    def rels(self, part):
        folder = posixpath.dirname(part)
        root = self.xml(posixpath.join(folder, "_rels", posixpath.basename(part) + ".rels"))
        result = {}
        for rel in [] if root is None else root:
            target = rel.get("Target", "")
            if rel.get("TargetMode") == "External" or not target:
                continue
            path = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join(folder, target))
            result[rel.get("Id")] = (path, rel.get("Type", ""))
        return result

    def title(self):
        root = self.xml("docProps/core.xml")
        node = None if root is None else root.find("{http://purl.org/dc/elements/1.1/}title")
        return _clean(node.text) if node is not None else ""


def _joined(element, text_tag):
    return _clean("".join(node.text or "" for node in element.iter(text_tag)))


def _drawing_table(table):
    return [[_joined(cell, A + "t") for cell in row.iter(A + "tc")] for row in table.iter(A + "tr")]


def pptx_lines(package):
    order = []
    presentation = package.xml("ppt/presentation.xml")
    if presentation is not None:
        rels = package.rels("ppt/presentation.xml")
        for slide in presentation.iter(P + "sldId"):
            target = rels.get(slide.get(R + "id"))
            if target:
                order.append(target[0])
    if not order:
        number = lambda name: int(re.search(r"(\d+)\.xml$", name).group(1))
        order = sorted((name for name in package.names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)), key=number)
    lines, first_title = [], ""
    for index, part in enumerate(order, 1):
        slide = package.xml(part)
        if slide is None or slide.get("show") == "0":
            continue
        title, body = "", []
        tree = slide.find(f"{P}cSld/{P}spTree")
        for element in [] if tree is None else tree.iter():
            if element.tag == P + "sp":
                placeholder = element.find(f"{P}nvSpPr/{P}nvPr/{P}ph")
                kind = placeholder.get("type", "") if placeholder is not None else ""
                if kind in ("sldNum", "dt", "ftr"):
                    continue
                text_body = element.find(P + "txBody")
                paragraphs = [] if text_body is None else text_body.findall(A + "p")
                if kind in ("title", "ctrTitle") and not title:
                    title = " ".join(filter(None, (_joined(p, A + "t") for p in paragraphs)))
                    continue
                for paragraph in paragraphs:
                    text = _joined(paragraph, A + "t")
                    if text:
                        props = paragraph.find(A + "pPr")
                        level = int(props.get("lvl", "0")) if props is not None and props.get("lvl", "0").isdigit() else 0
                        body.append("  " * level + "- " + text)
            elif element.tag == A + "tbl":
                body += table_lines(_drawing_table(element))
            elif element.tag == P + "pic":
                props = element.find(f"{P}nvPicPr/{P}cNvPr")
                description = _clean(props.get("descr")) if props is not None else ""
                if description:
                    body.append(f"- [图片：{description}]")
        notes = []
        for path, kind in package.rels(part).values():
            if kind.endswith("/notesSlide"):
                root = package.xml(path)
                for shape in [] if root is None else root.iter(P + "sp"):
                    placeholder = shape.find(f"{P}nvSpPr/{P}nvPr/{P}ph")
                    if placeholder is not None and placeholder.get("type") == "body":
                        notes += [t for t in (_joined(p, A + "t") for p in shape.iter(A + "p")) if t]
        if not (title or body or notes):
            continue
        first_title = first_title or title
        lines.append(f"## 第 {index} 页" + (f"：{title}" if title else ""))
        lines += body
        if notes:
            lines.append("备注：" + " ".join(notes))
    document_title = package.title() or first_title
    return (["# " + document_title] if document_title else []) + lines


def docx_lines(package):
    styles = {}
    style_root = package.xml("word/styles.xml")
    for style in [] if style_root is None else style_root.iter(W + "style"):
        name = style.find(W + "name")
        if style.get(W + "styleId") and name is not None:
            styles[style.get(W + "styleId")] = (name.get(W + "val") or "").lower()
    document = package.xml("word/document.xml")
    if document is None:
        raise ValueError("Missing word/document.xml")

    def paragraph_text(paragraph):
        parts = []
        for node in paragraph.iter():
            if node.tag == W + "t":
                parts.append(node.text or "")
            elif node.tag in (W + "tab", W + "br", W + "cr"):
                parts.append(" ")
        return _clean("".join(parts))

    def paragraph_line(paragraph):
        text = paragraph_text(paragraph)
        props = paragraph.find(W + "pPr")
        if not text or props is None:
            return text
        style = props.find(W + "pStyle")
        style_id = style.get(W + "val", "") if style is not None else ""
        name = styles.get(style_id, style_id.lower())
        match = re.match(r"(?:heading|标题)\s*(\d)", name)
        outline = props.find(W + "outlineLvl")
        if name == "title":
            return "# " + text
        if match:
            return "#" * min(int(match.group(1)) + 1, 6) + " " + text
        if outline is not None and outline.get(W + "val", "").isdigit() and int(outline.get(W + "val")) < 6:
            return "#" * (int(outline.get(W + "val")) + 2) + " " + text
        numbering = props.find(W + "numPr")
        if numbering is not None:
            level = numbering.find(W + "ilvl")
            depth = int(level.get(W + "val", "0")) if level is not None and level.get(W + "val", "0").isdigit() else 0
            return "  " * depth + "- " + text
        return text

    lines = []

    def walk(container):
        for child in container:
            if child.tag == W + "p":
                lines.append(paragraph_line(child))
            elif child.tag == W + "tbl":
                lines.extend(table_lines([[" ".join(filter(None, map(paragraph_text, cell.iter(W + "p"))))
                                           for cell in row.findall(W + "tc")] for row in child.findall(W + "tr")]))
            elif child.tag in (W + "sdt", W + "sdtContent", W + "customXml"):
                walk(child)

    body = document.find(W + "body")
    walk([] if body is None else body)
    title = package.title()
    # Body headings are shifted one level so the document title stays the only H1.
    return (["# " + title] if title else []) + lines


DATE_FORMAT_IDS = set(range(14, 23)) | {45, 46, 47}


def _column_index(reference):
    match = re.match(r"([A-Z]+)", reference or "")
    if not match:
        return None
    index = 0
    for letter in match.group(1):
        index = index * 26 + ord(letter) - 64
    return index - 1


def xlsx_lines(package):
    workbook = package.xml("xl/workbook.xml")
    if workbook is None:
        raise ValueError("Missing xl/workbook.xml")
    properties = workbook.find(S + "workbookPr")
    epoch = datetime(1904, 1, 1) if properties is not None and properties.get("date1904") in ("1", "true") \
        else datetime(1899, 12, 30)
    shared = []
    strings = package.xml("xl/sharedStrings.xml")
    for item in [] if strings is None else strings.findall(S + "si"):
        # Phonetic runs (rPh) are reading aids, not cell text.
        shared.append("".join(node.text or "" for child in item if child.tag in (S + "t", S + "r")
                              for node in child.iter(S + "t")))
    date_styles = set()
    styles = package.xml("xl/styles.xml")
    if styles is not None:
        custom = {f.get("numFmtId"): f.get("formatCode", "") for f in styles.iter(S + "numFmt")}
        formats = styles.find(S + "cellXfs")
        for index, xf in enumerate([] if formats is None else formats.findall(S + "xf")):
            identifier = xf.get("numFmtId", "0")
            code = re.sub(r'"[^"]*"|\[[^\]]*]|\\.', "", custom.get(identifier, ""))
            if (identifier.isdigit() and int(identifier) in DATE_FORMAT_IDS) or re.search(r"[yd]", code, re.I):
                date_styles.add(str(index))

    def cell_value(cell):
        kind = cell.get("t", "n")
        value = cell.find(S + "v")
        raw = value.text if value is not None and value.text is not None else ""
        if kind == "s":
            return shared[int(raw)] if raw.isdigit() and int(raw) < len(shared) else ""
        if kind == "inlineStr":
            node = cell.find(S + "is")
            return "" if node is None else "".join(t.text or "" for t in node.iter(S + "t"))
        if kind == "b":
            return "TRUE" if raw == "1" else "FALSE"
        number = _number(raw) if kind == "n" else None
        if number is None:
            return raw
        if cell.get("s") in date_styles and 0 < number < 2958466:
            moment = epoch + timedelta(days=number)
            return moment.strftime("%Y-%m-%d %H:%M" if number % 1 else "%Y-%m-%d")
        return _format_number(number)

    rels = package.rels("xl/workbook.xml")
    lines = []
    for sheet in workbook.iter(S + "sheet"):
        if sheet.get("state") in ("hidden", "veryHidden"):
            continue
        target = rels.get(sheet.get(R + "id"))
        root = package.xml(target[0]) if target else None
        if root is None:
            continue
        rows = []
        for row in root.iter(S + "row"):
            values = {}
            for position, cell in enumerate(row.findall(S + "c")):
                column = _column_index(cell.get("r"))
                values[position if column is None else column] = cell_value(cell)
            if any(_clean(v) for v in values.values()):
                rows.append([values.get(i, "") for i in range(max(values) + 1)])
        if not rows:
            continue
        width = len([i for i in range(max(map(len, rows))) if any(i < len(r) and _clean(r[i]) for r in rows)])
        lines += table_lines(rows, caption=f"## 工作表：{sheet.get('name', '')}（{len(rows)} 行 × {width} 列）")
    title = package.title()
    return (["# " + title] if title else []) + lines


# ------------------------------------------------------------------ PDF and CSV

PAGE_NUMBER = re.compile(r"^(?:第\s*\d+\s*页(?:\s*/\s*共\s*\d+\s*页)?|\d+\s*(?:/\s*\d+)?|-\s*\d+\s*-|page\s+\d+(?:\s+of\s+\d+)?)$", re.I)


def _pdf_text(path):
    try:
        result = subprocess.run(["pdftotext", "-enc", "UTF-8", str(path), "-"],
                                capture_output=True, timeout=30, check=True)
        return result.stdout.decode("utf-8", errors="replace")
    except FileNotFoundError:
        pass
    try:
        # The Hindsight server venv ships pdfminer (a markitdown dependency).
        from pdfminer.high_level import extract_text
    except ImportError as error:
        raise ValueError("pdftotext or pdfminer is required for PDF") from error
    return extract_text(str(path))


def pdf_lines(path):
    text = _pdf_text(path)
    if len(text) > MAX_TEXT * 4:
        raise ValueError("Document text too large")
    pages = [page for page in text.split("\f") if page.strip()]
    counts = Counter(line for page in pages for line in {l.strip() for l in page.splitlines() if l.strip()})
    # Lines on most pages are running headers or footers.
    repeated = {line for line, count in counts.items()
                if len(pages) >= 3 and count >= max(3, len(pages) * 0.5) and len(line) <= 80}
    lines = []
    for page in pages:
        lines += [l.strip() for l in page.splitlines()
                  if l.strip() not in repeated and not PAGE_NUMBER.match(l.strip())]
        lines.append("")
    return lines


def csv_lines(text):
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",\t;|")
    except csv.Error:
        dialect = csv.excel
    return table_lines(list(csv.reader(io.StringIO(text), dialect)))


# --------------------------------------------------------------------- entry

def digest_document(path):
    """Return compact Markdown for an artifact, or "" when nothing worth keeping remains."""
    suffix = path.suffix.lower()
    if suffix in (".docx", ".pptx", ".xlsx"):
        with _Package(path) as package:
            lines = {".docx": docx_lines, ".pptx": pptx_lines, ".xlsx": xlsx_lines}[suffix](package)
        text = tidy(lines, dedupe=suffix == ".pptx")
    elif suffix == ".pdf":
        text = tidy(pdf_lines(path))
    else:
        raw = path.read_bytes()
        if b"\0" in raw:
            raise ValueError("Binary document")
        source = raw.decode("utf-8-sig", errors="strict")
        if suffix in (".html", ".htm"):
            text = tidy(html_lines(source), dedupe=True)
        elif suffix == ".csv":
            text = tidy(csv_lines(source))
        else:
            text = source.strip()
    if len(text) > MAX_TEXT:
        raise ValueError("Document text too large")
    if suffix in (".html", ".htm") and useful_chars(text) < MIN_HTML_USEFUL_CHARS:
        return ""
    return text
