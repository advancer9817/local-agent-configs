"""Run: python3 -m unittest test_artifact_digest (stdlib only)."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import time
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from artifact_digest import digest_document  # noqa: E402
import session_documents  # noqa: E402

NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"

HTML = """<!doctype html><html><head><title>部署说明</title><style>.x{}</style>
<script>var secret = "ignored";</script></head><body>
<div class="toolbar" role="toolbar"><button>导出 PNG</button><button>深色</button></div>
<nav><a href="#">首页</a></nav>
<div hidden>隐藏的弹层文字</div>
<h1>部署说明</h1><p>服务运行在 <b>18888</b> 端口，通过 SSH 隧道访问。</p>
<ul><li>备份目录 /data/backup</li><li>每日 03:00 执行</li></ul>
<div class="tab-panel" hidden><h2>回滚</h2><p>使用上一版二进制回滚。</p></div>
<table><tr><th>组件</th><th>版本</th></tr><tr><td>CPA</td><td>8.0.33</td></tr></table>
<svg><defs><marker id="m"><text>ignored</text></marker></defs>
<g data-node-id="a" data-node-label="客户端" data-node-sublabel="Codex"><text>客户端</text></g>
<g data-node-id="b" data-node-label="服务端"><text>服务端</text></g>
<path data-edge-from="a" data-edge-to="b" data-edge-label="REST"/><text>REST</text></svg>
<p>服务运行在 18888 端口，通过 SSH 隧道访问。</p>
</body></html>"""


def write_zip(path, files):
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)


def pptx(path):
    def shape(kind, paragraphs):
        ph = f'<p:ph type="{kind}"/>' if kind else ""
        paras = "".join(f'<a:p><a:pPr lvl="{lvl}"/><a:r><a:t>{text}</a:t></a:r></a:p>' for lvl, text in paragraphs)
        return (f'<p:sp><p:nvSpPr><p:cNvPr id="1" name="s"/><p:cNvSpPr/><p:nvPr>{ph}</p:nvPr></p:nvSpPr>'
                f'<p:txBody>{paras}</p:txBody></p:sp>')

    def slide(shapes, show=""):
        return (f'<p:sld xmlns:a="{NS_A}" xmlns:p="{NS_P}" xmlns:r="{NS_R}"{show}><p:cSld><p:spTree>'
                + "".join(shapes) + "</p:spTree></p:cSld></p:sld>")

    table = ('<p:graphicFrame><a:graphic><a:graphicData><a:tbl>'
             '<a:tr><a:tc><a:txBody><a:p><a:r><a:t>指标</a:t></a:r></a:p></a:txBody></a:tc>'
             '<a:tc><a:txBody><a:p><a:r><a:t>值</a:t></a:r></a:p></a:txBody></a:tc></a:tr>'
             '<a:tr><a:tc><a:txBody><a:p><a:r><a:t>文档数</a:t></a:r></a:p></a:txBody></a:tc>'
             '<a:tc><a:txBody><a:p><a:r><a:t>213</a:t></a:r></a:p></a:txBody></a:tc></a:tr>'
             '</a:tbl></a:graphicData></a:graphic></p:graphicFrame>')
    write_zip(path, {
        "ppt/presentation.xml": f'<p:presentation xmlns:p="{NS_P}" xmlns:r="{NS_R}"><p:sldIdLst>'
                                '<p:sldId id="256" r:id="rId2"/><p:sldId id="257" r:id="rId1"/>'
                                '<p:sldId id="258" r:id="rId3"/></p:sldIdLst></p:presentation>',
        "ppt/_rels/presentation.xml.rels": f'<Relationships xmlns="{REL}">'
            '<Relationship Id="rId1" Type="x/slide" Target="slides/slide1.xml"/>'
            '<Relationship Id="rId2" Type="x/slide" Target="slides/slide2.xml"/>'
            '<Relationship Id="rId3" Type="x/slide" Target="slides/slide3.xml"/></Relationships>',
        # slide2 is first in presentation order.
        "ppt/slides/slide2.xml": slide([shape("ctrTitle", [(0, "季度汇报")]), shape("sldNum", [(0, "1")])]),
        "ppt/slides/slide1.xml": slide([shape("title", [(0, "核心指标")]),
                                        shape("body", [(0, "压缩完成"), (1, "8.3 倍")]), table]),
        "ppt/slides/_rels/slide1.xml.rels": f'<Relationships xmlns="{REL}">'
            '<Relationship Id="rId9" Type="x/notesSlide" Target="../notesSlides/notesSlide1.xml"/></Relationships>',
        "ppt/notesSlides/notesSlide1.xml": slide([shape("body", [(0, "强调 QAI 合并")])]).replace("p:sld ", "p:notes ").replace("</p:sld>", "</p:notes>"),
        "ppt/slides/slide3.xml": slide([shape("title", [(0, "隐藏页")])], show=' show="0"'),
    })


def docx(path):
    def para(text, style=None, num=False):
        props = (f'<w:pStyle w:val="{style}"/>' if style else "") + ('<w:numPr><w:ilvl w:val="0"/></w:numPr>' if num else "")
        return f'<w:p><w:pPr>{props}</w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>'
    cell = lambda text: f"<w:tc>{para(text)}</w:tc>"
    write_zip(path, {
        "word/document.xml": f'<w:document xmlns:w="{NS_W}"><w:body>' + para("迁移方案", "Title")
            + para("背景", "Heading1") + para("旧机器下线。") + para("第一步", num=True)
            + f"<w:tbl><w:tr>{cell('项')}{cell('值')}</w:tr><w:tr>{cell('IP')}{cell('35.194.237.91')}</w:tr></w:tbl>"
            + "</w:body></w:document>",
        "word/styles.xml": f'<w:styles xmlns:w="{NS_W}"><w:style w:styleId="Title"><w:name w:val="Title"/></w:style>'
                           '<w:style w:styleId="Heading1"><w:name w:val="heading 1"/></w:style></w:styles>',
    })


def xlsx(path, rows=3):
    data = '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="C1" t="s"><v>1</v></c></row>'
    for index in range(2, rows + 2):
        data += (f'<row r="{index}"><c r="A{index}" s="1"><v>{46294 + index}</v></c>'
                 f'<c r="C{index}"><v>{index * 10}</v></c></row>')
    write_zip(path, {
        "xl/workbook.xml": f'<workbook xmlns="{NS_S}" xmlns:r="{NS_R}"><sheets>'
                           '<sheet name="费用" sheetId="1" r:id="rId1"/>'
                           '<sheet name="内部" sheetId="2" state="hidden" r:id="rId2"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": f'<Relationships xmlns="{REL}">'
            '<Relationship Id="rId1" Type="x/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="x/worksheet" Target="/xl/worksheets/sheet2.xml"/></Relationships>',
        "xl/sharedStrings.xml": f'<sst xmlns="{NS_S}"><si><t>日期</t></si><si><r><t>金</t></r><r><t>额</t></r></si></sst>',
        "xl/styles.xml": f'<styleSheet xmlns="{NS_S}"><cellXfs><xf numFmtId="0"/><xf numFmtId="14"/></cellXfs></styleSheet>',
        "xl/worksheets/sheet1.xml": f'<worksheet xmlns="{NS_S}"><sheetData>{data}</sheetData></worksheet>',
        "xl/worksheets/sheet2.xml": f'<worksheet xmlns="{NS_S}"><sheetData><row r="1"><c r="A1" t="inlineStr">'
                                    '<is><t>不应出现</t></is></c></row></sheetData></worksheet>',
    })


class DigestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_html_drops_chrome_and_keeps_content(self):
        path = self.root / "page.html"
        path.write_text(HTML, encoding="utf-8")
        text = digest_document(path)
        for kept in ("# 部署说明", "18888", "- 备份目录 /data/backup", "## 回滚", "| CPA | 8.0.33 |",
                     "- 客户端：Codex", "- 客户端 → 服务端：REST"):
            self.assertIn(kept, text)
        for dropped in ("导出 PNG", "深色", "首页", "隐藏的弹层", "secret", "ignored"):
            self.assertNotIn(dropped, text)
        self.assertEqual(text.count("通过 SSH 隧道访问"), 1)
        self.assertEqual(text.count("# 部署说明"), 1)

    def test_pptx_follows_presentation_order_with_notes_and_tables(self):
        path = self.root / "deck.pptx"
        pptx(path)
        text = digest_document(path)
        self.assertTrue(text.startswith("# 季度汇报"))
        self.assertLess(text.index("第 1 页：季度汇报"), text.index("第 2 页：核心指标"))
        self.assertIn("  - 8.3 倍", text)
        self.assertIn("备注：强调 QAI 合并", text)
        self.assertIn("| 文档数 | 213 |", text)
        self.assertNotIn("隐藏页", text)

    def test_docx_headings_lists_and_tables(self):
        path = self.root / "plan.docx"
        docx(path)
        text = digest_document(path)
        self.assertIn("# 迁移方案", text)
        self.assertIn("## 背景", text)
        self.assertIn("- 第一步", text)
        self.assertIn("| IP | 35.194.237.91 |", text)

    def test_xlsx_dates_sparse_columns_and_hidden_sheets(self):
        path = self.root / "cost.xlsx"
        xlsx(path)
        text = digest_document(path)
        self.assertIn("## 工作表：费用（4 行 × 2 列）", text)
        self.assertIn("| 日期 | 金额 |", text)
        self.assertIn("| 2026-10-01 | 20 |", text)
        self.assertNotIn("不应出现", text)

    def test_long_tables_are_summarized(self):
        path = self.root / "big.xlsx"
        xlsx(path, rows=50)
        text = digest_document(path)
        self.assertIn("共 50 行数据，以上列出前 30 行", text)
        self.assertIn("- 金额：数值 50 个，最小 20，最大 510，合计 13250", text)
        self.assertIn("个不同日期", text)
        self.assertNotIn("| 2026-11-19 |", text)

    def test_csv_becomes_table(self):
        path = self.root / "data.csv"
        path.write_text("name,count\nalpha,1\nbeta,2\n", encoding="utf-8")
        self.assertIn("| beta | 2 |", digest_document(path))

    def test_empty_shell_is_skipped(self):
        path = self.root / "shell.html"
        path.write_text("<html><body><div role='toolbar'><button>导出全部图表文件</button></div>"
                        "<p>加载中</p></body></html>", encoding="utf-8")
        self.assertEqual(digest_document(path), "")

    def test_markdown_is_untouched(self):
        path = self.root / "note.md"
        path.write_text("# 标题\n\n\n\n正文 正文\n", encoding="utf-8")
        self.assertEqual(digest_document(path), "# 标题\n\n\n\n正文 正文")


def load_hook():
    spec = importlib.util.spec_from_file_location("hindsight_hook", Path(__file__).with_name("hindsight-hook.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UploadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.page = self.root / "work" / "page.html"
        self.page.parent.mkdir()
        self.page.write_text(HTML.replace('var secret = "ignored"', 'var data = "ignored"'), encoding="utf-8")
        self.state = self.root / "state"
        self.payload = {"cwd": str(self.page.parent),
                        "session_started_at": "2000-01-01T00:00:00Z"}
        self.transcript = f"user: 做个页面\n\nassistant: 已生成 [page]({self.page})"

    def tearDown(self):
        self.tmp.cleanup()

    def test_html_artifact_is_collected_as_original_bytes(self):
        ready, blocked = session_documents.collect_artifacts(self.transcript, self.payload, "machine")
        self.assertEqual(blocked, [])
        self.assertEqual(len(ready), 1)
        self.assertIn("导出 PNG".encode(), ready[0]["data"])
        again, _ = session_documents.collect_artifacts(self.transcript, self.payload, "machine")
        self.assertEqual(again[0]["key"], ready[0]["key"])
        self.assertEqual(again[0]["sha256"], ready[0]["sha256"])

    def test_large_html_is_allowed_but_large_markdown_is_not(self):
        roots = [self.root]
        big_html = self.root / "big.html"
        big_html.write_bytes(b"<p>" + b"x" * 2_000_000 + b"</p>")
        big_md = self.root / "big.md"
        big_md.write_bytes(b"x" * 2_000_000)
        started = time.time() - 60
        self.assertTrue(session_documents.allowed_artifact(big_html, roots, started))
        self.assertFalse(session_documents.allowed_artifact(big_md, roots, started))

    def upload_body(self, page):
        hook = load_hook()
        captured = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *unused):
                return False

            def read(self, *unused):
                return b'{"accepted": [], "failed": []}'

        class Opener:
            def open(self, request, timeout):
                captured["body"], captured["url"] = request.data, request.full_url
                return Response()

        hook.connection = lambda: {"api_url": "http://127.0.0.1:1", "bank_id": "b", "mcp_token": "t"}
        hook.urllib.request.build_opener = lambda *unused: Opener()
        item = {"path": page, "data": page.read_bytes()}
        manifest = {"source_id": "s", "session_id": "sid", "title": "t",
                    "artifacts": [{"filename": page.name, "source_path": str(page)}]}
        self.assertEqual(hook.post_session(manifest, "user: hi", [item]), {"accepted": [], "failed": []})
        self.assertTrue(captured["url"].endswith("/ext/ingest/banks/b/sessions"))
        return captured["body"].decode("utf-8")

    def test_upload_sends_original_for_server_parsing(self):
        body = self.upload_body(self.page)
        self.assertIn('name="file0"; filename="page.html"', body)
        self.assertIn('name="session"', body)
        self.assertIn("<h1>部署说明</h1>", body)

    def test_collection_blocks_secret_instead_of_converting_locally(self):
        page = self.page.with_name("leak.html")
        page.write_text("<h1>连接</h1><p>api_key=sk-abcdefghijklmnop1234</p>", encoding="utf-8")
        from ingest_safety import inspect_upload
        with self.assertRaises(ValueError):
            inspect_upload(page.name, page.read_bytes(), check_credentials=True)


if __name__ == "__main__":
    unittest.main()
