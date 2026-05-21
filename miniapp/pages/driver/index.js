const api = require('../../utils/api');
const offlineQueue = require('../../utils/offlineQueue');

const STATUS_TEXT = {
  assigned: '待确认',
  confirmed: '已确认',
  departed: '已出库',
  arrived: '已到达',
  in_service: '服务中',
  completed: '已完成',
  returned: '已归库'
};

const ORDER_FLOW = {
  assigned: { kind: 'report', event: 'confirm_order', label: '确认接单', hint: '确认后订单进入今日执行。' },
  confirmed: { kind: 'report', event: 'depart_yard', label: '开启第一单', hint: '完成出库后可开始第一单。' },
  departed: { kind: 'report', event: 'arrive_pickup', label: '到达上车点', hint: '到达后先拍等待照片。' },
  arrived: { kind: 'photo', event: 'arrive_waiting_photo', label: '上传到达等待照片', hint: '客人未上车前拍照留证。' },
  in_service: { kind: 'photo', event: 'dropoff_photo', label: '上传送达照片', hint: '送达后再点行程结束。' },
  completed: { kind: 'report', event: 'return_yard', label: '行程结束 / 回库', hint: '若仍有下一单，先开启下一单。' }
};

const PHOTO_STEPS = [
  { event: 'arrive_waiting_photo', title: '到达拍照', hint: '到达上车点，等待客人照片' },
  { event: 'pickup_photo', title: '接上客人拍照', hint: '客人上车后拍照' },
  { event: 'dropoff_photo', title: '送达拍照', hint: '客人下车后拍照' }
];

const PREFLIGHT_ITEMS = [
  { key: 'check_light', label: '车灯正常' },
  { key: 'check_brake', label: '刹车正常' },
  { key: 'check_body', label: '车身无新损伤' },
  { key: 'has_license', label: '已携带驾照' },
  { key: 'has_attendant_cert', label: '已携带乘务员证' },
  { key: 'alcohol_ok', label: '酒精测试通过' },
  { key: 'sleep_ok', label: '睡眠充足' }
];

Page({
  data: {
    driverId: 1,
    driverName: '司机',
    today: '',
    nowText: '',
    statusMode: 'rest',
    statusText: '休息',
    isOnline: true,
    loading: false,
    submitting: false,
    uploadingEvidence: false,
    activeTab: 'orders',
    assignments: [],
    activeAssignments: [],
    completedAssignments: [],
    pendingConfirm: [],
    selected: null,
    nextOrder: null,
    nextAction: null,
    nextActionLabel: '今日暂无任务',
    nextActionHint: '等待调度派单。',
    note: '',
    locationText: '',
    latitude: '',
    longitude: '',
    notifications: [],
    pendingCount: 0,
    offlineText: '',
    evidenceUploads: [],
    photoSteps: PHOTO_STEPS,
    preflightItems: PREFLIGHT_ITEMS,
    preflightChecked: {},
    cacheKey: ''
  },

  onLoad(options) {
    const driverId = Number(options.driver_id || wx.getStorageSync('driver_id') || 1);
    const today = this.today();
    this.setData({
      driverId,
      today,
      cacheKey: `driver_workbench_v2_${driverId}`,
      nowText: this.timeNow()
    });
    wx.setStorageSync('driver_id', driverId);
    this.startClock();
    this.bindNetworkWatcher();
    this.restoreCache();
    this.refreshPendingCount();
    this.loadAll({ force: true });
  },

  onShow() {
    this.refreshPendingCount();
    this.loadAll({ silent: true });
  },

  onUnload() {
    if (this.clockTimer) clearInterval(this.clockTimer);
  },

  startClock() {
    if (this.clockTimer) clearInterval(this.clockTimer);
    this.clockTimer = setInterval(() => {
      this.setData({ nowText: this.timeNow() });
    }, 15000);
  },

  bindNetworkWatcher() {
    wx.getNetworkType({
      success: (res) => this.applyNetwork(res.networkType !== 'none')
    });
    wx.onNetworkStatusChange((res) => {
      this.applyNetwork(res.isConnected);
      if (res.isConnected) {
        this.retryPendingTasks();
        this.loadAll({ force: true, silent: true });
      }
    });
  },

  applyNetwork(online) {
    this.setData({
      isOnline: online,
      offlineText: online ? '' : '当前离线，提交会进入待补发。'
    });
  },

  onDriverInput(e) {
    const driverId = Number(e.detail.value || 0);
    this.setData({ driverId, cacheKey: `driver_workbench_v2_${driverId}` });
    wx.setStorageSync('driver_id', driverId);
  },

  onSwitchDriver() {
    this.setData({
      assignments: [],
      activeAssignments: [],
      completedAssignments: [],
      pendingConfirm: [],
      selected: null,
      nextOrder: null,
      nextAction: null
    });
    this.restoreCache();
    this.loadAll({ force: true });
  },

  onTabChange(e) {
    this.setData({ activeTab: e.currentTarget.dataset.tab });
  },

  onSelectOrder(e) {
    const assignmentId = Number(e.currentTarget.dataset.id);
    const selected = this.data.assignments.find((item) => Number(item.assignment_id) === assignmentId);
    this.applySelection(selected);
  },

  applySelection(selected) {
    if (!selected) return;
    const nextOrder = this.pickNextOrder(selected);
    const nextAction = this.computeNextAction(selected);
    this.setData({
      selected,
      nextOrder,
      nextAction,
      nextActionLabel: nextAction.label,
      nextActionHint: nextAction.hint
    });
    this.updateEvidence(selected);
    this.updateTopStatus();
  },

  loadAll(options = {}) {
    const silent = !!options.silent;
    if (!this.data.isOnline) {
      this.restoreCache();
      return;
    }
    this.setData({ loading: !silent });
    Promise.all([
      api.driverWorkbench(this.data.driverId),
      api.driverAssignments(this.data.driverId),
      api.driverNotifications(this.data.driverId)
    ]).then(([workbench, assRes, noteRes]) => {
      const all = (assRes.assignments || [])
        .filter((item) => !item.order_date || item.order_date === this.data.today)
        .map((item) => ({ ...item, status_label: STATUS_TEXT[item.execution_status || 'assigned'] || item.execution_status || '-' }))
        .sort((a, b) => `${a.start_time || ''}${a.assignment_id}`.localeCompare(`${b.start_time || ''}${b.assignment_id}`));
      const pendingConfirm = all.filter((x) => (x.execution_status || 'assigned') === 'assigned');
      const completed = all.filter((x) => ['completed', 'returned'].includes(x.execution_status || ''));
      const active = all.filter((x) => !['completed', 'returned'].includes(x.execution_status || ''));
      const selected = this.pickCurrentSelection(all, workbench.current_assignment);
      const nextOrder = this.pickNextOrder(selected, all);
      const nextAction = this.computeNextAction(selected);
      const checked = this.data.preflightChecked || {};
      const driverName = selected && selected.driver_name ? selected.driver_name : (workbench.driver_name || `司机${this.data.driverId}`);
      this.setData({
        loading: false,
        driverName,
        assignments: all,
        pendingConfirm,
        completedAssignments: completed,
        activeAssignments: active,
        selected,
        nextOrder,
        nextAction,
        nextActionLabel: nextAction.label,
        nextActionHint: nextAction.hint,
        notifications: noteRes.notifications || [],
        preflightChecked: checked
      });
      this.updateTopStatus();
      wx.setStorageSync(this.data.cacheKey, {
        driverName,
        assignments: all,
        notifications: noteRes.notifications || [],
        selectedId: selected ? selected.assignment_id : null
      });
      if (selected) this.updateEvidence(selected);
    }).catch(() => {
      this.setData({ loading: false, offlineText: '同步失败，已显示缓存。' });
      this.restoreCache();
    });
  },

  pickCurrentSelection(assignments, current) {
    if (!assignments.length) return null;
    if (current && current.assignment_id) {
      const found = assignments.find((x) => Number(x.assignment_id) === Number(current.assignment_id));
      if (found) return found;
    }
    const saved = wx.getStorageSync(`${this.data.cacheKey}_selected`);
    if (saved) {
      const found = assignments.find((x) => Number(x.assignment_id) === Number(saved));
      if (found) return found;
    }
    return assignments.find((x) => ['confirmed', 'departed', 'arrived', 'in_service'].includes(x.execution_status || '')) || assignments[0];
  },

  pickNextOrder(selected, list) {
    const source = list || this.data.assignments;
    if (!selected || !source.length) return null;
    const idx = source.findIndex((x) => Number(x.assignment_id) === Number(selected.assignment_id));
    if (idx < 0) return null;
    for (let i = idx + 1; i < source.length; i += 1) {
      if (!['completed', 'returned'].includes(source[i].execution_status || '')) return source[i];
    }
    return null;
  },

  computeNextAction(selected) {
    if (!selected) return { kind: 'idle', event: 'idle', label: '今日暂无任务', hint: '等待调度派单。' };
    const status = selected.execution_status || 'assigned';
    if (status === 'confirmed' && this.data.statusMode !== 'departed') {
      return { kind: 'preflight', event: 'roll_call_out', label: '点呼出库', hint: '先完成出库检查，再点呼出库。' };
    }
    return ORDER_FLOW[status] || { kind: 'report', event: 'complete_order', label: '行程结束', hint: '完成本单。' };
  },

  updateTopStatus() {
    const selected = this.data.selected;
    let mode = 'rest';
    let text = '休息';
    if (selected) {
      if (['departed', 'arrived', 'in_service'].includes(selected.execution_status || '')) {
        mode = 'departed';
        text = '已出库';
      } else if (['assigned', 'confirmed'].includes(selected.execution_status || '')) {
        mode = 'ready';
        text = '未出库';
      } else if (['completed', 'returned'].includes(selected.execution_status || '')) {
        mode = 'rest';
        text = '休息';
      }
    }
    this.setData({ statusMode: mode, statusText: text });
  },

  onTogglePreflight(e) {
    const key = e.currentTarget.dataset.key;
    const next = { ...this.data.preflightChecked, [key]: !this.data.preflightChecked[key] };
    this.setData({ preflightChecked: next });
  },

  allPreflightChecked() {
    return PREFLIGHT_ITEMS.every((item) => this.data.preflightChecked[item.key]);
  },

  onPrimaryAction() {
    const action = this.data.nextAction;
    const selected = this.data.selected;
    if (!action || !selected || this.data.submitting || this.data.uploadingEvidence) return;
    if (action.kind === 'photo') {
      this.uploadEvidence(action.event);
      return;
    }
    if (action.kind === 'preflight') {
      if (!this.allPreflightChecked()) {
        wx.showToast({ title: '请先完成全部出库检查', icon: 'none' });
        return;
      }
      this.submitWorkflowEvent('roll_call_out');
      this.submitReport('depart_yard');
      return;
    }
    this.submitReport(action.event);
  },

  submitWorkflowEvent(eventType) {
    const selected = this.data.selected;
    if (!selected) return;
    const payload = {
      driver_id: this.data.driverId,
      assignment_id: selected.assignment_id,
      event_type: eventType,
      latitude: this.data.latitude,
      longitude: this.data.longitude,
      location_text: this.data.locationText || '司机端上报',
      note: this.data.note
    };
    if (!this.data.isOnline) {
      this.queueTask('workflow', payload, '离线已保存，待补发');
      return;
    }
    api.submitDriverWorkflowEvent(payload).catch(() => this.queueTask('workflow', payload, '流程记录失败，已入补发'));
  },

  submitReport(reportType) {
    const selected = this.data.selected;
    if (!selected) return;
    this.setData({ submitting: true });
    this.getLocationPayload().then((location) => {
      const payload = {
        driver_id: this.data.driverId,
        assignment_id: selected.assignment_id,
        report_type: reportType,
        latitude: location.latitude,
        longitude: location.longitude,
        location_text: location.location_text,
        note: this.data.note
      };
      this.submitOrQueue('report', payload, api.submitDriverReport, '状态已提交');
    }).catch(() => {
      const payload = {
        driver_id: this.data.driverId,
        assignment_id: selected.assignment_id,
        report_type: reportType,
        latitude: this.data.latitude,
        longitude: this.data.longitude,
        location_text: this.data.locationText || '司机手动定位',
        note: this.data.note
      };
      this.submitOrQueue('report', payload, api.submitDriverReport, '状态已提交');
    });
  },

  submitOrQueue(type, payload, submitter, successText) {
    if (!this.data.isOnline) {
      this.queueTask(type, payload, '离线已保存，待补发');
      this.setData({ submitting: false });
      return;
    }
    submitter(payload).then((res) => {
      this.setData({ submitting: false });
      if (!res.success) {
        this.queueTask(type, payload, '提交失败，已入补发');
        return;
      }
      wx.showToast({ title: successText, icon: 'success' });
      if (payload.report_type === 'return_yard') {
        this.setData({ preflightChecked: {} });
      }
      this.loadAll({ force: true, silent: true });
    }).catch(() => {
      this.setData({ submitting: false });
      this.queueTask(type, payload, '提交失败，已入补发');
    });
  },

  getLocationPayload() {
    return new Promise((resolve, reject) => {
      wx.getLocation({
        type: 'gcj02',
        success: (loc) => {
          const locationText = this.data.locationText || '微信定位';
          this.setData({ latitude: loc.latitude, longitude: loc.longitude, locationText });
          resolve({ latitude: loc.latitude, longitude: loc.longitude, location_text: locationText });
        },
        fail: reject
      });
    });
  },

  onUploadLocation() {
    const selected = this.data.selected;
    if (!selected) return;
    this.getLocationPayload().then((location) => {
      const payload = {
        driver_id: this.data.driverId,
        assignment_id: selected.assignment_id,
        latitude: location.latitude,
        longitude: location.longitude,
        location_text: location.location_text,
        source: 'driver_mobile_manual'
      };
      this.submitOrQueue('location', payload, api.submitDriverLocation, '位置已上报');
    }).catch(() => wx.showToast({ title: '定位失败', icon: 'none' }));
  },

  onNavigatePickup() {
    this.openNavigation(this.data.selected && this.data.selected.pickup_location, '上车点');
  },

  onNavigateDropoff() {
    this.openNavigation(this.data.selected && this.data.selected.dropoff_location, '终点');
  },

  openNavigation(address, name) {
    const lat = Number(this.data.latitude);
    const lng = Number(this.data.longitude);
    const googleUrl = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(address || name)}`;
    if (lat && lng && wx.openLocation) {
      wx.openLocation({ latitude: lat, longitude: lng, scale: 16, name, address: address || name });
      return;
    }
    wx.showModal({
      title: '导航提示',
      content: `${address || name}\n暂无坐标，请复制地址到导航软件。\nGoogle Maps: ${googleUrl}`,
      confirmText: '复制地址',
      cancelText: '关闭',
      success: (res) => {
        if (res.confirm && address) wx.setClipboardData({ data: address });
      }
    });
  },

  onCallGuest() {
    const phone = this.data.selected && this.data.selected.guest_contact;
    if (!phone) {
      wx.showToast({ title: '暂无电话', icon: 'none' });
      return;
    }
    wx.makePhoneCall({ phoneNumber: phone });
  },

  onPhotoUploadTap(e) {
    this.uploadEvidence(e.currentTarget.dataset.event);
  },

  uploadEvidence(eventType) {
    const selected = this.data.selected;
    if (!selected || this.data.uploadingEvidence) return;
    if (!this.data.isOnline) {
      wx.showToast({ title: '离线不能上传照片', icon: 'none' });
      return;
    }
    wx.chooseImage({
      count: 1,
      sizeType: ['compressed'],
      sourceType: ['camera', 'album'],
      success: (ret) => {
        const filePath = ret.tempFilePaths && ret.tempFilePaths[0];
        if (!filePath) return;
        this.setData({ uploadingEvidence: true });
        wx.getFileSystemManager().readFile({
          filePath,
          encoding: 'base64',
          success: (file) => {
            api.uploadDriverEvidence({
              driver_id: this.data.driverId,
              assignment_id: selected.assignment_id,
              evidence_type: eventType,
              image_base64: file.data,
              note: this.data.note
            }).then((res) => {
              this.setData({ uploadingEvidence: false });
              wx.showToast({ title: res.success ? '照片已上传' : '上传失败', icon: res.success ? 'success' : 'none' });
              this.updateEvidence(selected);
              if (eventType === 'arrive_waiting_photo') {
                this.setData({
                  nextAction: { kind: 'photo', event: 'pickup_photo', label: '上传接客照片', hint: '客人上车后拍照。' },
                  nextActionLabel: '上传接客照片',
                  nextActionHint: '客人上车后拍照。'
                });
              }
              if (eventType === 'dropoff_photo') {
                this.setData({
                  nextAction: { kind: 'report', event: 'complete_order', label: '订单完了', hint: '提交订单完成。' },
                  nextActionLabel: '订单完了',
                  nextActionHint: '提交订单完成。'
                });
              }
            }).catch(() => {
              this.setData({ uploadingEvidence: false });
              wx.showToast({ title: '上传失败', icon: 'none' });
            });
          },
          fail: () => {
            this.setData({ uploadingEvidence: false });
            wx.showToast({ title: '读取照片失败', icon: 'none' });
          }
        });
      }
    });
  },

  updateEvidence(selected) {
    if (!selected || !this.data.isOnline) return;
    api.driverEvidence(this.data.driverId, selected.assignment_id)
      .then((res) => this.setData({ evidenceUploads: res.evidence || [] }))
      .catch(() => this.setData({ evidenceUploads: [] }));
  },

  onInput(e) {
    this.setData({ [e.currentTarget.dataset.key]: e.detail.value });
  },

  queueTask(type, payload, message) {
    offlineQueue.enqueue(type, payload);
    this.refreshPendingCount();
    this.setData({ offlineText: message });
    wx.showToast({ title: message, icon: 'none' });
  },

  retryPendingTasks() {
    const tasks = offlineQueue.list(this.data.driverId);
    if (!tasks.length || !this.data.isOnline) return;
    const done = [];
    this.setData({ submitting: true });
    const run = tasks.reduce((p, task) => p.then(() => {
      const call = task.type === 'location'
        ? api.submitDriverLocation(task.payload)
        : task.type === 'workflow'
          ? api.submitDriverWorkflowEvent(task.payload)
          : api.submitDriverReport(task.payload);
      return call.then((res) => {
        if (res.success) done.push(task.id);
      }).catch(() => undefined);
    }), Promise.resolve());
    run.then(() => {
      offlineQueue.clearDone(done);
      this.setData({ submitting: false });
      this.refreshPendingCount();
      this.loadAll({ silent: true });
    });
  },

  refreshPendingCount() {
    this.setData({ pendingCount: offlineQueue.count(this.data.driverId) });
  },

  restoreCache() {
    const cache = wx.getStorageSync(this.data.cacheKey);
    if (!cache) return;
    const assignments = cache.assignments || [];
    const selected = assignments.find((x) => Number(x.assignment_id) === Number(cache.selectedId)) || assignments[0] || null;
    const active = assignments.filter((x) => !['completed', 'returned'].includes(x.execution_status || ''));
    const completed = assignments.filter((x) => ['completed', 'returned'].includes(x.execution_status || ''));
    const pendingConfirm = assignments.filter((x) => (x.execution_status || 'assigned') === 'assigned');
    const nextOrder = this.pickNextOrder(selected, assignments);
    const nextAction = this.computeNextAction(selected);
    this.setData({
      driverName: cache.driverName || `司机${this.data.driverId}`,
      assignments,
      activeAssignments: active,
      completedAssignments: completed,
      pendingConfirm,
      selected,
      nextOrder,
      nextAction,
      nextActionLabel: nextAction.label,
      nextActionHint: nextAction.hint,
      notifications: cache.notifications || []
    });
    this.updateTopStatus();
  },

  timeNow() {
    const now = new Date();
    return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  },

  today() {
    return new Date().toISOString().slice(0, 10);
  }
});
