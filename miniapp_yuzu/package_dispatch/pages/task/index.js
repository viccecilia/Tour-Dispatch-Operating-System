const api = require('../../utils/api');

const PREFLIGHT_ITEMS = [
  { key: 'light', label: '车灯正常' },
  { key: 'brake', label: '刹车正常' },
  { key: 'body', label: '车身无新增损伤' },
  { key: 'license', label: '已携带驾照' },
  { key: 'certificate', label: '已携带乘务员证' },
  { key: 'alcohol', label: '出库前酒精确认' },
  { key: 'sleep', label: '睡眠状态充足' }
];

const RETURN_ITEMS = [
  { key: 'clean', label: '车辆已清扫' },
  { key: 'inspection', label: '入库点检完成' },
  { key: 'alcohol', label: '入库后酒精确认' },
  { key: 'roll_call', label: '点呼入库完成' }
];

const ACTIVE_STATUSES = ['departed', 'arrived', 'in_service'];
const OPEN_STATUSES = ['assigned', 'confirmed', 'departed', 'arrived', 'in_service'];
const ACTUAL_PENDING_KEY = 'driver_route_actual_pending_v1';
const ACTUAL_DRAFT_KEY = 'driver_route_actual_drafts_v2';

Page({
  data: {
    session: null,
    driverId: 0,
    allAssignments: [],
    assignments: [],
    readyAssignments: [],
    runDocuments: [],
    today: '',
    selectedDate: '',
    selectedLabel: '',
    monthLabel: '',
    selectedDayAnchor: '',
    weekDays: [],
    monthDays: [],
    weekLabels: ['日', '一', '二', '三', '四', '五', '六'],
    showMonth: false,
    yardFocus: '',
    reportFocus: false,
    loadState: 'idle',
    workflowEvents: [],
    vehicleStatusText: '未出库',
    departSubmitted: false,
    returnSubmitted: false,
    departExpanded: true,
    returnExpanded: true,
    departEditing: false,
    returnEditing: false,
    canWriteSelectedDate: true,
    departRecord: { done: false, time: '', checks: [], attachmentName: '' },
    returnRecord: { done: false, time: '', checks: [], attachmentName: '' },
    pageHero: {
      dateText: '', driverText: '-', vehicleText: '车辆待确认', stateLabel: '未出库', stateTone: 'pending',
      progressText: '0/0', flowText: '等待出库点呼', actionLabel: '办理出库', actionTarget: 'depart'
    },
    preflightItems: PREFLIGHT_ITEMS,
    returnItems: RETURN_ITEMS,
    preflightChecked: {},
    returnChecked: {},
    departForm: {
      depart_time: '',
      sleep_hours: ''
    },
    returnForm: {
      return_time: '',
      rest_hours: ''
    },
    departMaterials: {
      alcohol: { file_name: '', image_base64: '' }
    },
    returnMaterials: {
      alcohol: { file_name: '', image_base64: '' }
    },
    dailyReport: { status: 'draft', assignment_count: 0, assignments: [], summary: '', rest_hours: '', submitted_at: '' },
    reportEditorOpen: false,
    dailyReportSaving: false,
    message: '',
    loading: false,
    submitting: false,
    actualPendingCount: 0
  },

  onShow() {
    api.setActiveTab('/package_dispatch/pages/task/index');
    const session = api.getSession();
    const role = api.getRole(session);
    if (!session || role !== 'driver') {
      wx.reLaunch({ url: '/package_dispatch/pages/home/index' });
      return;
    }
    this.refreshTabBar();
    const today = this.today();
    const yardFocus = wx.getStorageSync('driver_task_yard_focus') || '';
    if (yardFocus) wx.removeStorageSync('driver_task_yard_focus');
    const reportFocus = !!wx.getStorageSync('driver_task_report_focus');
    if (reportFocus) wx.removeStorageSync('driver_task_report_focus');
    const driverId = Number(session.user && session.user.profile_id || 0);
    this.setData({
      session,
      driverId,
      yardFocus,
      reportFocus,
      today,
      selectedDate: today,
      selectedLabel: this.formatDayLabel(today),
      ...this.buildCalendarState([], today, today),
      'departForm.depart_time': this.nowTime(),
      'returnForm.return_time': this.nowTime()
    });
    this.loadTasks();
  },

  refreshTabBar() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().refresh();
    }
  },

  loadTasks() {
    if (!this.data.driverId) {
      const selectedDate = this.data.selectedDate || this.data.today || this.today();
      this.setData({
        message: '司机资料未绑定。',
        assignments: [],
        readyAssignments: [],
        allAssignments: [],
        ...this.buildCalendarState([], selectedDate, this.data.today || selectedDate)
      });
      return;
    }
    const selectedDateRequest = this.data.selectedDate || this.data.today;
    this.setData({ loading: true, loadState: 'loading', message: '' });
    Promise.all([
      api.driverAssignments(this.data.driverId),
      api.driverWorkflowEvents(selectedDateRequest).catch(() => ({ events: [] })),
      api.driverRunDocuments(this.data.driverId).catch(() => ({ documents: [] })),
      api.driverDailyReport(selectedDateRequest).catch(() => ({ report: {} })),
      api.driverDayWorkbench(selectedDateRequest).catch(() => ({ nodes: [] })),
      api.driverProfile(this.data.driverId).catch(() => ({ driver: null }))
    ])
      .then(([res, workflowRes, documentsRes, dailyReportRes, actualWorkbench, profileRes]) => {
        const actualNodes = actualWorkbench.nodes || [];
        const allRows = (res.assignments || []).map((item) => this.decorateAssignment(item, actualNodes));
        const selectedDate = this.data.selectedDate || this.data.today;
        const selectedRows = allRows.filter((item) => this.isOnDate(item, selectedDate));
        const workflowEvents = (workflowRes.events || []).filter((item) => String(item.event_status || 'submitted') === 'submitted');
        const departRecord = this.buildYardRecord(workflowEvents, 'depart');
        const returnRecord = this.buildYardRecord(workflowEvents, 'return');
        const departed = departRecord.done;
        const returned = returnRecord.done;
        const vehicleStatusText = returned ? '已入库' : (departed ? '已出库' : '未出库');
        const report = dailyReportRes.report || {};
        const dailyReport = {
          status: report.status || 'draft',
          assignment_count: report.assignment_count || 0,
          assignments: report.assignments || [],
          summary: report.summary || '',
          rest_hours: report.rest_hours === null || report.rest_hours === undefined ? '' : String(report.rest_hours),
          submitted_at: report.submitted_at || ''
        };
        const canWriteSelectedDate = selectedDate <= this.data.today;
        const focusDepart = this.data.yardFocus === 'depart';
        const focusReturn = this.data.yardFocus === 'return';
        this.setData({
          allAssignments: allRows,
          selectedDate,
          ...this.buildCalendarState(allRows, selectedDate, this.data.today),
          vehicleStatusText,
          departSubmitted: departed || returned,
          returnSubmitted: returned,
          workflowEvents,
          departRecord,
          returnRecord,
          preflightChecked: this.checksToMap(departRecord.checks),
          returnChecked: this.checksToMap(returnRecord.checks),
          'departForm.depart_time': departRecord.time || this.nowTime(),
          'departForm.sleep_hours': departRecord.hours,
          'returnForm.return_time': returnRecord.time || this.nowTime(),
          'returnForm.rest_hours': returnRecord.hours,
          'departMaterials.alcohol': { file_name: departRecord.attachmentName, image_base64: '' },
          'returnMaterials.alcohol': { file_name: returnRecord.attachmentName, image_base64: '' },
          departExpanded: departed ? focusDepart : true,
          returnExpanded: returned ? focusReturn : true,
          departEditing: false,
          returnEditing: false,
          canWriteSelectedDate,
          runDocuments: (documentsRes.documents || []).filter((item) => !item.business_date || String(item.business_date).slice(0, 10) === selectedDate).map((item) => ({
            ...item,
            title: `${item.business_date} 运行文件`,
            meta: `${item.plate_number || ''} · 运行文书 V${item.version} · ${item.page_count || 0}页`
          })),
          dailyReport,
          reportEditorOpen: returned && (this.data.reportFocus || this.data.reportEditorOpen),
          yardFocus: '',
          reportFocus: false,
          loading: false,
          loadState: 'ready',
          actualPendingCount: this.actualPendingQueue().length
        });
        this.applySelectedDate();
        this.setData({
          pageHero: this.buildPageHero(this.data.assignments, departRecord, returnRecord, dailyReport, profileRes.driver || {})
        });
      })
      .catch(() => {
        const selectedDate = this.data.selectedDate || this.data.today || this.today();
        this.setData({
          loading: false,
          loadState: 'error',
          message: '无法加载司机任务。',
          assignments: [],
          readyAssignments: [],
          allAssignments: [],
          ...this.buildCalendarState([], selectedDate, this.data.today || selectedDate)
        });
      });
  },

  openRunDocument(e) {
    const url = String((e.currentTarget.dataset || {}).url || '');
    if (!url) return;
    wx.showLoading({ title: '打开 PDF' });
    api.downloadAndOpenDocument(url)
      .then(() => wx.hideLoading())
      .catch((err) => {
        console.warn('[driver run document open failed]', err);
        wx.hideLoading();
        wx.showToast({ title: '运行文件打开失败', icon: 'none' });
      });
  },

  parseWorkflowNote(event) {
    const raw = event && event.note;
    if (!raw) return {};
    if (typeof raw === 'object') return raw;
    try {
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch (err) {
      return {};
    }
  },

  findWorkflowEvent(events, types) {
    const wanted = Array.isArray(types) ? types : [types];
    return (events || []).find((item) => wanted.indexOf(String(item.event_type || '')) >= 0) || null;
  },

  buildYardRecord(events, section) {
    const isDepart = section === 'depart';
    const event = this.findWorkflowEvent(events, isDepart
      ? ['depart_yard', 'roll_call_out', 'vehicle_check_out']
      : ['return_yard', 'roll_call_in', 'vehicle_check_in']);
    const alcohol = this.findWorkflowEvent(events, isDepart ? 'alcohol_test_out' : 'alcohol_test_in');
    const note = this.parseWorkflowNote(event);
    const alcoholNote = this.parseWorkflowNote(alcohol);
    const attachments = alcoholNote.attachments || [];
    return {
      done: !!event,
      time: this.workflowTimeText(event && event.event_time),
      eventId: event && event.id || 0,
      checks: Array.isArray(note.checks) ? note.checks : [],
      hours: (isDepart ? note.sleep_hours : note.rest_hours) === null || (isDepart ? note.sleep_hours : note.rest_hours) === undefined
        ? '' : String(isDepart ? note.sleep_hours : note.rest_hours),
      attachmentName: attachments[0] && (attachments[0].name || attachments[0].file_name) || '',
      locationText: event && event.location_text || ''
    };
  },

  checksToMap(checks) {
    return (checks || []).reduce((result, key) => {
      result[key] = true;
      return result;
    }, {});
  },

  workflowTimeText(value) {
    const text = String(value || '').replace('T', ' ');
    const match = text.match(/\b(\d{2}:\d{2})(?::\d{2})?/);
    return match ? match[1] : '';
  },

  buildPageHero(rows, departRecord, returnRecord, dailyReport, driver) {
    const tasks = rows || [];
    const completed = tasks.filter((item) => ['completed', 'returned'].indexOf(String(item.rawStatus || '')) >= 0
      || Number(item.actualEditor && item.actualEditor.savedCount || 0) === 6).length;
    const reportSubmitted = dailyReport && dailyReport.status === 'submitted';
    let stateLabel = '未出库';
    let stateTone = 'pending';
    let flowText = '等待出库点呼';
    let actionLabel = '办理出库';
    let actionTarget = 'depart';
    if (!tasks.length && !departRecord.done && !returnRecord.done && !reportSubmitted) {
      stateLabel = '当天无任务';
      stateTone = 'idle';
      flowText = '暂无本人已发布任务';
      actionLabel = '查看日历';
      actionTarget = 'calendar';
    } else if (returnRecord.done && reportSubmitted) {
      stateLabel = '今日已完成';
      stateTone = 'completed';
      flowText = `出库 ${departRecord.time || '--:--'} · 入库 ${returnRecord.time || '--:--'} · 日报已提交`;
      actionLabel = '查看日报';
      actionTarget = 'report';
    } else if (returnRecord.done) {
      stateLabel = '已入库・日报待提交';
      stateTone = 'report';
      flowText = `出库 ${departRecord.time || '--:--'} · 入库 ${returnRecord.time || '--:--'}`;
      actionLabel = '日报整理';
      actionTarget = 'report';
    } else if (departRecord.done) {
      stateLabel = '运行中';
      stateTone = 'active';
      flowText = `已出库 ${departRecord.time || '--:--'} · 今日运行中`;
      actionLabel = '查看任务';
      actionTarget = 'tasks';
    }
    const first = tasks[0] || {};
    const sessionUser = this.data.session && this.data.session.user || {};
    return {
      dateText: `${this.formatFullDate(this.data.selectedDate)} · ${driver.name || driver.driver_name || sessionUser.name || sessionUser.username || '司机'}`,
      driverText: driver.name || driver.driver_name || first.driver_name || sessionUser.name || '-',
      vehicleText: first.plate_number || first.vehicle_plate || '车辆待确认',
      stateLabel,
      stateTone,
      progressText: `${completed}/${tasks.length}`,
      flowText,
      actionLabel,
      actionTarget
    };
  },

  formatFullDate(dateText) {
    const date = this.parseDate(dateText || this.data.today);
    const week = ['日', '一', '二', '三', '四', '五', '六'][date.getDay()];
    return `${date.getMonth() + 1}月${date.getDate()}日 周${week}`;
  },

  decorateAssignment(item, actualNodes = []) {
    const status = item.execution_status || item.status || 'assigned';
    const timeText = this.assignmentTimeText(item);
    const routeText = this.assignmentRouteText(item);
    const assignmentId = Number(item.assignment_id || item.id || 0);
    const orderId = Number(item.order_id || 0);
    const nodes = actualNodes.filter((node) => Number(node.assignment_id || 0) === assignmentId || (orderId && Number(node.order_id || 0) === orderId));
    const pickupNode = nodes.find((node) => ['pickup', 'origin', 'start'].indexOf(String(node.node_type || '').toLowerCase()) >= 0) || nodes[0] || null;
    const dropoffNode = nodes.slice().reverse().find((node) => ['dropoff', 'destination', 'end'].indexOf(String(node.node_type || '').toLowerCase()) >= 0) || nodes[nodes.length - 1] || null;
    const actualEditor = this.buildActualEditor(pickupNode, dropoffNode);
    return {
      ...item,
      rawStatus: status,
      orderNoText: item.oid || item.order_id || '任务',
      routeText,
      timeText,
      orderStatusText: this.orderStatusText(status),
      orderStatusClass: this.orderStatusClass(status),
      canConfirm: status === 'assigned',
      isExpanded: ACTIVE_STATUSES.indexOf(status) >= 0,
      actualEditor,
      baseCanEditActual: !!(pickupNode && dropoffNode),
      canEditActual: !!(pickupNode && dropoffNode),
      actualSyncText: actualEditor.savedCount ? `已保存 ${actualEditor.savedCount}/6 项` : '尚未保存实际值'
    };
  },

  buildActualEditor(pickupNode, dropoffNode) {
    const pickup = pickupNode && pickupNode.actual || {};
    const dropoff = dropoffNode && dropoffNode.actual || {};
    const value = (raw) => raw === null || raw === undefined ? '' : String(raw);
    const form = {
      pickup_location: value(pickup.actual_location),
      pickup_departure_at: value(pickup.actual_departure_at),
      dropoff_arrival_at: value(dropoff.actual_arrival_at),
      dropoff_location: value(dropoff.actual_location),
      pickup_odometer: value(pickup.odometer_km),
      dropoff_odometer: value(dropoff.odometer_km)
    };
    return {
      pickupNode, dropoffNode, form, dirty: {}, saving: false,
      savedCount: Object.keys(form).filter((key) => form[key] !== '').length,
      pickupPlannedLocation: pickupNode && pickupNode.planned_location || '',
      pickupPlannedTime: this.readableTimestamp(pickupNode && pickupNode.planned_departure_at),
      dropoffPlannedTime: this.readableTimestamp(dropoffNode && dropoffNode.planned_arrival_at),
      dropoffPlannedLocation: dropoffNode && dropoffNode.planned_location || ''
    };
  },

  readableTimestamp(value) {
    const text = String(value || '');
    if (!text) return '';
    return text.replace('T', ' ').replace(/([+-]\d\d:\d\d|Z)$/, '').slice(0, 16);
  },

  onActualInput(e) {
    const assignmentId = Number(e.currentTarget.dataset.id || 0);
    const key = e.currentTarget.dataset.key;
    const value = e.detail.value;
    const rows = this.data.assignments.map((item) => {
      if (Number(item.assignment_id || item.id) !== assignmentId) return item;
      return Object.assign({}, item, {
        actualEditor: Object.assign({}, item.actualEditor, {
          form: Object.assign({}, item.actualEditor.form, { [key]: value }),
          dirty: Object.assign({}, item.actualEditor.dirty, { [key]: true })
        })
      });
    });
    this.setData({ assignments: rows });
    this.saveActualDraft(this.data.selectedDate, assignmentId, key, value);
  },

  saveActualFields(e) {
    const assignmentId = Number(e.currentTarget.dataset.id || 0);
    const item = this.data.assignments.find((row) => Number(row.assignment_id || row.id) === assignmentId);
    if (!item || !item.canEditActual || item.actualEditor.saving) return;
    const editor = item.actualEditor;
    const pickupChanges = {};
    const dropoffChanges = {};
    const form = editor.form;
    const dirty = editor.dirty || {};
    if (dirty.pickup_location && form.pickup_location) pickupChanges.actual_location = form.pickup_location;
    if (dirty.pickup_departure_at && form.pickup_departure_at) pickupChanges.actual_departure_at = form.pickup_departure_at;
    if (dirty.pickup_odometer && form.pickup_odometer !== '') pickupChanges.odometer_km = Number(form.pickup_odometer);
    if (dirty.dropoff_arrival_at && form.dropoff_arrival_at) dropoffChanges.actual_arrival_at = form.dropoff_arrival_at;
    if (dirty.dropoff_location && form.dropoff_location) dropoffChanges.actual_location = form.dropoff_location;
    if (dirty.dropoff_odometer && form.dropoff_odometer !== '') {
      dropoffChanges.odometer_km = Number(form.dropoff_odometer);
      if (!form.dropoff_arrival_at && !(editor.dropoffNode.actual || {}).actual_arrival_at) dropoffChanges.actual_arrival_at = new Date().toISOString();
    }
    const calls = [];
    if (Object.keys(pickupChanges).length) calls.push(this.actualSavePayload(item, editor.pickupNode, pickupChanges));
    if (Object.keys(dropoffChanges).length) calls.push(this.actualSavePayload(item, editor.dropoffNode, dropoffChanges));
    if (!calls.length) {
      wx.showToast({ title: '请先填写或修改实际值', icon: 'none' });
      return;
    }
    this.setActualSaving(assignmentId, true);
    Promise.all(calls.map((payload) => this.sendActualPayload(payload)))
      .then(() => {
        this.clearActualDraft(this.data.selectedDate, assignmentId, Object.keys(dirty));
        this.setData({ message: '本单实际值已同步保存。' });
        this.loadTasks();
      })
      .catch((err) => {
        this.setActualSaving(assignmentId, false);
        this.handleActualSaveError(err);
      });
  },

  actualSavePayload(item, node, changes) {
    return Object.assign({
      client_request_id: `route-actual-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
      run_group_id: node.run_group_id,
      route_node_id: node.route_node_id,
      source_document_version_id: node.document_version_id,
      source_sha256: node.source_sha256,
      assignment_id: item.assignment_id || item.id,
      order_id: item.order_id,
      expected_revision: Number(node.actual && node.actual.revision || 0),
      client_recorded_at: new Date().toISOString()
    }, changes);
  },

  sendActualPayload(payload) {
    return api.saveDriverRouteNodeActual(payload).then((result) => {
      const queue = this.actualPendingQueue().filter((item) => item.client_request_id !== payload.client_request_id);
      wx.setStorageSync(ACTUAL_PENDING_KEY, queue);
      this.setData({ actualPendingCount: queue.length });
      return result;
    }).catch((err) => {
      if (err && ['network_timeout', 'network_failed'].indexOf(err.error) >= 0) {
        const queue = this.actualPendingQueue();
        if (!queue.some((item) => item.client_request_id === payload.client_request_id)) queue.push(payload);
        wx.setStorageSync(ACTUAL_PENDING_KEY, queue);
        this.setData({ actualPendingCount: queue.length });
      }
      throw err;
    });
  },

  retryPendingActuals() {
    const queue = this.actualPendingQueue();
    if (!queue.length) return;
    this.setData({ message: `正在重试 ${queue.length} 条本机未同步记录…` });
    Promise.all(queue.map((payload) => this.sendActualPayload(payload)))
      .then(() => { this.setData({ message: '未同步记录已全部保存。' }); this.loadTasks(); })
      .catch((err) => this.handleActualSaveError(err));
  },

  actualPendingQueue() {
    const rows = wx.getStorageSync(ACTUAL_PENDING_KEY);
    return Array.isArray(rows) ? rows : [];
  },

  actualDraftStore() {
    const stored = wx.getStorageSync(ACTUAL_DRAFT_KEY);
    return stored && typeof stored === 'object' && !Array.isArray(stored) ? stored : {};
  },

  saveActualDraft(dateText, assignmentId, key, value) {
    const store = this.actualDraftStore();
    const rowKey = `${dateText}:${assignmentId}`;
    store[rowKey] = Object.assign({}, store[rowKey] || {}, { [key]: value });
    wx.setStorageSync(ACTUAL_DRAFT_KEY, store);
  },

  clearActualDraft(dateText, assignmentId, keys) {
    const store = this.actualDraftStore();
    const rowKey = `${dateText}:${assignmentId}`;
    const row = Object.assign({}, store[rowKey] || {});
    (keys || []).forEach((key) => delete row[key]);
    if (Object.keys(row).length) store[rowKey] = row;
    else delete store[rowKey];
    wx.setStorageSync(ACTUAL_DRAFT_KEY, store);
  },

  mergeActualDraft(item, dateText) {
    const assignmentId = Number(item.assignment_id || item.id || 0);
    const row = this.actualDraftStore()[`${dateText}:${assignmentId}`] || {};
    if (!Object.keys(row).length) return item;
    return Object.assign({}, item, {
      actualEditor: Object.assign({}, item.actualEditor, {
        form: Object.assign({}, item.actualEditor.form, row),
        dirty: Object.assign({}, item.actualEditor.dirty, Object.keys(row).reduce((result, key) => {
          result[key] = true;
          return result;
        }, {}))
      }),
      actualSyncText: '有未同步草稿'
    });
  },

  setActualSaving(assignmentId, saving) {
    this.setData({ assignments: this.data.assignments.map((item) => Number(item.assignment_id || item.id) === assignmentId
      ? Object.assign({}, item, { actualEditor: Object.assign({}, item.actualEditor, { saving }) }) : item) });
  },

  handleActualSaveError(err) {
    const code = String(err && (err.backendError || err.error) || '');
    if (Number(err && err.statusCode) === 409) {
      this.setData({ message: '计划或实绩已由其他端更新，已重新读取，请核对差异后再保存。' });
      this.loadTasks();
      return;
    }
    const pending = this.actualPendingQueue().length;
    this.setData({ message: pending ? `网络失败，${pending} 条记录仅保存在本机，点击重试。` : (api.errorMessage(err) || code) });
  },

  assignmentTimeText(item) {
    const startDate = item.order_date || item.start_date || '-';
    const startTime = item.start_time || '--:--';
    const endDate = item.end_date || '';
    const endTime = item.end_time || '';
    const startText = `${startDate} ${startTime}`;
    if (!endTime) return startText;
    if (endDate && endDate !== startDate) return `${startText} - ${endDate} ${endTime}`;
    return `${startText} - ${endTime}`;
  },

  assignmentRouteText(item) {
    return `${item.pickup_location || '-'} → ${item.dropoff_location || '-'}`;
  },

  applySelectedDate() {
    const selectedDate = this.data.selectedDate || this.data.today;
    const canWriteSelectedDate = selectedDate <= this.data.today;
    const readyRows = this.data.allAssignments
      .filter((item) => item.rawStatus === 'confirmed')
      .sort((a, b) => `${a.order_date || ''} ${a.start_time || ''}`.localeCompare(`${b.order_date || ''} ${b.start_time || ''}`));
    const rows = this.data.allAssignments
      .filter((item) => this.isOnDate(item, selectedDate))
      .sort((a, b) => String(a.start_time || '').localeCompare(String(b.start_time || '')))
      .map((item, index) => ({
        ...this.mergeActualDraft(item, selectedDate),
        canEditActual: canWriteSelectedDate && item.baseCanEditActual,
        isExpanded: ACTIVE_STATUSES.indexOf(item.rawStatus) >= 0 || (index === 0 && ACTIVE_STATUSES.indexOf(item.rawStatus) >= 0)
    }));
    this.setData({
      assignments: rows,
      readyAssignments: readyRows,
      selectedLabel: this.formatDayLabel(selectedDate),
      monthLabel: this.formatMonthLabel(selectedDate),
      canWriteSelectedDate
    });
  },

  onSelectDate(e) {
    const date = e.currentTarget.dataset.date;
    if (!date) return;
    this.setData({
      selectedDate: date,
      weekDays: this.buildWeekDays(this.data.allAssignments, date, this.data.today, date),
      monthDays: this.buildMonthDays(this.data.allAssignments, date, this.data.today, date),
      monthLabel: this.formatMonthLabel(date),
      selectedDayAnchor: this.dayAnchor(date)
    });
    this.applySelectedDate();
    this.loadTasks();
  },

  toggleMonth() {
    this.setData({ showMonth: !this.data.showMonth });
  },

  onPickMonth(e) {
    const value = e.detail && e.detail.value;
    if (!value) return;
    const date = `${value}-01`;
    this.setData({
      selectedDate: date,
      weekDays: this.buildWeekDays(this.data.allAssignments, date, this.data.today, date),
      monthDays: this.buildMonthDays(this.data.allAssignments, date, this.data.today, date),
      monthLabel: this.formatMonthLabel(date),
      selectedDayAnchor: this.dayAnchor(date),
      showMonth: true
    });
    this.applySelectedDate();
    this.loadTasks();
  },

  toggleTask(e) {
    const assignmentId = Number(e.currentTarget.dataset.id || 0);
    const rows = this.data.assignments.map((item) => {
      if (Number(item.assignment_id || item.id) !== assignmentId) return item;
      return { ...item, isExpanded: !item.isExpanded };
    });
    this.setData({ assignments: rows });
  },

  toggleYardSection(e) {
    const section = String((e.currentTarget.dataset || {}).section || '');
    if (section === 'depart' && this.data.departSubmitted) {
      this.setData({ departExpanded: !this.data.departExpanded, departEditing: false });
    }
    if (section === 'return' && this.data.returnSubmitted) {
      this.setData({ returnExpanded: !this.data.returnExpanded, returnEditing: false });
    }
  },

  editYardRecord(e) {
    const section = String((e.currentTarget.dataset || {}).section || '');
    if (!this.data.canWriteSelectedDate) return;
    if (section === 'depart') this.setData({ departExpanded: true, departEditing: true });
    if (section === 'return') this.setData({ returnExpanded: true, returnEditing: true });
  },

  focusHeroAction(e) {
    const target = String((e.currentTarget.dataset || {}).target || this.data.pageHero.actionTarget || 'tasks');
    if (target === 'depart') this.setData({ departExpanded: true });
    if (target === 'return') this.setData({ returnExpanded: true });
    if (target === 'report') this.setData({ reportEditorOpen: this.data.returnSubmitted });
    const selectors = { calendar: '.calendar-panel', depart: '#driver-depart', tasks: '#driver-tasks', return: '#driver-return', report: '#driver-report' };
    if (wx.pageScrollTo) wx.pageScrollTo({ selector: selectors[target] || '#driver-tasks', duration: 250 });
  },

  toggleReportEditor() {
    if (!this.data.returnSubmitted) {
      wx.showToast({ title: '请先完成入库点呼', icon: 'none' });
      return;
    }
    this.setData({ reportEditorOpen: !this.data.reportEditorOpen });
  },

  orderStatusText(status) {
    if (ACTIVE_STATUSES.indexOf(status) >= 0) return '正在执行';
    if (status === 'completed' || status === 'returned') return '已完成';
    return '待执行';
  },

  orderStatusClass(status) {
    if (ACTIVE_STATUSES.indexOf(status) >= 0) return 'active';
    if (status === 'completed' || status === 'returned') return 'done';
    return 'pending';
  },

  confirmTask(e) {
    const assignmentId = Number(e.currentTarget.dataset.id || 0);
    const item = this.data.assignments.find((row) => Number(row.assignment_id || row.id) === assignmentId);
    if (!item || !this.data.driverId) return;
    wx.showModal({
      title: '确认接单',
      content: `${item.timeText}\n${item.routeText}`,
      confirmText: '确认',
      cancelText: '取消',
      success: (res) => {
        if (!res.confirm) return;
        this.submitReport(item, 'confirm_order', {
          location_text: '司机端确认接单',
          note: JSON.stringify({ action: 'confirm_order' })
        }, '已确认接单');
      }
    });
  },

  onDepartInput(e) {
    this.setData({ [`departForm.${e.currentTarget.dataset.key}`]: e.detail.value });
  },

  onReturnInput(e) {
    this.setData({ [`returnForm.${e.currentTarget.dataset.key}`]: e.detail.value });
  },

  onTogglePreflight(e) {
    const key = e.currentTarget.dataset.key;
    this.setData({ preflightChecked: { ...this.data.preflightChecked, [key]: !this.data.preflightChecked[key] } });
  },

  onToggleReturn(e) {
    const key = e.currentTarget.dataset.key;
    this.setData({ returnChecked: { ...this.data.returnChecked, [key]: !this.data.returnChecked[key] } });
  },

  chooseYardMaterial(e) {
    const section = e.currentTarget.dataset.section;
    const key = e.currentTarget.dataset.key;
    if (!section || !key || this.data.submitting) return;
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const file = res.tempFiles && res.tempFiles[0];
        if (!file || !file.tempFilePath) return;
        this.readFileBase64(file.tempFilePath)
          .then((base64) => {
            const parts = file.tempFilePath.split(/[\\/]/);
            this.setData({
              [`${section}Materials.${key}`]: {
                image_base64: base64,
                file_name: parts[parts.length - 1] || `${key}.jpg`
              }
            });
          })
          .catch(() => wx.showToast({ title: '照片读取失败', icon: 'none' }));
      }
    });
  },

  clearYardMaterial(e) {
    const section = e.currentTarget.dataset.section;
    const key = e.currentTarget.dataset.key;
    if (!section || !key || this.data.submitting) return;
    this.setData({ [`${section}Materials.${key}`]: { file_name: '', image_base64: '' } });
  },

  submitDepart() {
    if (!this.data.canWriteSelectedDate) {
      wx.showToast({ title: '未来日期只能查看计划', icon: 'none' });
      return;
    }
    if (!this.data.assignments.length) {
      wx.showToast({ title: '所选日期没有可关联任务', icon: 'none' });
      return;
    }
    if (!this.allChecked(this.data.preflightItems, this.data.preflightChecked)) {
      wx.showToast({ title: '请先完成全部出库确认项', icon: 'none' });
      return;
    }
    const sleepHours = Number(this.data.departForm.sleep_hours || 0);
    if (!sleepHours) {
      wx.showToast({ title: '请填写睡眠时间', icon: 'none' });
      return;
    }
    const departTime = this.normalizeTime(this.data.departForm.depart_time);
    if (!departTime) {
      wx.showToast({ title: '请填写出库时间', icon: 'none' });
      return;
    }
    const alcoholAttachment = this.yardAttachment('depart', 'alcohol', 'alcohol_test_out');
    const isUpdate = this.data.departSubmitted || this.data.vehicleStatusText === '已出库' || this.data.vehicleStatusText === '已入库';
    if (!isUpdate && !alcoholAttachment) {
      wx.showToast({ title: '请上传出库酒精测试', icon: 'none' });
      return;
    }
    const businessDate = this.data.selectedDate || this.data.today;
    this.submitYardEvent('depart_yard', {
      event_time: `${businessDate} ${departTime}:00`,
      location_text: '司机端点呼出库',
      note: JSON.stringify({
        action: isUpdate ? 'depart_yard_update' : 'depart_yard',
        depart_time: departTime,
        sleep_hours: sleepHours,
        checks: this.checkedKeys(this.data.preflightChecked)
      })
    }, isUpdate ? '出库信息已保存' : '已出库', {
      beforeEvents: alcoholAttachment ? [{
        event_type: 'alcohol_test_out',
        event_time: `${businessDate} ${departTime}:00`,
        location_text: '司机端出库酒精测试',
        attachments: [alcoholAttachment],
        note: JSON.stringify({ action: isUpdate ? 'alcohol_test_out_update' : 'alcohol_test_out' })
      }] : []
    });
  },

  submitReturn() {
    if (!this.data.canWriteSelectedDate) {
      wx.showToast({ title: '未来日期只能查看计划', icon: 'none' });
      return;
    }
    if (!this.data.assignments.length) {
      wx.showToast({ title: '所选日期没有可关联任务', icon: 'none' });
      return;
    }
    if (!this.allChecked(this.data.returnItems, this.data.returnChecked)) {
      wx.showToast({ title: '请先完成全部入库确认项', icon: 'none' });
      return;
    }
    const restText = String(this.data.returnForm.rest_hours || '').trim();
    if (!restText) {
      wx.showToast({ title: '请填写休息时间', icon: 'none' });
      return;
    }
    const restHours = Number(restText);
    if (Number.isNaN(restHours)) {
      wx.showToast({ title: '休息时间格式不正确', icon: 'none' });
      return;
    }
    const returnTime = this.normalizeTime(this.data.returnForm.return_time);
    if (!returnTime) {
      wx.showToast({ title: '请填写入库时间', icon: 'none' });
      return;
    }
    const alcoholAttachment = this.yardAttachment('return', 'alcohol', 'alcohol_test_in');
    const isUpdate = this.data.returnSubmitted || this.data.vehicleStatusText === '已入库';
    if (!isUpdate && !alcoholAttachment) {
      wx.showToast({ title: '请上传入库酒精测试', icon: 'none' });
      return;
    }
    const businessDate = this.data.selectedDate || this.data.today;
    this.submitYardEvent('return_yard', {
      event_time: `${businessDate} ${returnTime}:00`,
      location_text: '司机端点呼入库',
      note: JSON.stringify({
        action: isUpdate ? 'return_yard_update' : 'return_yard',
        return_time: returnTime,
        rest_hours: restHours,
        checks: this.checkedKeys(this.data.returnChecked)
      })
    }, isUpdate ? '入库信息已保存' : '已入库，今日工作结束', {
      beforeEvents: alcoholAttachment ? [{
        event_type: 'alcohol_test_in',
        event_time: `${businessDate} ${returnTime}:00`,
        location_text: '司机端入库酒精测试',
        attachments: [alcoholAttachment],
        note: JSON.stringify({ action: isUpdate ? 'alcohol_test_in_update' : 'alcohol_test_in' })
      }] : []
    });
  },

  yardAttachment(section, key, kind) {
    const group = section === 'depart' ? this.data.departMaterials : this.data.returnMaterials;
    const item = group && group[key];
    if (!item || !item.image_base64) return null;
    return {
      kind,
      name: item.file_name || `${kind}.jpg`,
      image_base64: item.image_base64
    };
  },

  onDailyReportInput(event) {
    const key = event.currentTarget.dataset.key;
    this.setData({ [`dailyReport.${key}`]: event.detail.value });
  },

  saveDailyReport(event) {
    if (this.data.dailyReportSaving) return;
    const submit = event.currentTarget.dataset.submit === 'true';
    this.setData({ dailyReportSaving: true, message: '' });
    api.saveDriverDailyReport({
      driver_id: this.data.driverId,
      business_date: this.data.selectedDate || this.data.today,
      summary: this.data.dailyReport.summary,
      rest_hours: this.data.dailyReport.rest_hours,
      submit
    }).then((result) => {
      if (!result || result.success === false) throw result || new Error('daily_report_save_failed');
      const report = result.report || {};
      this.setData({
        dailyReportSaving: false,
        'dailyReport.status': report.status || (submit ? 'submitted' : 'draft'),
        'dailyReport.assignment_count': report.assignment_count || 0,
        'dailyReport.assignments': report.assignments || [],
        'dailyReport.summary': report.summary || '',
        'dailyReport.rest_hours': report.rest_hours === null || report.rest_hours === undefined ? '' : String(report.rest_hours),
        'dailyReport.submitted_at': report.submitted_at || '',
        reportEditorOpen: submit ? false : this.data.reportEditorOpen
      });
      wx.showToast({ title: submit ? '日报已提交' : '日报已保存', icon: 'success' });
      this.loadTasks();
    }).catch(() => {
      this.setData({ dailyReportSaving: false, message: '日报保存失败，请稍后重试。' });
    });
  },

  submitYardEvent(eventType, extra, successTitle, options = {}) {
    if (this.data.submitting) return;
    this.setData({ submitting: true, message: '' });
    const selectedAssignment = (this.data.assignments || [])[0] || {};
    const basePayload = {
      driver_id: this.data.driverId,
      assignment_id: selectedAssignment.assignment_id || selectedAssignment.id || undefined,
      order_id: selectedAssignment.order_id || undefined,
      vehicle_id: selectedAssignment.vehicle_id || undefined
    };
    const beforeEvents = options.beforeEvents || [];
    const calls = beforeEvents.map((item) => api.submitDriverWorkflowEvent({
      ...basePayload,
      ...item
    }));
    calls.push(api.submitDriverWorkflowEvent({
      ...basePayload,
      event_type: eventType,
      ...extra
    }));
    Promise.all(calls).then((results) => {
      this.setData({ submitting: false });
      const failed = (results || []).find((item) => item && item.success === false);
      if (failed) {
        wx.showToast({ title: this.reportError(failed), icon: 'none' });
        return;
      }
      const vehicleStatusText = eventType === 'return_yard' ? '已入库' : '已出库';
      wx.showToast({ title: successTitle, icon: 'success' });
      this.setData({
        vehicleStatusText,
        departSubmitted: eventType === 'depart_yard' ? true : this.data.departSubmitted,
        returnSubmitted: eventType === 'return_yard' ? true : this.data.returnSubmitted,
        departEditing: false,
        returnEditing: false
      });
      this.loadTasks();
    }).catch(() => {
      this.setData({ submitting: false });
      wx.showToast({ title: '提交失败', icon: 'none' });
    });
  },

  submitReport(item, reportType, extra, successTitle, afterSuccess) {
    if (this.data.submitting) return;
    this.setData({ submitting: true, message: '' });
    api.submitDriverReport({
      driver_id: this.data.driverId,
      assignment_id: item.assignment_id || item.id,
      report_type: reportType,
      ...extra
    }).then((result) => {
      this.setData({ submitting: false });
      if (result && result.success === false) {
        wx.showToast({ title: this.reportError(result), icon: 'none' });
        return;
      }
      wx.showToast({ title: successTitle, icon: 'success' });
      if (typeof afterSuccess === 'function') {
        afterSuccess(result);
        return;
      }
      this.loadTasks();
    }).catch(() => {
      this.setData({ submitting: false });
      wx.showToast({ title: '提交失败', icon: 'none' });
    });
  },

  reportError(result) {
    return {
      invalid_workflow_attachment: '材料格式不正确',
      invalid_workflow_attachments: '材料格式不正确',
      invalid_image_base64: '照片读取失败',
      image_too_large: '照片超过 5MB',
      execution_status_duplicate_or_regression_not_allowed: '状态已更新，请刷新任务',
      execution_status_skip_not_allowed: '请按流程顺序操作',
      assignment_not_found_for_driver: '未找到司机任务'
    }[result && result.error] || '提交失败';
  },

  buildWeekDays(rows, baseDate, today, selectedDate) {
    const base = this.parseDate(baseDate || today);
    return Array.from({ length: 15 }).map((_, index) => {
      const date = this.addDays(base, index - 7);
      return this.decorateCalendarDay(rows, date, today, selectedDate || baseDate || today);
    });
  },

  buildCalendarState(rows, selectedDate, today) {
    const safeToday = today || this.today();
    const safeSelectedDate = selectedDate || safeToday;
    return {
      weekDays: this.buildWeekDays(rows || [], safeSelectedDate, safeToday, safeSelectedDate),
      monthDays: this.buildMonthDays(rows || [], safeSelectedDate, safeToday, safeSelectedDate),
      monthLabel: this.formatMonthLabel(safeSelectedDate),
      selectedDayAnchor: this.dayAnchor(safeSelectedDate)
    };
  },

  buildMonthDays(rows, baseDate, today, selectedDate) {
    const base = this.parseDate(baseDate || today);
    const first = new Date(base.getFullYear(), base.getMonth(), 1);
    const total = new Date(base.getFullYear(), base.getMonth() + 1, 0).getDate();
    const days = [];
    const prefix = first.getDay();
    for (let index = 0; index < prefix; index += 1) {
      days.push({ date: '', day: '', week: '', count: 0, selected: false, today: false, holiday: false, empty: true });
    }
    Array.from({ length: total }).forEach((_, index) => {
      const date = this.addDays(first, index);
      days.push(this.decorateCalendarDay(rows, date, today, selectedDate || baseDate || today));
    });
    while (days.length % 7 !== 0) {
      days.push({ date: '', day: '', week: '', count: 0, selected: false, today: false, holiday: false, empty: true });
    }
    return days;
  },

  decorateCalendarDay(rows, date, today, selectedDate) {
    const dateText = this.formatDate(date);
    const count = rows.filter((item) => this.isOnDate(item, dateText)).length;
    const weekIndex = date.getDay();
    const holiday = weekIndex === 0 || weekIndex === 6 || this.isJapanHoliday(dateText);
    return {
      date: dateText,
      day: String(date.getDate()),
      week: ['日', '一', '二', '三', '四', '五', '六'][weekIndex],
      count,
      selected: dateText === (selectedDate || today),
      today: dateText === today,
      holiday,
      anchor: this.dayAnchor(dateText)
    };
  },

  isJapanHoliday(dateText) {
    return [
      '2026-01-01',
      '2026-01-12',
      '2026-02-11',
      '2026-02-23',
      '2026-03-20',
      '2026-04-29',
      '2026-05-03',
      '2026-05-04',
      '2026-05-05',
      '2026-05-06',
      '2026-07-20',
      '2026-08-11',
      '2026-09-21',
      '2026-09-22',
      '2026-09-23',
      '2026-10-12',
      '2026-11-03',
      '2026-11-23'
    ].indexOf(dateText) >= 0;
  },

  markSelected(days, date) {
    return (days || []).map((item) => ({ ...item, selected: item.date === date }));
  },

  resolveSelectedDate(rows, currentDate) {
    if ((rows || []).some((item) => this.isOnDate(item, currentDate))) return currentDate;
    const active = (rows || [])
      .filter((item) => OPEN_STATUSES.indexOf(item.rawStatus) >= 0)
      .sort((a, b) => `${a.order_date || ''} ${a.start_time || ''}`.localeCompare(`${b.order_date || ''} ${b.start_time || ''}`))[0];
    if (active && active.order_date) return active.order_date;
    const first = (rows || [])
      .slice()
      .sort((a, b) => `${a.order_date || ''} ${a.start_time || ''}`.localeCompare(`${b.order_date || ''} ${b.start_time || ''}`))[0];
    return (first && first.order_date) || currentDate;
  },

  allChecked(items, values) {
    return items.every((item) => values[item.key]);
  },

  checkedKeys(values) {
    return Object.keys(values || {}).filter((key) => values[key]);
  },

  isOnDate(item, date) {
    const start = item.order_date || date;
    const end = item.end_date || start;
    return start <= date && end >= date;
  },

  normalizeTime(value) {
    const text = String(value || '').trim();
    const match = text.match(/^(\d{1,2}):(\d{2})$/);
    if (!match) return '';
    const hour = Number(match[1]);
    const minute = Number(match[2]);
    if (hour > 23 || minute > 59) return '';
    return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
  },

  nowTime() {
    const date = new Date();
    return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
  },

  readFileBase64(path) {
    return new Promise((resolve, reject) => {
      wx.getFileSystemManager().readFile({
        filePath: path,
        encoding: 'base64',
        success: (res) => resolve(res.data),
        fail: reject
      });
    });
  },

  today() {
    return this.formatDate(new Date());
  },

  parseDate(value) {
    const parts = String(value || '').split('-').map(Number);
    return new Date(parts[0], (parts[1] || 1) - 1, parts[2] || 1);
  },

  addDays(date, days) {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
  },

  formatDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  },

  dayAnchor(dateText) {
    return `day${String(dateText || '').replace(/-/g, '')}`;
  },

  formatDayLabel(dateText) {
    const date = this.parseDate(dateText);
    return `${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getDate()).padStart(2, '0')}`;
  },

  formatMonthLabel(dateText) {
    const date = this.parseDate(dateText);
    return `${date.getFullYear()}年${String(date.getMonth() + 1).padStart(2, '0')}月`;
  }
});

