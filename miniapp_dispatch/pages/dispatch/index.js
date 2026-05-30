const api = require('../../utils/api');

const SAMPLE_TEXT = [
  '5.29 08:00 KIX接机大阪市内 3代 绿450',
  '5.29 10:20 大阪市内-京都市内 包车 3代 1500',
  '5.29 13:30 京都酒店-关西机场 3代 儿童座椅 绿600'
].join('\n');

const AIRPORT_WORDS = ['kix', '机场', '空港', '关西', '关空', '羽田', '成田', '伊丹', '神户机场'];

Page({
  data: {
    importOpen: false,
    importText: SAMPLE_TEXT,
    pendingRows: [],
    charterRows: [],
    pickupRows: [],
    dropoffRows: [],
    drivers: [],
    vehicles: [],
    assignments: [],
    selectedKeys: [],
    driverId: '',
    vehicleId: '',
    editingKey: '',
    editing: {},
    sortMode: false,
    charterCollapsed: false,
    loading: false,
    message: '',
    conflictText: '',
    preview: {
      orderCount: 0,
      driverName: '未选司机',
      vehicleName: '未选车辆'
    },
    canAssign: false
  },
  _lastTapKey: '',
  _lastTapAt: 0,
  _tapTimer: null,

  onShow() {
    api.setActiveTab('/pages/dispatch/index');
    this.refreshTabBar();
    if (!api.canAccess('dispatch')) {
      wx.showToast({ title: '当前账号没有派车权限', icon: 'none' });
      wx.switchTab({ url: '/pages/index/index' });
      return;
    }
    this.loadAll();
  },

  refreshTabBar() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().refresh();
    }
  },

  toggleImport() {
    this.setData({ importOpen: !this.data.importOpen });
  },

  toggleCharter() {
    this.setData({ charterCollapsed: !this.data.charterCollapsed });
  },

  onImportText(e) {
    this.setData({ importText: e.detail.value });
  },

  noop() {},

  parseOrders() {
    const text = String(this.data.importText || '').trim();
    if (!text) {
      wx.showToast({ title: '请先粘贴订单文本', icon: 'none' });
      return;
    }
    this.setData({ loading: true, message: '', conflictText: '' });
    api.parseText(text)
      .then((res) => {
        this.setData({
          loading: false,
          importOpen: false,
          message: `已解析 ${res.count || 0} 条，系统已按包车、接机、送机分类。`
        });
        this.loadAll();
      })
      .catch(() => {
        this.setData({ loading: false, conflictText: '解析失败，请检查后端服务或订单文本格式。' });
      });
  },

  loadAll() {
    this.setData({ loading: true });
    Promise.all([
      api.drafts().catch(() => ({ drafts: [] })),
      api.unassignedOrders().catch(() => ({ orders: [] })),
      api.drivers(),
      api.vehicles(),
      api.assignments()
    ])
      .then(([draftsRes, ordersRes, driversRes, vehiclesRes, assignmentsRes]) => {
        const drafts = (draftsRes.drafts || [])
          .filter((item) => item.parse_status !== 'confirmed' && item.parse_status !== 'discarded')
          .map((item) => this.decoratePendingRow({ ...item, kind: 'draft' }));
        const orders = (ordersRes.orders || []).map((item) => this.decoratePendingRow({ ...item, kind: 'order' }));
        const pendingRows = this.sortPendingRows(drafts.concat(orders)).slice(0, 160);
        const assignments = assignmentsRes.assignments || [];
        this.setData({
          pendingRows,
          ...this.groupPendingRows(pendingRows),
          drivers: this.decorateDrivers(driversRes.drivers || [], assignments),
          vehicles: this.decorateVehicles(vehiclesRes.vehicles || [], assignments),
          assignments,
          loading: false
        });
        this.updatePreview();
      })
      .catch(() => {
        this.setData({ loading: false, conflictText: '加载派车数据失败，请确认后端在线。' });
      });
  },

  decoratePendingRow(row) {
    const key = `${row.kind}-${row.id}`;
    const selected = this.data.selectedKeys.includes(key);
    const risks = this.getRowRisks(row);
    const dispatchKind = this.classifyOrder(row);
    const oid = row.oid || this.formatDraftNo(row);
    return {
      ...row,
      key,
      oid,
      selected,
      dispatchKind,
      riskText: risks.join(' / '),
      hasRisk: risks.length > 0,
      sourceText: row.kind === 'draft' ? '草稿' : '订单',
      typeText: dispatchKind === 'charter' ? '包车' : dispatchKind === 'dropoff' ? '送机' : '接机',
      timeText: `${row.order_date || '待确认日期'} ${row.start_time || '--:--'}-${row.end_time || '--:--'}`,
      compactTimeText: `${row.order_date || '待确认日期'} ${row.start_time || '--:--'}`,
      routeText: `${row.pickup_location || '待确认'} → ${row.dropoff_location || '待确认'}`,
      priceText: row.price ? `¥${row.price}` : '',
      charterDetailText: this.buildCharterDetail(row, risks)
    };
  },

  formatDraftNo(row) {
    const day = String(row.order_date || '').replace(/-/g, '').slice(2) || 'TMP';
    return `${day}-${String(row.id || '').padStart(3, '0')}`;
  },

  buildCharterDetail(row, risks) {
    const parts = [];
    if (row.vehicle_type) parts.push(row.vehicle_type);
    if (row.guest_name) parts.push(`客人 ${row.guest_name}`);
    if (row.guest_contact) parts.push(row.guest_contact);
    if (row.agency_name) parts.push(row.agency_name);
    if (row.remark) parts.push(row.remark);
    return parts.join(' · ');
  },

  classifyOrder(row) {
    const text = [
      row.order_type,
      row.pickup_location,
      row.dropoff_location,
      row.remark,
      row.raw_text
    ].filter(Boolean).join(' ').toLowerCase();
    const pickup = String(row.pickup_location || '').toLowerCase();
    const dropoff = String(row.dropoff_location || '').toLowerCase();
    if (text.includes('包车') || text.includes('包車') || text.includes('charter')) return 'charter';
    if (text.includes('送机') || text.includes('送機') || text.includes('airport_dropoff')) return 'dropoff';
    if (text.includes('接机') || text.includes('接機') || text.includes('airport_pickup')) return 'pickup';
    const pickupAirport = AIRPORT_WORDS.some((word) => pickup.includes(word));
    const dropoffAirport = AIRPORT_WORDS.some((word) => dropoff.includes(word));
    if (dropoffAirport && !pickupAirport) return 'dropoff';
    return 'pickup';
  },

  groupPendingRows(rows) {
    return {
      charterRows: rows.filter((item) => item.dispatchKind === 'charter'),
      pickupRows: rows.filter((item) => item.dispatchKind === 'pickup'),
      dropoffRows: rows.filter((item) => item.dispatchKind === 'dropoff')
    };
  },

  getRowRisks(row) {
    return [];
  },

  sortPendingRows(rows) {
    return rows.slice().sort((a, b) => {
      const left = `${a.order_date || ''} ${a.start_time || ''} ${a.pickup_location || ''}`;
      const right = `${b.order_date || ''} ${b.start_time || ''} ${b.pickup_location || ''}`;
      return left.localeCompare(right, 'zh-Hans-CN');
    });
  },

  decorateDrivers(drivers, assignments) {
    const selectedWindows = this.getSelectedWindows();
    return drivers.map((driver) => {
      const active = assignments.find((item) => Number(item.driver_id) === Number(driver.id));
      const conflict = this.hasConflict(assignments, 'driver_id', driver.id, selectedWindows);
      return {
        ...driver,
        displayName: this.formatDriverDisplayName(driver),
        selected: String(this.data.driverId) === String(driver.id),
        disabled: conflict,
        statusText: conflict ? '冲突' : (active ? '占用' : '空闲'),
        statusClass: conflict ? 'danger' : (active ? 'busy' : 'ok')
      };
    }).sort((a, b) => {
      if (a.disabled !== b.disabled) return a.disabled ? 1 : -1;
      if ((a.statusClass === 'busy') !== (b.statusClass === 'busy')) return a.statusClass === 'busy' ? 1 : -1;
      return String(a.name || '').localeCompare(String(b.name || ''), 'zh-Hans-CN');
    }).slice(0, 15);
  },

  formatDriverDisplayName(driver) {
    const raw = String(driver.display_name || driver.driver_name || driver.name || driver.driver_code || '未命名司机');
    return raw.replace(/(R00[0-9]司机[AB]?)[0-9A-Za-z_-]+$/, '$1');
  },

  decorateVehicles(vehicles, assignments) {
    const selectedWindows = this.getSelectedWindows();
    return vehicles.map((vehicle) => {
      const active = assignments.find((item) => Number(item.vehicle_id) === Number(vehicle.id));
      const conflict = this.hasConflict(assignments, 'vehicle_id', vehicle.id, selectedWindows);
      return {
        ...vehicle,
        selected: String(this.data.vehicleId) === String(vehicle.id),
        disabled: conflict,
        shortPlate: String(vehicle.plate_number || '').slice(-4) || vehicle.plate_number,
        statusText: conflict ? '冲突' : (active ? '占用' : '空闲'),
        statusClass: conflict ? 'danger' : (active ? 'busy' : 'ok')
      };
    }).sort((a, b) => {
      if (a.disabled !== b.disabled) return a.disabled ? 1 : -1;
      if ((a.statusClass === 'busy') !== (b.statusClass === 'busy')) return a.statusClass === 'busy' ? 1 : -1;
      return String(a.plate_number || '').localeCompare(String(b.plate_number || ''), 'ja-JP');
    }).slice(0, 15);
  },

  toggleRowByKey(key) {
    const selected = this.data.selectedKeys.slice();
    const index = selected.indexOf(key);
    if (index >= 0) selected.splice(index, 1);
    else selected.push(key);
    this.setData({ selectedKeys: selected });
    this.refreshRowsAndResources();
  },

  handleRowTap(e) {
    const key = e.currentTarget.dataset.key;
    const now = Date.now();
    if (this._lastTapKey === key && now - this._lastTapAt < 320) {
      if (this._tapTimer) {
        clearTimeout(this._tapTimer);
        this._tapTimer = null;
      }
      this._lastTapKey = '';
      this._lastTapAt = 0;
      this.startEditByKey(key);
      return;
    }
    this._lastTapKey = key;
    this._lastTapAt = now;
    if (this._tapTimer) clearTimeout(this._tapTimer);
    this._tapTimer = setTimeout(() => {
      this.toggleRowByKey(key);
      this._tapTimer = null;
    }, 220);
  },

  smartRouteSort() {
    const selectedSet = new Set(this.data.selectedKeys);
    const selected = this.data.pendingRows.filter((item) => selectedSet.has(item.key));
    if (!selected.length) {
      const pendingRows = this.sortPendingRows(this.data.pendingRows);
      this.setData({ pendingRows, ...this.groupPendingRows(pendingRows), message: '已按日期、时间和起点排序。' });
      return;
    }
    const rest = this.data.pendingRows.filter((item) => !selectedSet.has(item.key));
    const pendingRows = this.sortPendingRows(selected).concat(this.sortPendingRows(rest));
    this.setData({
      pendingRows,
      ...this.groupPendingRows(pendingRows),
      message: `已为 ${selected.length} 单按接龙顺序排序。`
    });
  },

  toggleSortMode() {
    this.setData({ sortMode: !this.data.sortMode });
  },

  enterSortMode(e) {
    const key = e.currentTarget.dataset.key;
    if (!this.data.selectedKeys.includes(key)) {
      this.setData({ selectedKeys: this.data.selectedKeys.concat(key) });
    }
    this.setData({ sortMode: true, message: '已进入排序模式，可用上移/下移调整派车顺序。' });
    this.refreshRowsAndResources();
  },

  moveRow(e) {
    const key = e.currentTarget.dataset.key;
    const direction = e.currentTarget.dataset.direction;
    const rows = this.data.pendingRows.slice();
    const index = rows.findIndex((item) => item.key === key);
    if (index < 0) return;
    const target = direction === 'up' ? index - 1 : index + 1;
    if (target < 0 || target >= rows.length) return;
    const current = rows[index];
    rows[index] = rows[target];
    rows[target] = current;
    this.setData({ pendingRows: rows, ...this.groupPendingRows(rows) });
  },

  startEdit(e) {
    this.startEditByKey(e.currentTarget.dataset.key);
  },

  startEditByKey(key) {
    const row = this.data.pendingRows.find((item) => item.key === key);
    if (!row) return;
    this.setData({
      editingKey: key,
      editing: {
        order_date: row.order_date || '',
        start_time: row.start_time || '',
        end_time: row.end_time || '',
        pickup_location: row.pickup_location || '',
        dropoff_location: row.dropoff_location || '',
        order_type: row.order_type || '',
        vehicle_type: row.vehicle_type || '',
        price: row.price || '',
        guest_name: row.guest_name || '',
        guest_contact: row.guest_contact || '',
        agency_name: row.agency_name || '',
        remark: row.remark || ''
      }
    });
  },

  onEditField(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [`editing.${field}`]: e.detail.value });
  },

  saveEdit() {
    const row = this.data.pendingRows.find((item) => item.key === this.data.editingKey);
    if (!row) return;
    this.saveRow(row, this.data.editing)
      .then(() => {
        wx.showToast({ title: '已保存' });
        this.setData({ editingKey: '', editing: {} });
        this.loadAll();
      })
      .catch(() => wx.showToast({ title: '保存失败', icon: 'none' }));
  },

  cancelEdit() {
    this.setData({ editingKey: '', editing: {} });
  },

  confirmRow(e) {
    const key = e.currentTarget.dataset.key;
    const row = this.data.pendingRows.find((item) => item.key === key);
    if (!row) return;
    this.ensureOrder(row)
      .then(() => {
        wx.showToast({ title: '已确认入库' });
        this.loadAll();
      })
      .catch(() => wx.showToast({ title: '确认失败', icon: 'none' }));
  },

  confirmSelectedDrafts() {
    const rows = this.selectedRows().filter((item) => item.kind === 'draft');
    if (!rows.length) {
      wx.showToast({ title: '请选择需要入库的草稿', icon: 'none' });
      return;
    }
    this.setData({ loading: true, conflictText: '', message: '' });
    rows.reduce((chain, row) => chain.then(() => this.ensureOrder(row)), Promise.resolve())
      .then(() => {
        wx.showToast({ title: '批量入库完成' });
        this.setData({
          loading: false,
          selectedKeys: this.data.selectedKeys.filter((key) => !rows.some((row) => row.key === key)),
          message: `已确认入库 ${rows.length} 条草稿。`
        });
        this.loadAll();
      })
      .catch(() => {
        this.setData({ loading: false, conflictText: '批量入库失败，请检查草稿字段。' });
      });
  },

  selectDriver(e) {
    const id = String(e.currentTarget.dataset.id);
    const item = this.data.drivers.find((driver) => String(driver.id) === id);
    if (item && item.disabled) {
      wx.showToast({ title: '该司机与所选订单时间冲突', icon: 'none' });
      return;
    }
    this.setData({ driverId: id });
    this.refreshRowsAndResources();
  },

  selectVehicle(e) {
    const id = String(e.currentTarget.dataset.id);
    const item = this.data.vehicles.find((vehicle) => String(vehicle.id) === id);
    if (item && item.disabled) {
      wx.showToast({ title: '该车辆与所选订单时间冲突', icon: 'none' });
      return;
    }
    this.setData({ vehicleId: id });
    this.refreshRowsAndResources();
  },

  refreshRowsAndResources() {
    const rows = this.data.pendingRows.map((row) => this.decoratePendingRow(row));
    this.setData({
      pendingRows: rows,
      ...this.groupPendingRows(rows),
      drivers: this.decorateDrivers(this.data.drivers, this.data.assignments),
      vehicles: this.decorateVehicles(this.data.vehicles, this.data.assignments)
    });
    this.updatePreview();
  },

  updatePreview() {
    const selectedRows = this.selectedRows();
    const driver = this.data.drivers.find((item) => String(item.id) === String(this.data.driverId));
    const vehicle = this.data.vehicles.find((item) => String(item.id) === String(this.data.vehicleId));
    this.setData({
      canAssign: Boolean(selectedRows.length && driver && vehicle),
      preview: {
        orderCount: selectedRows.length,
        driverName: driver ? driver.name : '未选司机',
        vehicleName: vehicle ? (vehicle.shortPlate || vehicle.plate_number) : '未选车辆'
      }
    });
  },

  selectedRows() {
    const selected = new Set(this.data.selectedKeys);
    return this.data.pendingRows.filter((item) => selected.has(item.key));
  },

  saveRow(row, payload) {
    if (row.kind === 'draft') return api.updateDraft(row.id, payload);
    return api.updateOrder(row.id, payload);
  },

  ensureOrder(row) {
    if (row.kind === 'order') return Promise.resolve(row.id);
    return api.confirmDraft(row.id).then((res) => res.order_id);
  },

  assignSelected() {
    const rows = this.selectedRows();
    if (!rows.length || !this.data.driverId || !this.data.vehicleId) {
      wx.showToast({ title: '请先选择订单、司机和车辆', icon: 'none' });
      return;
    }
    this.setData({ loading: true, conflictText: '', message: '' });
    rows.reduce((chain, row) => {
      return chain.then((ids) => {
        const payload = row.key === this.data.editingKey ? this.data.editing : row;
        return this.saveRow(row, payload)
          .then(() => this.ensureOrder(row))
          .then((id) => ids.concat(Number(id)));
      });
    }, Promise.resolve([]))
      .then((orderIds) => api.assignOrders({
        order_ids: orderIds,
        driver_id: Number(this.data.driverId),
        vehicle_id: Number(this.data.vehicleId)
      }))
      .then((res) => {
        if (res && res.success === false) {
          this.setData({ loading: false, conflictText: this.formatConflicts(res.conflicts || []) });
          return;
        }
        wx.showToast({ title: '派车成功' });
        this.setData({
          loading: false,
          selectedKeys: [],
          driverId: '',
          vehicleId: '',
          editingKey: '',
          editing: {},
          message: '订单已派给司机和车辆，司机端将显示待确认任务。'
        });
        this.loadAll();
      })
      .catch(() => {
        this.setData({ loading: false, conflictText: '派车失败，请检查冲突或后端连接。' });
      });
  },

  reassignSelected() {
    if (!this.data.canAssign) {
      wx.showToast({ title: '请选择订单、司机和车辆', icon: 'none' });
      return;
    }
    wx.showModal({
      title: '重新分配订单',
      content: '确认将已选订单重新分配给当前司机和车辆？',
      confirmText: '重新分配',
      success: (res) => {
        if (res.confirm) this.assignSelected();
      }
    });
  },

  getSelectedWindows() {
    return this.selectedRows().map((row) => this.toWindow(row)).filter(Boolean);
  },

  hasConflict(assignments, key, resourceId, selectedWindows) {
    if (!selectedWindows.length) return false;
    return assignments
      .filter((item) => Number(item[key]) === Number(resourceId))
      .some((item) => {
        const activeWindow = this.toWindow(item);
        return activeWindow && selectedWindows.some((selected) => selected.start < activeWindow.end && activeWindow.start < selected.end);
      });
  },

  toWindow(item) {
    const start = this.toTimeValue(item.order_date, item.start_time);
    let end = this.toTimeValue(item.end_date || item.order_date, item.end_time);
    if (!start || !end) return null;
    if (end <= start) end += 24 * 60 * 60 * 1000;
    return { start, end };
  },

  toTimeValue(dateText, timeText) {
    if (!dateText || !timeText || !String(timeText).includes(':')) return null;
    const date = String(dateText).split('-').map((part) => Number(part));
    const time = String(timeText).split(':').map((part) => Number(part));
    if (date.length < 3 || time.length < 2 || date.some(Number.isNaN) || time.some(Number.isNaN)) return null;
    return new Date(date[0], date[1] - 1, date[2], time[0], time[1], 0, 0).getTime();
  },

  formatConflicts(conflicts) {
    if (!conflicts.length) return '存在时间冲突，未派车。';
    return conflicts.map((item) => {
      if (item.type === 'driver_time_overlap') return `司机时间冲突：订单 ${item.order_id}`;
      if (item.type === 'vehicle_time_overlap') return `车辆时间冲突：订单 ${item.order_id}`;
      if (item.type === 'order_already_assigned') return `订单已派车：${item.order_id}`;
      return `${item.type || '冲突'}：${item.order_id || '-'}`;
    }).join('；');
  }
});
