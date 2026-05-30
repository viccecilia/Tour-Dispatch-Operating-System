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

Page({
  data: {
    session: null,
    driverId: 0,
    allAssignments: [],
    assignments: [],
    departAssignment: null,
    returnAssignment: null,
    today: '',
    selectedDate: '',
    selectedLabel: '',
    weekDays: [],
    monthDays: [],
    showMonth: false,
    vehicleStatusText: '未出库',
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
    message: '',
    loading: false,
    submitting: false
  },

  onShow() {
    api.setActiveTab('/pages/task/index');
    const session = api.getSession();
    const role = api.getRole(session);
    if (!session || role !== 'driver') {
      wx.reLaunch({ url: '/pages/index/index' });
      return;
    }
    this.refreshTabBar();
    const today = this.today();
    const driverId = Number(session.user && session.user.profile_id || 0);
    this.setData({
      session,
      driverId,
      today,
      selectedDate: today,
      selectedLabel: this.formatDayLabel(today),
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
      this.setData({ message: '司机资料未绑定。', assignments: [] });
      return;
    }
    this.setData({ loading: true, message: '' });
    Promise.all([
      api.driverAssignments(this.data.driverId),
      api.driverWorkbench(this.data.driverId).catch(() => ({}))
    ])
      .then(([res, workbench]) => {
        const allRows = (res.assignments || []).map((item) => this.decorateAssignment(item));
        const todayRows = allRows.filter((item) => this.isOnDate(item, this.data.today));
        const departed = todayRows.some((item) => ACTIVE_STATUSES.indexOf(item.rawStatus) >= 0)
          || String((workbench || {}).vehicle_status || '').indexOf('已出库') >= 0;
        const returned = todayRows.some((item) => item.rawStatus === 'returned')
          || String((workbench || {}).vehicle_status || '').indexOf('已入库') >= 0;
        const vehicleStatusText = returned ? '已入库' : (departed ? '已出库' : '未出库');
        this.setData({
          allAssignments: allRows,
          weekDays: this.buildWeekDays(allRows, this.data.today),
          monthDays: this.buildMonthDays(allRows, this.data.today),
          vehicleStatusText,
          departAssignment: !departed && !returned ? this.pickDepartAssignment(todayRows) : null,
          returnAssignment: !returned ? this.pickReturnAssignment(todayRows) : null,
          loading: false
        });
        this.applySelectedDate();
      })
      .catch(() => this.setData({ loading: false, message: '无法加载司机任务。' }));
  },

  decorateAssignment(item) {
    const status = item.execution_status || item.status || 'assigned';
    return {
      ...item,
      rawStatus: status,
      routeText: `${item.pickup_location || '-'} -> ${item.dropoff_location || '-'}`,
      timeText: `${item.order_date || '-'} ${item.start_time || '--:--'}`,
      orderStatusText: this.orderStatusText(status),
      orderStatusClass: this.orderStatusClass(status),
      canConfirm: status === 'assigned',
      isExpanded: ACTIVE_STATUSES.indexOf(status) >= 0
    };
  },

  applySelectedDate() {
    const selectedDate = this.data.selectedDate || this.data.today;
    const rows = this.data.allAssignments
      .filter((item) => this.isOnDate(item, selectedDate))
      .sort((a, b) => String(a.start_time || '').localeCompare(String(b.start_time || '')))
      .map((item, index) => ({
        ...item,
        isExpanded: ACTIVE_STATUSES.indexOf(item.rawStatus) >= 0 || (index === 0 && ACTIVE_STATUSES.indexOf(item.rawStatus) >= 0)
      }));
    this.setData({
      assignments: rows,
      selectedLabel: this.formatDayLabel(selectedDate)
    });
  },

  onSelectDate(e) {
    const date = e.currentTarget.dataset.date;
    this.setData({
      selectedDate: date,
      weekDays: this.markSelected(this.data.weekDays, date),
      monthDays: this.markSelected(this.data.monthDays, date)
    });
    this.applySelectedDate();
  },

  toggleMonth() {
    this.setData({ showMonth: !this.data.showMonth });
  },

  toggleTask(e) {
    const assignmentId = Number(e.currentTarget.dataset.id || 0);
    const rows = this.data.assignments.map((item) => {
      if (Number(item.assignment_id || item.id) !== assignmentId) return item;
      return { ...item, isExpanded: !item.isExpanded };
    });
    this.setData({ assignments: rows });
  },

  pickDepartAssignment(rows) {
    if (rows.some((item) => item.rawStatus === 'assigned')) return null;
    return rows.find((item) => item.rawStatus === 'confirmed') || null;
  },

  pickReturnAssignment(rows) {
    const hasOpen = rows.some((item) => OPEN_STATUSES.indexOf(item.rawStatus) >= 0);
    if (hasOpen) return null;
    const completed = rows.filter((item) => item.rawStatus === 'completed');
    return completed.length ? completed[completed.length - 1] : null;
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

  submitDepart() {
    const item = this.data.departAssignment;
    if (!item) return;
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
    this.submitReport(item, 'depart_yard', {
      report_time: `${this.data.today} ${departTime}:00`,
      location_text: '司机端点呼出库',
      note: JSON.stringify({
        action: 'depart_yard',
        depart_time: departTime,
        sleep_hours: sleepHours,
        checks: this.checkedKeys(this.data.preflightChecked)
      })
    }, '已出库');
  },

  submitReturn() {
    const item = this.data.returnAssignment;
    if (!item) return;
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
    this.submitReport(item, 'return_yard', {
      report_time: `${this.data.today} ${returnTime}:00`,
      location_text: '司机端点呼入库',
      note: JSON.stringify({
        action: 'return_yard',
        return_time: returnTime,
        rest_hours: restHours,
        checks: this.checkedKeys(this.data.returnChecked)
      })
    }, '已入库，今日工作结束');
  },

  submitReport(item, reportType, extra, successTitle) {
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
      this.loadTasks();
    }).catch(() => {
      this.setData({ submitting: false });
      wx.showToast({ title: '提交失败', icon: 'none' });
    });
  },

  reportError(result) {
    return {
      execution_status_duplicate_or_regression_not_allowed: '状态已更新，请刷新任务',
      execution_status_skip_not_allowed: '请按流程顺序操作',
      assignment_not_found_for_driver: '未找到司机任务'
    }[result && result.error] || '提交失败';
  },

  buildWeekDays(rows, today) {
    const base = this.parseDate(today);
    return Array.from({ length: 7 }).map((_, index) => {
      const date = this.addDays(base, index);
      return this.decorateCalendarDay(rows, date, today);
    });
  },

  buildMonthDays(rows, today) {
    const base = this.parseDate(today);
    const first = new Date(base.getFullYear(), base.getMonth(), 1);
    const total = new Date(base.getFullYear(), base.getMonth() + 1, 0).getDate();
    return Array.from({ length: total }).map((_, index) => {
      const date = this.addDays(first, index);
      return this.decorateCalendarDay(rows, date, today);
    });
  },

  decorateCalendarDay(rows, date, today) {
    const dateText = this.formatDate(date);
    const count = rows.filter((item) => this.isOnDate(item, dateText)).length;
    return {
      date: dateText,
      day: String(date.getDate()),
      week: ['日', '一', '二', '三', '四', '五', '六'][date.getDay()],
      count,
      selected: dateText === (this.data.selectedDate || today),
      today: dateText === today
    };
  },

  markSelected(days, date) {
    return (days || []).map((item) => ({ ...item, selected: item.date === date }));
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

  formatDayLabel(dateText) {
    const date = this.parseDate(dateText);
    return `${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getDate()).padStart(2, '0')}`;
  }
});
