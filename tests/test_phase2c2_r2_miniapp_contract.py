import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Phase2C2R2MiniappContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = (ROOT / "miniapp_yuzu/package_dispatch/pages/dispatch/index.js").read_text(encoding="utf-8")
        cls.wxml = (ROOT / "miniapp_yuzu/package_dispatch/pages/dispatch/index.wxml").read_text(encoding="utf-8")

    def test_quick_dispatch_exposes_one_combined_pdf_and_reopen_action(self):
        self.assertIn("生成文书", self.wxml)
        self.assertIn("两种文书合并", self.wxml)
        self.assertIn("bindtap=\"openFixedTourGeneratedPdf\"", self.wxml)
        self.assertIn("PDF草稿已生成 · ${Number(document.page_count || 0)}页", self.js)
        self.assertNotIn("生成两份 PDF 草稿", self.wxml)
        self.assertNotIn("两份内部 PDF 草稿已生成", self.js)

    def test_document_body_precedes_collapsed_diagnostics(self):
        paper_index = self.wxml.index("document-paper-title")
        issues_index = self.wxml.index("document-issue-compact")
        self.assertLess(paper_index, issues_index)
        self.assertIn("dailyPdfIssuesExpanded", self.wxml)
        self.assertIn("openDocumentCellEditor", self.wxml)
        self.assertIn("下载打印", self.wxml)
        self.assertIn("buildValidationPresentation", self.js)

    def test_document_workbench_does_not_silently_render_an_empty_preview(self):
        self.assertIn("previewUnavailable = !['acceptance', 'dispatch'].some", self.js)
        self.assertIn("dailyPdfVisiblePages && dailyPdfVisiblePages.length", self.wxml)
        self.assertIn("当前后端版本未返回文书正文", self.wxml)
        self.assertNotIn('style="width: {{dailyPdfZoom}}%;"', self.wxml)


if __name__ == "__main__":
    unittest.main()
