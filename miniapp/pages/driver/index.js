const api = require('../../utils/api');

const STATUS_TEXT = {
  assigned: '待确认',
  confirmed: '已确认',
  departed: '已出库',
  arrived: '已到达',
  in_service: '服务中',
  completed: '已完成',
  returned: '已归库'
};

const TAB_ITEMS = [
  { key: 'home', label: '首页' },
  { key: 'task', label: '任务' },
  { key: 'map', label: '地图' },
  { key: 'expense', label: '费用' },
  { key: 'mine', label: '我的' }
];

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

const PHOTO_STEPS = [
  { key: 'arrive_waiting_photo', label: '到达上车点拍照', allowedStatuses: ['arrived', 'in_service', 'completed', 'returned'], lockedHint: '先到达上车点' },
  { key: 'pickup_photo', label: '接到客人拍照', allowedStatuses: ['arrived', 'in_service', 'completed', 'returned'], lockedHint: '先到达上车点' },
  { key: 'waypoint_photo', label: '中途地点拍照', allowedStatuses: ['in_service', 'completed', 'returned'], lockedHint: '先接到客人并开始行程' },
  { key: 'dropoff_photo', label: '送达目的地拍照', allowedStatuses: ['in_service', 'completed', 'returned'], lockedHint: '先开始行程' }
];

const ARRIVAL_RADIUS_METERS = 800;

Page({
  data: {
    tabItems: TAB_ITEMS,
    activeTab: 'home',
    driverId: 1,
    driverName: '司机',
    driverInitial: '司',
    today: '',
    nowText: '',
    statusMode: 'rest',
    statusText: '未出库',
    isOnline: true,
    loading: false,
    submitting: false,
    workbench: {},
    allAssignments: [],
    assignments: [],
    tomorrowAssignments: [],
    selectedDate: '',
    selectedDateAssignments: [],
    availableDates: [],
    calendarMonth: '',
    calendarTitle: '',
    calendarMode: 'week',
    calendarDays: [],
    calendarTouchStartY: 0,
    selected: null,
    nextActionLabel: '暂无任务',
    nextActionHint: '等待调度分配订单',
    pendingConfirmAssignments: [],
    dockVisible: true,
    dockDisabled: true,
    dockLabel: '暂无任务',
    preflightItems: PREFLIGHT_ITEMS,
    returnItems: RETURN_ITEMS,
    preflightChecked: {},
    returnChecked: {},
    photoSteps: PHOTO_STEPS,
    currentPhotoStep: null,
    photoCollapsedText: '只显示下一次应该上传的位置。',
    mapLatitude: 35.6812,
    mapLongitude: 139.7671,
    mapScale: 12,
    mapMarkers: [],
    navigationLabel: '打开微信导航',
    latitude: '',
    longitude: '',
    locationText: '',
    expenses: [],
    expensePanelOpen: false,
    expenseKind: 'advance',
    expenseAmount: '',
    expenseNote: '',
    driverProfile: {},
    incomeSummary: { today: {}, monthly: {} },
    notifications: [],
    history: []
  },

  onLoad(options) {
    const driverId = Number((options && options.driver_id) || wx.getStorageSync('driver_id') || 1);
    wx.setStorageSync('driver_id', driverId);
    this.setData({
      driverId,
      today: this.formatDate(new Date()),
      nowText: this.formatTime(new Date())
    });
    this.startClock();
    this.loadAll();
  },

  onShow() {
    this.loadAll({ silent: true });
  },

  onUnload() {
    if (this.clockTimer) clearInterval(this.clockTimer);
  },

  startClock() {
    if (this.clockTimer) clearInterval(this.clockTimer);
    this.clockTimer = setInterval(() => {
      this.setData({ nowText: this.formatTime(new Date()) });
    }, 30000);
  },

  loadAll(options = {}) {
    const silent = !!options.silent;
    this.setData({ loading: !silent });
    Promise.all([
      api.driverWorkbench(this.data.driverId),
      api.driverAssignments(this.data.driverId),
      api.driverExpenses(this.data.driverId),
      api.driverIncome(this.data.driverId),
      api.driverNotifications(this.data.driverId),
      api.listDrivers(),
      api.driverHistory(this.data.driverId, {})
    ]).then(([workbench, assignmentRes, expenseRes, incomeRes, notificationRes, driversRes, historyRes]) => {
      const assignments = this.normalizeAssignments((assignmentRes && assignmentRes.assignments) || []);
      const todayAssignments = assignments.filter((item) => this.isAssignmentOnDate(item, this.data.today));
      const tomorrowAssignments = assignments.filter((item) => item.order_date && this.getAssignmentStartDate(item) > this.data.today);
      const todayOpenAssignments = todayAssignments.filter((item) => (item.execution_status || 'assigned') !== 'returned');
      const displayList = todayOpenAssignments.length ? todayOpenAssignments : (tomorrowAssignments.length ? tomorrowAssignments : todayAssignments);
      const selectedDate = this.data.selectedDate || this.data.today;
      const selectedDateAssignments = this.filterAssignmentsByDate(assignments, selectedDate);
      const calendarMonth = this.data.calendarMonth || selectedDate.slice(0, 7);
      const selected = this.pickSelected(displayList);
      const pendingConfirmAssignments = todayAssignments.concat(tomorrowAssignments).filter((item) => (item.execution_status || 'assigned') === 'assigned');
      const driver = this.pickDriver((driversRes && driversRes.drivers) || [], selected, workbench || {});
      this.setData({
        loading: false,
        isOnline: true,
        workbench: workbench || {},
        allAssignments: assignments,
        assignments: todayAssignments,
        tomorrowAssignments,
        selectedDate,
        selectedDateAssignments,
        availableDates: this.buildAvailableDates(assignments),
        pendingConfirmAssignments,
        calendarMonth,
        calendarTitle: this.formatCalendarTitle(calendarMonth),
        calendarDays: this.buildCalendarDays(assignments, calendarMonth, selectedDate, this.data.calendarMode),
        selected,
        expenses: (expenseRes && expenseRes.expenses) || [],
        incomeSummary: incomeRes || { today: {}, monthly: {} },
        notifications: (notificationRes && notificationRes.notifications) || [],
        history: (historyRes && (historyRes.history || historyRes.items)) || [],
        driverProfile: driver,
        driverName: driver.name || (selected && selected.driver_name) || `司机${this.data.driverId}`,
        driverInitial: this.firstChar(driver.name || (selected && selected.driver_name) || '司')
      });
      this.refreshDerivedState();
    }).catch(() => {
      this.setData({
        loading: false,
        isOnline: false,
        nextActionLabel: '网络异常',
        nextActionHint: '请确认后端服务和手机网络'
      });
    });
  },

  normalizeAssignments(items) {
    const rows = items.map((item) => {
      const status = item.execution_status || 'assigned';
      return {
        ...item,
        status_label: STATUS_TEXT[status] || status,
        vehicle_display: this.formatVehicleDisplay(item),
        time_label: this.formatAssignmentTimeLabel(item),
        datetime_label: this.formatAssignmentDateTimeLabel(item),
        short_datetime_label: this.formatAssignmentShortDateTimeLabel(item)
      };
    }).sort((a, b) => String(a.start_time || '').localeCompare(String(b.start_time || '')));
    const grouped = {};
    rows.forEach((item) => {
      const dateKey = this.getAssignmentStartDate(item);
      if (!grouped[dateKey]) grouped[dateKey] = [];
      grouped[dateKey].push(item);
    });
    Object.keys(grouped).forEach((dateKey) => {
      const dayRows = grouped[dateKey].sort((a, b) => String(a.start_time || '').localeCompare(String(b.start_time || '')));
      dayRows.forEach((item, index) => {
        if (dayRows.length === 1) {
          item.day_flow_label = '出库 / 归库';
        } else if (index === 0) {
          item.day_flow_label = '出库';
        } else if (index === dayRows.length - 1) {
          item.day_flow_label = '归库';
        } else {
          item.day_flow_label = '任务';
        }
      });
    });
    return rows;
  },

  formatVehicleDisplay(item) {
    const value = String(item.vehicle_code || item.vehicle_short_code || item.plate_short || item.plate_number || item.vehicle_plate || '').trim();
    if (!value) return '';
    const digitGroups = value.match(/\d+/g);
    if (digitGroups && digitGroups.length) {
      const last = digitGroups[digitGroups.length - 1];
      return last.length > 4 ? last.slice(-4) : last;
    }
    return value;
  },

  filterAssignmentsByDate(items, targetDate) {
    return items.filter((item) => this.isAssignmentOnDate(item, targetDate));
  },

  buildAvailableDates(items) {
    const seen = {};
    items.forEach((item) => {
      this.expandAssignmentDates(item).forEach((dateText) => {
        seen[dateText] = true;
      });
    });
    const dates = Object.keys(seen);
    dates.sort();
    return dates.slice(0, 14);
  },

  buildCalendarDays(items, month, selectedDate, mode = 'week') {
    const [year, monthNumber] = month.split('-').map(Number);
    const first = new Date(year, monthNumber - 1, 1);
    const startWeekday = first.getDay();
    const daysInMonth = new Date(year, monthNumber, 0).getDate();
    const counts = {};
    items.forEach((item) => {
      this.expandAssignmentDates(item).forEach((dateKey) => {
        counts[dateKey] = (counts[dateKey] || 0) + 1;
      });
    });
    const cells = [];
    for (let i = 0; i < startWeekday; i += 1) {
      cells.push({ key: `blank-${i}`, blank: true });
    }
    for (let day = 1; day <= daysInMonth; day += 1) {
      const dateKey = `${year}-${String(monthNumber).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      const weekday = new Date(year, monthNumber - 1, day).getDay();
      const holidayName = this.getJapanHolidayName(dateKey);
      cells.push({
        key: dateKey,
        date: dateKey,
        day,
        count: counts[dateKey] || 0,
        active: dateKey === selectedDate,
        today: dateKey === this.data.today,
        holiday: !!holidayName || weekday === 0,
        holidayName
      });
    }
    while (cells.length % 7 !== 0) {
      cells.push({ key: `blank-tail-${cells.length}`, blank: true });
    }
    if (mode === 'week') {
      const selectedIndex = cells.findIndex((cell) => cell.date === selectedDate);
      const index = selectedIndex >= 0 ? selectedIndex : cells.findIndex((cell) => cell.date === this.data.today);
      const weekStart = Math.max(0, Math.floor(Math.max(index, 0) / 7) * 7);
      return cells.slice(weekStart, weekStart + 7);
    }
    return cells;
  },

  getAssignmentStartDate(item) {
    return (item && item.order_date) || this.data.today;
  },

  formatAssignmentTimeLabel(item) {
    const start = item.start_time || '--:--';
    const end = item.end_time || '--:--';
    const startDate = this.getAssignmentStartDate(item);
    const endDate = this.getAssignmentEndDate(item);
    return endDate > startDate ? `${start} - 次日 ${end}` : `${start} - ${end}`;
  },

  formatAssignmentDateTimeLabel(item) {
    const start = item.start_time || '--:--';
    const end = item.end_time || '--:--';
    const startDate = this.getAssignmentStartDate(item);
    const endDate = this.getAssignmentEndDate(item);
    return endDate > startDate ? `${startDate} ${start} - ${endDate} ${end}` : `${startDate} ${start} - ${end}`;
  },

  formatAssignmentShortDateTimeLabel(item) {
    const start = item.start_time || '--:--';
    const end = item.end_time || '--:--';
    const startDate = this.getAssignmentStartDate(item);
    const endDate = this.getAssignmentEndDate(item);
    const startShort = startDate.slice(5);
    const endShort = endDate.slice(5);
    return endDate > startDate ? `${startShort} ${start} - ${endShort} ${end}` : `${startShort} ${start} - ${end}`;
  },

  getAssignmentEndDate(item) {
    if (!item) return this.data.today;
    if (item.end_date) return item.end_date;
    const startDate = this.getAssignmentStartDate(item);
    const startTime = item.start_time || '';
    const endTime = item.end_time || '';
    if (startTime && endTime && endTime < startTime) {
      return this.addDays(startDate, 1);
    }
    return startDate;
  },

  isAssignmentOnDate(item, targetDate) {
    if (!targetDate) return false;
    const startDate = this.getAssignmentStartDate(item);
    const endDate = this.getAssignmentEndDate(item);
    return startDate <= targetDate && targetDate <= endDate;
  },

  expandAssignmentDates(item) {
    const startDate = this.getAssignmentStartDate(item);
    const endDate = this.getAssignmentEndDate(item);
    const dates = [];
    let current = startDate;
    for (let guard = 0; guard < 8 && current <= endDate; guard += 1) {
      dates.push(current);
      current = this.addDays(current, 1);
    }
    return dates;
  },

  addDays(dateText, days) {
    const parts = String(dateText || '').split('-').map(Number);
    if (parts.length !== 3 || parts.some((part) => Number.isNaN(part))) return dateText;
    const dt = new Date(parts[0], parts[1] - 1, parts[2] + days);
    const year = dt.getFullYear();
    const month = String(dt.getMonth() + 1).padStart(2, '0');
    const day = String(dt.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  },

  formatCalendarTitle(month) {
    const [year, monthNumber] = month.split('-');
    return `${year}年${Number(monthNumber)}月`;
  },

  getJapanHolidayName(dateKey) {
    const fixed = {
      '2026-01-01': '元日',
      '2026-01-12': '成人の日',
      '2026-02-11': '建国記念の日',
      '2026-02-23': '天皇誕生日',
      '2026-03-20': '春分の日',
      '2026-04-29': '昭和の日',
      '2026-05-03': '憲法記念日',
      '2026-05-04': 'みどりの日',
      '2026-05-05': 'こどもの日',
      '2026-05-06': '振替休日',
      '2026-07-20': '海の日',
      '2026-08-11': '山の日',
      '2026-09-21': '敬老の日',
      '2026-09-22': '国民の休日',
      '2026-09-23': '秋分の日',
      '2026-10-12': 'スポーツの日',
      '2026-11-03': '文化の日',
      '2026-11-23': '勤労感謝の日'
    };
    return fixed[dateKey] || '';
  },

  pickSelected(items) {
    if (!items.length) return null;
    const active = items.find((item) => ['confirmed', 'departed', 'arrived', 'in_service'].includes(item.execution_status || ''));
    const assigned = items.find((item) => (item.execution_status || 'assigned') === 'assigned');
    const completed = items.find((item) => (item.execution_status || '') === 'completed');
    return active || assigned || completed || items[0];
  },

  pickDriver(drivers, selected, workbench) {
    const found = drivers.find((item) => Number(item.id) === Number(this.data.driverId));
    if (found) return found;
    return {
      name: workbench.driver_name || (selected && selected.driver_name) || `司机${this.data.driverId}`,
      phone: '',
      driver_code: ''
    };
  },

  refreshDerivedState() {
    const selected = this.data.selected;
    const action = this.computeNextAction(selected);
    const dock = this.computeDockState(selected, action, this.data.activeTab);
    const photoSteps = this.buildPhotoSteps(selected);
    this.setData({
      nextActionLabel: action.label,
      nextActionHint: action.hint,
      dockVisible: dock.visible,
      dockDisabled: dock.disabled,
      dockLabel: dock.label,
      photoSteps,
      currentPhotoStep: this.pickCurrentPhotoStep(selected, photoSteps),
      photoCollapsedText: this.buildPhotoCollapsedText(photoSteps),
      navigationLabel: this.computeNavigationLabel(selected)
    });
    this.updateStatus(selected);
    this.updateMap(selected);
  },

  buildPhotoSteps(selected) {
    const status = selected ? (selected.execution_status || 'assigned') : 'assigned';
    return PHOTO_STEPS.map((step) => {
      const disabled = !selected || !step.allowedStatuses.includes(status);
      return {
        ...step,
        disabled,
        hint: disabled ? step.lockedHint : '可以上传'
      };
    });
  },

  pickCurrentPhotoStep(selected, steps) {
    const status = selected ? (selected.execution_status || 'assigned') : 'assigned';
    const pickup = selected ? (selected.pickup_location || '上车点') : '上车点';
    const dropoff = selected ? (selected.dropoff_location || '终点') : '终点';
    const stepByStatus = {
      assigned: { key: 'arrive_waiting_photo', label: '到达上车点后拍照', disabled: true, hint: '请先确认接单并出库', location: pickup },
      confirmed: { key: 'arrive_waiting_photo', label: '到达上车点后拍照', disabled: true, hint: '请先点呼出库', location: pickup },
      departed: { key: 'arrive_waiting_photo', label: '到达上车点后拍照', disabled: true, hint: '到达上车点后开放', location: pickup },
      arrived: { key: 'arrive_waiting_photo', label: '到达上车点照片', disabled: false, hint: '可以上传', location: pickup },
      in_service: { key: 'waypoint_photo', label: '行程中地点照片', disabled: false, hint: '可以上传', location: `${pickup} → ${dropoff}` },
      completed: { key: 'dropoff_photo', label: '送达目的地照片', disabled: false, hint: '可以上传', location: dropoff },
      returned: { key: 'dropoff_photo', label: '今日照片节点已结束', disabled: true, hint: '车辆已入库', location: dropoff }
    };
    const current = stepByStatus[status] || null;
    if (!current) return (steps || []).find((item) => !item.disabled) || null;
    return current;
  },

  buildPhotoCollapsedText(steps) {
    const disabledCount = (steps || []).filter((item) => item.disabled).length;
    const enabledCount = (steps || []).filter((item) => !item.disabled).length;
    if (enabledCount > 0) return `其他 ${disabledCount} 个照片节点已折叠，只处理当前节点。`;
    return '还没到下一次拍照节点，其他节点已折叠。';
  },

  computeNavigationLabel(selected) {
    if (!selected) return '暂无导航';
    const status = selected.execution_status || 'assigned';
    if (['in_service', 'completed', 'returned'].includes(status)) return '导航到终点';
    return '导航到上车点';
  },

  computeDockState(selected, action, activeTab) {
    if (activeTab === 'expense' || activeTab === 'mine' || activeTab === 'task') {
      return { visible: false, disabled: true, label: action.label };
    }
    if (!selected) {
      return { visible: true, disabled: true, label: '本人没有订单了' };
    }
    const status = selected.execution_status || 'assigned';
    if (activeTab === 'home') {
      if (this.data.pendingConfirmAssignments.length > 0) {
        return { visible: true, disabled: false, label: `确认全部接单（${this.data.pendingConfirmAssignments.length}单）` };
      }
      if (status === 'assigned') return { visible: true, disabled: false, label: '确认接单' };
      if (status === 'confirmed') return { visible: true, disabled: false, label: '点呼出库' };
      if (['departed', 'arrived', 'in_service'].includes(status)) return { visible: true, disabled: false, label: '去地图执行任务' };
      if (status === 'completed' && this.findNextRunnable(selected)) {
        return { visible: true, disabled: false, label: '开启下一单' };
      }
      if (status === 'completed' && !this.findNextRunnable(selected)) {
        return { visible: true, disabled: false, label: '点呼入库' };
      }
      return { visible: true, disabled: true, label: action.label };
    }
    if (activeTab === 'map') {
      if (status === 'assigned') return { visible: true, disabled: true, label: '请先在首页确认接单' };
      if (status === 'confirmed') return { visible: true, disabled: true, label: '请先回首页点呼出库' };
      if (status === 'completed' && !this.findNextRunnable(selected)) return { visible: true, disabled: true, label: '请回首页点呼入库' };
      return { visible: true, disabled: !action.reportType && action.type !== 'select_next', label: action.label };
    }
    return { visible: true, disabled: !selected || (!action.reportType && action.type !== 'select_next'), label: action.label };
  },

  computeNextAction(selected) {
    if (!selected) {
      return { type: 'idle', label: '本人没有订单了', hint: '当前选择日期没有调度分配的订单' };
    }
    const status = selected.execution_status || 'assigned';
    if (status === 'assigned') return { type: 'report', reportType: 'confirm_order', label: '确认接单', hint: '确认收到调度分配的订单' };
    if (status === 'confirmed') return { type: 'depart', reportType: 'depart_yard', label: '点呼出库', hint: '完成车辆检查、证件确认和酒精测试后出库' };
    if (status === 'departed') return { type: 'report', reportType: 'arrive_pickup', label: '到达上车点', hint: '到达客人指定地点后点击' };
    if (status === 'arrived') return { type: 'report', reportType: 'start_service', label: '接到客人', hint: '接到客人并开始行程' };
    if (status === 'in_service') return { type: 'report', reportType: 'complete_order', label: '完成订单', hint: '送达目的地后点击完成' };
    if (status === 'completed') {
      const next = this.findNextRunnable(selected);
      if (next) return { type: 'select_next', label: '开启下一单', hint: `${next.start_time || '--:--'} ${next.pickup_location || ''} → ${next.dropoff_location || ''}` };
      return { type: 'return', reportType: 'return_yard', label: '准备入库', hint: '今天全部订单已完成，没有临时新增订单，请回库做清扫、入库点检、酒精测试和点呼入库' };
    }
    if (status === 'returned') return { type: 'idle', label: '今日收工', hint: '车辆已入库，今日任务已完成' };
    return { type: 'idle', label: '今日收工', hint: '今日任务已完成' };
  },

  findNextRunnable(current) {
    const currentId = current ? Number(current.assignment_id) : 0;
    const runnable = this.data.assignments.filter((item) => {
      const status = item.execution_status || 'assigned';
      if (Number(item.assignment_id) === currentId) return false;
      return !['completed', 'returned'].includes(status);
    });
    return runnable[0] || null;
  },

  updateStatus(selected) {
    const todayRows = this.data.assignments || [];
    if (!selected && !todayRows.length) {
      this.setData({ statusMode: 'rest', statusText: '休息' });
      return;
    }

    const statuses = todayRows.map((item) => item.execution_status || 'assigned');
    if (statuses.some((status) => ['departed', 'arrived', 'in_service'].includes(status))) {
      const inService = statuses.includes('in_service');
      this.setData({ statusMode: 'departed', statusText: inService ? '执行中' : '已出库' });
      return;
    }
    if (statuses.some((status) => status === 'completed')) {
      this.setData({ statusMode: 'departed', statusText: '已出库' });
      return;
    }
    if (statuses.length && statuses.every((status) => status === 'returned')) {
      this.setData({ statusMode: 'ready', statusText: '未出库' });
      return;
    }

    const status = selected ? (selected.execution_status || 'assigned') : 'assigned';
    if (['departed', 'arrived', 'in_service'].includes(status)) {
      this.setData({ statusMode: 'departed', statusText: status === 'in_service' ? '执行中' : '已出库' });
    } else if (status === 'completed') {
      this.setData({ statusMode: 'departed', statusText: '已出库' });
    } else if (status === 'returned') {
      this.setData({ statusMode: 'ready', statusText: '未出库' });
    } else {
      this.setData({ statusMode: 'ready', statusText: '未出库' });
    }
  },

  updateMap(selected) {
    const markers = [];
    const driverLat = Number(this.data.latitude);
    const driverLng = Number(this.data.longitude);
    if (driverLat && driverLng) {
      markers.push({ id: 1, latitude: driverLat, longitude: driverLng, title: '当前位置' });
    }
    const pickup = this.getPoint(selected, 'pickup');
    if (pickup) markers.push({ id: 2, latitude: pickup.latitude, longitude: pickup.longitude, title: '上车点' });
    const dropoff = this.getPoint(selected, 'dropoff');
    if (dropoff) markers.push({ id: 3, latitude: dropoff.latitude, longitude: dropoff.longitude, title: '终点' });
    this.setData({
      mapMarkers: markers,
      mapLatitude: driverLat || (pickup && pickup.latitude) || 35.6812,
      mapLongitude: driverLng || (pickup && pickup.longitude) || 139.7671
    });
  },

  getPoint(order, type) {
    if (!order) return null;
    const lat = Number(type === 'dropoff' ? order.dropoff_latitude : order.pickup_latitude);
    const lng = Number(type === 'dropoff' ? order.dropoff_longitude : order.pickup_longitude);
    return lat && lng ? { latitude: lat, longitude: lng } : null;
  },

  onTabChange(e) {
    this.setData({ activeTab: e.currentTarget.dataset.tab });
    this.refreshDerivedState();
  },

  onSelectOrder(e) {
    const id = Number(e.currentTarget.dataset.id);
    const all = this.data.allAssignments.length ? this.data.allAssignments : this.data.assignments.concat(this.data.tomorrowAssignments);
    const selected = all.find((item) => Number(item.assignment_id) === id);
    if (!selected) return;
    this.setData({ selected, selectedDate: selected.order_date || this.data.today, selectedDateAssignments: this.filterAssignmentsByDate(all, selected.order_date || this.data.today) });
    this.refreshDerivedState();
  },

  onCalendarDateChange(e) {
    const selectedDate = e.detail.value;
    const calendarMonth = selectedDate.slice(0, 7);
    const selectedDateAssignments = this.filterAssignmentsByDate(this.data.allAssignments, selectedDate);
    const selected = this.pickSelected(selectedDateAssignments);
    this.setData({
      selectedDate,
      selectedDateAssignments,
      selected,
      calendarMonth,
      calendarTitle: this.formatCalendarTitle(calendarMonth),
      calendarDays: this.buildCalendarDays(this.data.allAssignments, calendarMonth, selectedDate, this.data.calendarMode)
    });
    this.refreshDerivedState();
  },

  onQuickDateTap(e) {
    const selectedDate = e.currentTarget.dataset.date;
    const calendarMonth = selectedDate.slice(0, 7);
    const selectedDateAssignments = this.filterAssignmentsByDate(this.data.allAssignments, selectedDate);
    const selected = this.pickSelected(selectedDateAssignments);
    this.setData({
      selectedDate,
      selectedDateAssignments,
      selected,
      activeTab: 'task',
      calendarMonth,
      calendarTitle: this.formatCalendarTitle(calendarMonth),
      calendarDays: this.buildCalendarDays(this.data.allAssignments, calendarMonth, selectedDate, this.data.calendarMode)
    });
    this.refreshDerivedState();
  },

  onCalendarDayTap(e) {
    const selectedDate = e.currentTarget.dataset.date;
    if (!selectedDate) return;
    const selectedDateAssignments = this.filterAssignmentsByDate(this.data.allAssignments, selectedDate);
    const selected = this.pickSelected(selectedDateAssignments);
    this.setData({
      selectedDate,
      selectedDateAssignments,
      selected,
      calendarDays: this.buildCalendarDays(this.data.allAssignments, this.data.calendarMonth, selectedDate, this.data.calendarMode)
    });
    this.refreshDerivedState();
  },

  onCalendarMonthChange(e) {
    const direction = Number(e.currentTarget.dataset.direction || 0);
    const [year, monthNumber] = this.data.calendarMonth.split('-').map(Number);
    const target = new Date(year, monthNumber - 1 + direction, 1);
    const calendarMonth = `${target.getFullYear()}-${String(target.getMonth() + 1).padStart(2, '0')}`;
    this.setData({
      calendarMonth,
      calendarTitle: this.formatCalendarTitle(calendarMonth),
      calendarDays: this.buildCalendarDays(this.data.allAssignments, calendarMonth, this.data.selectedDate, this.data.calendarMode)
    });
  },

  onCalendarTouchStart(e) {
    const touch = e.touches && e.touches[0];
    if (!touch) return;
    this.setData({ calendarTouchStartY: touch.clientY });
  },

  onCalendarTouchEnd(e) {
    const touch = e.changedTouches && e.changedTouches[0];
    if (!touch) return;
    const deltaY = touch.clientY - this.data.calendarTouchStartY;
    if (Math.abs(deltaY) < 28) return;
    const calendarMode = deltaY > 0 ? 'month' : 'week';
    this.setData({
      calendarMode,
      calendarDays: this.buildCalendarDays(this.data.allAssignments, this.data.calendarMonth, this.data.selectedDate, calendarMode)
    });
  },

  onToggleCalendarMode() {
    const calendarMode = this.data.calendarMode === 'week' ? 'month' : 'week';
    this.setData({
      calendarMode,
      calendarDays: this.buildCalendarDays(this.data.allAssignments, this.data.calendarMonth, this.data.selectedDate, calendarMode)
    });
  },

  onPrimaryAction() {
    const action = this.computeNextAction(this.data.selected);
    if (!this.data.selected || this.data.submitting) return;
    const status = this.data.selected.execution_status || 'assigned';
    if (this.data.activeTab === 'home' && this.data.pendingConfirmAssignments.length > 0) {
      this.confirmAllPendingAssignments();
      return;
    }
    if (this.data.activeTab === 'home' && ['departed', 'arrived', 'in_service'].includes(status)) {
      this.setData({ activeTab: 'map' });
      this.refreshDerivedState();
      return;
    }
    if (this.data.activeTab === 'map' && ['assigned', 'confirmed'].includes(status)) {
      wx.showToast({ title: status === 'assigned' ? '请先在首页确认接单' : '请先回首页点呼出库', icon: 'none' });
      return;
    }
    if (this.data.activeTab === 'map' && action.type === 'return') {
      wx.showToast({ title: '请回首页完成入库', icon: 'none' });
      return;
    }
    if (action.type === 'select_next') {
      const next = this.findNextRunnable(this.data.selected);
      if (next) {
        this.setData({ selected: next, activeTab: 'map' });
        this.refreshDerivedState();
      }
      return;
    }
    if (!action.reportType) return;
    if (action.type === 'depart' && !this.allChecked(this.data.preflightItems, this.data.preflightChecked)) {
      this.setData({ activeTab: 'home' });
      wx.showToast({ title: '请先完成出库检查', icon: 'none' });
      return;
    }
    if (action.type === 'return' && !this.allChecked(this.data.returnItems, this.data.returnChecked)) {
      this.setData({ activeTab: 'home' });
      wx.showToast({ title: '请先完成入库检查', icon: 'none' });
      return;
    }
    this.submitReport(action.reportType);
  },

  confirmAllPendingAssignments() {
    const pending = this.data.pendingConfirmAssignments || [];
    if (!pending.length || this.data.submitting) return;
    this.setData({ submitting: true });
    const tasks = pending.map((item) => api.submitDriverReport({
      driver_id: this.data.driverId,
      assignment_id: item.assignment_id,
      report_type: 'confirm_order',
      latitude: this.data.latitude,
      longitude: this.data.longitude,
      location_text: this.data.locationText || '司机端确认接单'
    }));
    Promise.all(tasks).then((results) => {
      const failed = results.filter((res) => !res || res.success === false);
      this.setData({ submitting: false, activeTab: failed.length ? 'home' : 'task' });
      if (failed.length) {
        wx.showToast({ title: `${failed.length}单确认失败`, icon: 'none' });
      } else {
        wx.showToast({ title: '已全部接单', icon: 'success' });
      }
      this.loadAll({ silent: true });
    }).catch(() => {
      this.setData({ submitting: false });
      wx.showToast({ title: '网络异常', icon: 'none' });
    });
  },

  submitReport(reportType) {
    const selected = this.data.selected;
    if (!selected) return;
    this.setData({ submitting: true });
    this.resolveReportLocation(reportType, (locationResult) => {
      if (!locationResult.ok) {
        this.setData({ submitting: false });
        wx.showToast({ title: locationResult.message || '定位校验失败', icon: 'none' });
        return;
      }
      const payload = {
        driver_id: this.data.driverId,
        assignment_id: selected.assignment_id,
        report_type: reportType,
        latitude: locationResult.latitude || this.data.latitude,
        longitude: locationResult.longitude || this.data.longitude,
        location_text: locationResult.locationText || this.data.locationText || '司机端上报'
      };
      api.submitDriverReport(payload).then((res) => {
        this.setData({ submitting: false });
        if (!res || res.success === false) {
          wx.showToast({ title: this.reportErrorMessage(res), icon: 'none' });
          return;
        }
        wx.showToast({ title: '已提交', icon: 'success' });
        this.loadAll({ silent: true });
      }).catch(() => {
        this.setData({ submitting: false });
        wx.showToast({ title: '网络异常', icon: 'none' });
      });
    });
  },

  resolveReportLocation(reportType, done) {
    const targetType = reportType === 'arrive_pickup' ? 'pickup' : (reportType === 'complete_order' ? 'dropoff' : '');
    if (!targetType) {
      done({ ok: true });
      return;
    }
    const targetPoint = this.getPoint(this.data.selected, targetType);
    wx.getLocation({
      type: 'gcj02',
      success: (loc) => {
        this.setData({
          latitude: loc.latitude,
          longitude: loc.longitude,
          locationText: '微信定位',
          mapLatitude: loc.latitude,
          mapLongitude: loc.longitude
        });
        this.updateMap(this.data.selected);
        if (targetPoint) {
          const distance = this.distanceMeters(loc.latitude, loc.longitude, targetPoint.latitude, targetPoint.longitude);
          if (distance > ARRIVAL_RADIUS_METERS) {
            const label = targetType === 'pickup' ? '上车点' : '终点';
            done({ ok: false, message: `距离${label}约${Math.round(distance)}米，靠近后再确认` });
            return;
          }
        }
        done({ ok: true, latitude: loc.latitude, longitude: loc.longitude, locationText: '微信定位' });
      },
      fail: () => {
        if (targetPoint) {
          done({ ok: false, message: '无法获取定位，不能确认到达' });
          return;
        }
        done({ ok: true });
      }
    });
  },

  reportErrorMessage(res) {
    if (res && res.error === 'location_out_of_range') {
      const check = res.location_check || {};
      if (check.reason === 'driver_coordinate_missing') return '无法获取定位，不能确认到达';
      if (check.distance_meters) return `距离${check.target_label || '目标地点'}约${check.distance_meters}米，靠近后再确认`;
      return '位置不在目标地点附近';
    }
    return '提交失败';
  },

  distanceMeters(lat1, lng1, lat2, lng2) {
    const radius = 6371000;
    const toRad = (value) => value * Math.PI / 180;
    const phi1 = toRad(Number(lat1));
    const phi2 = toRad(Number(lat2));
    const deltaPhi = toRad(Number(lat2) - Number(lat1));
    const deltaLambda = toRad(Number(lng2) - Number(lng1));
    const a = Math.sin(deltaPhi / 2) * Math.sin(deltaPhi / 2) +
      Math.cos(phi1) * Math.cos(phi2) * Math.sin(deltaLambda / 2) * Math.sin(deltaLambda / 2);
    return radius * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  },

  onTogglePreflight(e) {
    const key = e.currentTarget.dataset.key;
    this.setData({ preflightChecked: { ...this.data.preflightChecked, [key]: !this.data.preflightChecked[key] } });
  },

  onToggleReturn(e) {
    const key = e.currentTarget.dataset.key;
    this.setData({ returnChecked: { ...this.data.returnChecked, [key]: !this.data.returnChecked[key] } });
  },

  allChecked(items, values) {
    return items.every((item) => values[item.key]);
  },

  onUploadLocation() {
    wx.getLocation({
      type: 'gcj02',
      success: (loc) => {
        this.setData({
          latitude: loc.latitude,
          longitude: loc.longitude,
          locationText: '微信定位',
          mapLatitude: loc.latitude,
          mapLongitude: loc.longitude
        });
        this.updateMap(this.data.selected);
        api.submitDriverLocation({
          driver_id: this.data.driverId,
          assignment_id: this.data.selected ? this.data.selected.assignment_id : '',
          latitude: loc.latitude,
          longitude: loc.longitude,
          location_text: '微信定位',
          source: 'miniapp'
        }).catch(() => undefined);
        wx.showToast({ title: '位置已上报', icon: 'success' });
      },
      fail: () => wx.showToast({ title: '定位失败', icon: 'none' })
    });
  },

  onNavigatePickup() {
    this.openNavigation('pickup');
  },

  onNavigateDropoff() {
    this.openNavigation('dropoff');
  },

  onOpenPrimaryNavigation() {
    const selected = this.data.selected;
    if (!selected) {
      wx.showToast({ title: '暂无订单', icon: 'none' });
      return;
    }
    const status = selected.execution_status || 'assigned';
    const targetType = ['in_service', 'completed', 'returned'].includes(status) ? 'dropoff' : 'pickup';
    this.openNavigation(targetType);
  },

  onOpenGoogleMap() {
    const selected = this.data.selected;
    if (!selected) {
      wx.showToast({ title: '暂无订单', icon: 'none' });
      return;
    }
    const pickup = selected.pickup_location || '';
    const dropoff = selected.dropoff_location || '';
    const pickupPoint = this.getPoint(selected, 'pickup');
    const dropoffPoint = this.getPoint(selected, 'dropoff');
    const params = [
      ['pickup', pickup],
      ['dropoff', dropoff],
      ['pickup_latitude', pickupPoint ? pickupPoint.latitude : ''],
      ['pickup_longitude', pickupPoint ? pickupPoint.longitude : ''],
      ['dropoff_latitude', dropoffPoint ? dropoffPoint.latitude : ''],
      ['dropoff_longitude', dropoffPoint ? dropoffPoint.longitude : '']
    ].map(([key, value]) => `${key}=${encodeURIComponent(value || '')}`).join('&');
    const url = `${api.getBaseUrl()}/driver-google-map?${params}`;
    wx.navigateTo({
      url: `/pages/driver/google_map/index?url=${encodeURIComponent(url)}`
    });
  },

  openNavigation(type) {
    const selected = this.data.selected;
    const address = selected ? (type === 'dropoff' ? selected.dropoff_location : selected.pickup_location) : '';
    const point = this.getPoint(selected, type);
    if (point) {
      wx.openLocation({
        latitude: point.latitude,
        longitude: point.longitude,
        scale: 16,
        name: type === 'dropoff' ? '终点' : '上车点',
        address
      });
      return;
    }
    const url = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address || '')}`;
    wx.showModal({
      title: '暂无坐标',
      content: `请使用文字地址导航：${address || '-'}\n可复制 Google Maps 搜索链接后到浏览器打开。`,
      confirmText: '复制链接',
      success: (res) => {
        if (res.confirm) wx.setClipboardData({ data: url || address });
      }
    });
  },

  onPhotoTap(e) {
    const type = e.currentTarget.dataset.type;
    const step = (this.data.photoSteps || []).find((item) => item.key === type);
    if (step && step.disabled) {
      wx.showToast({ title: step.lockedHint || '请按流程操作', icon: 'none' });
      return;
    }
    wx.showToast({ title: `${type || '照片'}入口已打开`, icon: 'none' });
  },

  openExpensePanel(e) {
    this.setData({
      expensePanelOpen: true,
      expenseKind: e.currentTarget.dataset.kind || 'advance'
    });
  },

  closeExpensePanel() {
    this.setData({ expensePanelOpen: false });
  },

  onInput(e) {
    this.setData({ [e.currentTarget.dataset.key]: e.detail.value });
  },

  onSubmitExpense() {
    const selected = this.data.selected;
    const amount = Number(this.data.expenseAmount || 0);
    if (!selected || !amount) {
      wx.showToast({ title: '请选择订单并填写金额', icon: 'none' });
      return;
    }
    api.submitDriverExpense({
      driver_id: this.data.driverId,
      assignment_id: selected.assignment_id,
      order_id: selected.order_id,
      expense_kind: this.data.expenseKind,
      category: this.data.expenseKind === 'collect' ? '代收' : '垫付',
      amount,
      note: this.data.expenseNote,
      submit_status: this.data.expenseKind === 'collect' ? 'in_hand' : 'submitted'
    }).then((res) => {
      if (!res || res.success === false) {
        wx.showToast({ title: '提交失败', icon: 'none' });
        return;
      }
      wx.showToast({ title: '费用已提交', icon: 'success' });
      this.setData({ expensePanelOpen: false, expenseAmount: '', expenseNote: '' });
      this.loadAll({ silent: true });
    }).catch(() => wx.showToast({ title: '网络异常', icon: 'none' }));
  },

  onSwitchDriver() {
    wx.setStorageSync('driver_id', this.data.driverId);
    this.loadAll();
  },

  firstChar(value) {
    return String(value || '司').slice(0, 1);
  },

  formatDate(date) {
    return date.toISOString().slice(0, 10);
  },

  formatTime(date) {
    return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
  }
});
