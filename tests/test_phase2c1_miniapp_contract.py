import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Phase2C1MiniappContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page_js = (ROOT / "miniapp_yuzu/package_dispatch/pages/dispatch/index.js").read_text(encoding="utf-8")
        cls.page_wxml = (ROOT / "miniapp_yuzu/package_dispatch/pages/dispatch/index.wxml").read_text(encoding="utf-8")
        cls.page_wxss = (ROOT / "miniapp_yuzu/package_dispatch/pages/dispatch/index.wxss").read_text(encoding="utf-8")
        cls.api_js = (ROOT / "miniapp_yuzu/package_dispatch/utils/api.js").read_text(encoding="utf-8")
        cls.routes_py = (ROOT / "backend/api/routes.py").read_text(encoding="utf-8")

    def test_three_existing_dispatch_modes_remain_visible(self):
        for label in ("日配模式", "日游行程", "批量导入"):
            self.assertIn(label, self.page_wxml)

    def test_route_sheet_search_and_unconditional_add_entry(self):
        self.assertIn('bindinput="onFixedTourRouteSearch"', self.page_wxml)
        add_position = self.page_wxml.index("新增行程")
        add_tag = self.page_wxml[self.page_wxml.rfind("<view", 0, add_position):add_position]
        self.assertNotIn("wx:if", add_tag)
        self.assertIn('tour-sheet-grid two', self.page_wxml)

    def test_one_shared_editor_covers_preset_and_custom(self):
        self.assertIn("openNewFixedTourPreset", self.page_js)
        self.assertIn("openCustomFixedTourDraft", self.page_js)
        self.assertIn("fixedTourView === 'editor'", self.page_wxml)
        self.assertIn("仅用于本次", self.page_wxml)
        self.assertIn("保存并使用", self.page_wxml)
        self.assertIn("fixedTourPickerOpen: ''", self.page_js)
        self.assertIn("fixedTourReturnToQuick: true", self.page_js)
        self.assertIn("fixedTourView: 'quick'", self.page_js)

    def test_mobile_editor_has_required_node_interactions(self):
        for handler in (
            "addFixedTourNode", "moveFixedTourNode", "removeFixedTourNode",
            "addFixedTourDay", "saveAndUseFixedTourEditor",
        ):
            self.assertIn(handler, self.page_js)
            self.assertIn(handler, self.page_wxml)
        self.assertIn("default_arrival_time", self.page_wxml)
        self.assertIn("default_departure_time", self.page_wxml)
        self.assertIn("FIXED_TOUR_EDITOR_STORAGE_KEY", self.page_js)
        self.assertIn("enableAlertBeforeUnload", self.page_js)

    def test_phase2c2_exposes_draft_generation_but_not_publish_action(self):
        fixed_block = self.page_wxml.split('<block wx:if="{{workbenchMode === \'fixed\'}}">', 1)[1].split('<block wx:if="{{workbenchMode === \'daily\'}}">', 1)[0]
        self.assertIn("生成文书", fixed_block)
        self.assertIn("查看PDF", fixed_block)
        self.assertIn("两种文书合并", fixed_block)
        self.assertNotIn("确认发布", fixed_block)
        self.assertNotIn("createFixedTourRun", fixed_block)
        self.assertIn("generateFixedTourDocuments", fixed_block)
        self.assertIn("generateFixedTourDocuments() {", self.page_js)
        self.assertIn("ensureFixedTourDraftForGeneration() {", self.page_js)
        self.assertIn("api.generateFixedTourDraftDocuments", self.page_js)
        self.assertIn("dailyPdfDraftOnly: true", self.page_js)

    def test_mobile_api_has_idempotent_draft_and_preset_operations(self):
        for path in (
            "/api/dispatch-mobile/fixed-tour/routes/save-use",
            "/api/dispatch-mobile/fixed-tour/drafts",
            "/api/dispatch-mobile/fixed-tour/routes/${routeId}/copy",
            "/api/dispatch-mobile/fixed-tour/routes/${routeId}/status",
        ):
            self.assertIn(path, self.api_js)
        self.assertIn("client_request_id", self.page_js)
        self.assertIn("fixed_tour_service_unavailable", self.api_js)
        self.assertIn("已保留填写内容", self.api_js)
        self.assertIn("/generate-documents", self.api_js)

    def test_mobile_write_roles_exclude_driver(self):
        start = self.routes_py.index('if path == "/api/dispatch-mobile/fixed-tour/routes/save-use"')
        end = self.routes_py.index('if path == "/api/fixed-tour/routes"', start)
        mobile_block = self.routes_py[start:end]
        self.assertIn('{"admin", "dispatcher", "operations_manager"}', mobile_block)
        self.assertNotIn('"driver"', mobile_block)

    def test_fixed_save_bar_and_safe_area_are_present(self):
        self.assertIn(".tour-save-bar", self.page_wxss)
        self.assertIn("env(safe-area-inset-bottom)", self.page_wxss)

    def test_daily_preview_exposes_business_date_and_batch_recovery(self):
        self.assertIn("dailyImportDefaultDate", self.page_js)
        self.assertIn("onDailyGroupDateChange", self.page_js)
        self.assertIn("client_batch_id", self.page_js)
        self.assertIn("dailyImportStatus", self.api_js)
        self.assertIn("daily_import_result_unknown", self.page_js)
        self.assertIn("当前 Trial 后端缺少批次状态接口", self.page_js)
        self.assertIn("{{item.serviceDate || '请选择日期'}}", self.page_wxml)
        self.assertIn("{{item.driverName}} · {{item.vehicleCode}} · {{item.orders.length}}单", self.page_wxml)

    def test_fixed_tour_picker_shows_real_lists_and_search_fallback(self):
        self.assertIn("司机列表 · {{fixedTourVisibleDrivers.length}} 人", self.page_wxml)
        self.assertIn("车辆列表 · {{fixedTourVisibleVehicles.length}} 台", self.page_wxml)
        self.assertIn("没有匹配的司机", self.page_wxml)
        self.assertIn("没有匹配的车辆", self.page_wxml)
        self.assertIn("dispatchDrivers.length ? dispatchDrivers", self.page_js)
        self.assertIn("dispatchVehicles.length ? dispatchVehicles", self.page_js)
        self.assertIn("当日冲突状态需人工核对", self.page_js)

    def test_route_picker_exposes_management_menu_without_select_bubbling(self):
        self.assertIn('catchtap="openFixedTourPresetMenu"', self.page_wxml)
        for handler in ("openFixedTourPresetMenu", "editFixedTourPreset", "copyFixedTourPreset", "deactivateFixedTourPreset"):
            self.assertIn(handler, self.page_js)
        for label in ("编辑预设", "另存副本", "停用预设"):
            self.assertIn(label, self.page_js)
        self.assertIn("没有匹配的线路，仍可在下方新增", self.page_wxml)

    def test_shared_document_workbench_edits_nodes_and_document_fields(self):
        self.assertIn("dailyPdfSourceMode: 'fixed'", self.page_js)
        self.assertIn("dailyPdfSourceMode: 'daily'", self.page_js)
        self.assertIn("expected_source_hash", self.page_js)
        self.assertIn("patchRunDocumentDraft", self.api_js)
        self.assertIn("/api/dispatch-mobile/run-documents/draft-patch", self.api_js)
        self.assertIn("openDocumentCellEditor", self.page_wxml)
        self.assertIn("saveDocumentTaskEdits", self.page_wxml)
        self.assertIn("草稿已保存，两份文书已同步", self.page_js)
        self.assertIn("确认生成", self.page_wxml)
        self.assertIn("document-paper", self.page_wxml)
        self.assertEqual(self.page_wxml.count('wx:if="{{dailyPdfReviewOpen}}"'), 1)
        self.assertNotIn("确认并发布", self.page_wxml)

    def test_document_workbench_requires_preview_and_separates_generate(self):
        self.assertIn("api.runDocumentPreview(key)", self.page_js)
        self.assertIn("dailyPdfPreviewUnavailable", self.page_js)
        self.assertIn("不能安全编辑", self.page_wxml)
        self.assertIn("prepareFixedTourDraftDocuments", self.page_js)
        self.assertIn("confirmGenerateDocument", self.page_js)
        start = self.page_js.index("saveDocumentTaskEdits()")
        end = self.page_js.index("saveDocumentDraft()", start)
        self.assertNotIn("generateRunDocument", self.page_js[start:end])

    def test_reusable_fields_require_explicit_atomic_apply_selection(self):
        self.assertIn("应用到其他订单（默认不选）", self.page_wxml)
        self.assertIn("toggleDocumentApplyTarget", self.page_wxml)
        self.assertIn("apply_source_field_id", self.page_js)
        self.assertIn("apply_options", self.page_js)
        self.assertIn("documentTaskPatches()", self.page_js)
        for field_name in ("price_jpy", "fare_jpy", "service_fee_jpy", "advance_jpy", "toll_fee_jpy", "parking_fee_jpy"):
            self.assertIn(field_name, self.page_js)

    def test_charter_workbench_reuses_current_draft_route_editor(self):
        self.assertIn("调整本次包车路线、节点顺序与日期", self.page_wxml)
        self.assertIn("editCurrentCharterRoute", self.page_js)
        self.assertIn("api.fixedTourCharterDraft", self.page_js)
        self.assertIn("this.openFixedTourDraft(draft)", self.page_js)
        self.assertIn("fixedTourReturnToDocumentWorkbench: true", self.page_js)
        self.assertIn("returnToFixedTourDocumentWorkbench", self.page_js)
        self.assertIn("api.prepareFixedTourDraftDocuments(draft.id", self.page_js)
        self.assertIn("dailyPdfDocumentTab: documentTab", self.page_js)
        self.assertIn("dailyPdfScrollAnchor: scrollAnchor", self.page_js)

    def test_validation_navigation_uses_stable_order_and_field_ids(self):
        self.assertIn("documentValidationCellName", self.page_js)
        self.assertIn("order_sequence", self.page_js)
        self.assertIn('data-field-id="{{item.field_id}}"', self.page_wxml)


if __name__ == "__main__":
    unittest.main()
