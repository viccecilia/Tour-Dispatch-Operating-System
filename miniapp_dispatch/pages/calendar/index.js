const api = require('../../utils/api');

const JAPAN_HOLIDAYS_2026 = {
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

Page({
  data: {
    mode: 'week',
    dateFrom: '',
    dateTo: '',
    selectedDate: '',
    days: [],
    calendarDays: [],
    weekdayHeaders: [
      { label: '周一' },
      { label: '周二' },
      { label: '周三' },
      { label: '周四' },
      { label: '周五' },
      { label: '周六', holiday: true },
      { label: '周日', holiday: true }
    ],
    assignments: [],
    dayRows: [],
    loading: false,
    rangeLabel: '本周'
  },

  onShow() {
    api.setActiveTab('/pages/calendar/index');
    this.refreshTabBar();
    if (!this.data.selectedDate) {
      const today = this.formatDate(new Date());
      this.applyRange('week', today);
    }
    this.loadCalendar();
  },

  onPullDownRefresh() {
    const base = this.data.selectedDate || this.formatDate(new Date());
    const nextMode = this.data.mode === 'month' ? 'week' : 'month';
    this.applyRange(nextMode, base);
    this.rebuildDays();
    wx.stopPullDownRefresh();
  },

  refreshTabBar() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) this.getTabBar().refresh();
  },

  loadCalendar() {
    this.setData({ loading: true });
    api.assignments()
      .then((res) => {
        const assignments = (res.assignments || []).map((item) => this.decorateAssignment(item));
        this.setData({ assignments, loading: false });
        this.rebuildDays();
      })
      .catch(() => {
        this.setData({ loading: false });
        wx.showToast({ title: '日历读取失败', icon: 'none' });
      });
  },

  toggleRange() {
    const base = this.data.selectedDate || this.formatDate(new Date());
    const nextMode = this.data.mode === 'month' ? 'week' : 'month';
    this.applyRange(nextMode, base);
    this.rebuildDays();
  },

  onDateFrom(e) {
    this.setData({ mode: 'custom', dateFrom: e.detail.value, rangeLabel: '自定义' });
    this.rebuildDays();
  },

  onDateTo(e) {
    this.setData({ mode: 'custom', dateTo: e.detail.value, rangeLabel: '自定义' });
    this.rebuildDays();
  },

  selectDay(e) {
    const date = e.currentTarget.dataset.date;
    if (!date) return;
    this.setData({ selectedDate: date });
    this.rebuildRowsForDate(date);
  },

  applyRange(mode, baseDate) {
    const range = this.rangeForMode(mode, baseDate);
    this.setData({
      mode,
      selectedDate: baseDate,
      dateFrom: range.from,
      dateTo: range.to,
      rangeLabel: mode === 'month' ? '本月' : '本周'
    });
  },

  rebuildDays() {
    const days = this.datesBetween(this.data.dateFrom, this.data.dateTo).map((date) => {
      const rows = this.rowsForDate(date);
      const incidentCount = rows.filter((row) => row.incident).length;
      const dayMeta = this.dayMeta(date);
      return {
        date,
        label: date.slice(5),
        weekday: dayMeta.weekday,
        attendanceCount: rows.length,
        incidentCount,
        active: date === this.data.selectedDate,
        holiday: dayMeta.isHoliday,
        weekend: dayMeta.isWeekend,
        holidayName: dayMeta.holidayName
      };
    });
    const calendarDays = this.padCalendarDays(days);
    const selectedDate = days.some((item) => item.date === this.data.selectedDate)
      ? this.data.selectedDate
      : (days[0] ? days[0].date : this.data.selectedDate);
    this.setData({ days, calendarDays, selectedDate });
    this.rebuildRowsForDate(selectedDate);
  },

  padCalendarDays(days) {
    if (!days.length) return [];
    const first = new Date(`${days[0].date}T00:00:00`);
    const last = new Date(`${days[days.length - 1].date}T00:00:00`);
    const leading = first.getDay() === 0 ? 6 : first.getDay() - 1;
    const trailing = 6 - (last.getDay() === 0 ? 6 : last.getDay() - 1);
    const leadingCells = Array.from({ length: leading }, (_, index) => ({
      key: `leading-${index}`,
      empty: true
    }));
    const trailingCells = Array.from({ length: trailing }, (_, index) => ({
      key: `trailing-${index}`,
      empty: true
    }));
    return [
      ...leadingCells,
      ...days.map((item) => ({ ...item, key: item.date })),
      ...trailingCells
    ];
  },

  rebuildRowsForDate(date) {
    this.setData({ dayRows: this.rowsForDate(date) });
  },

  rowsForDate(date) {
    return (this.data.assignments || []).filter((item) => item.date === date);
  },

  decorateAssignment(item) {
    const status = String(item.execution_status || item.status || '');
    const orderStatus = String(item.order_status || '');
    const incident = ['incident', 'exception', 'delayed'].indexOf(orderStatus || status) >= 0;
    return {
      id: item.assignment_id || item.id || item.oid || item.order_id,
      date: String(item.order_date || '').slice(0, 10),
      time: item.start_time || '--:--',
      driver: item.driver_name || '未定司机',
      vehicle: item.plate_number || '未定车辆',
      route: `${item.pickup_location || '-'} -> ${item.dropoff_location || '-'}`,
      status: this.statusText(status),
      sleep: item.sleep_hours || item.sleep_time || '-',
      departCall: item.depart_call_time || '-',
      departTime: item.departure_time || item.vehicle_out_time || '-',
      returnTime: item.return_time || item.vehicle_in_time || '-',
      rest: item.rest_time || item.break_time || '-',
      incident
    };
  },

  rangeForMode(mode, baseText) {
    const base = new Date(`${baseText}T00:00:00`);
    if (mode === 'month') {
      const from = new Date(base.getFullYear(), base.getMonth(), 1);
      const to = new Date(base.getFullYear(), base.getMonth() + 1, 0);
      return { from: this.formatDate(from), to: this.formatDate(to) };
    }
    const day = base.getDay();
    const mondayOffset = day === 0 ? -6 : 1 - day;
    const from = new Date(base);
    from.setDate(base.getDate() + mondayOffset);
    const to = new Date(from);
    to.setDate(from.getDate() + 6);
    return { from: this.formatDate(from), to: this.formatDate(to) };
  },

  datesBetween(fromText, toText) {
    const from = new Date(`${fromText}T00:00:00`);
    const to = new Date(`${toText}T00:00:00`);
    if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime()) || from > to) return [];
    const days = [];
    const cursor = new Date(from);
    while (cursor <= to && days.length < 62) {
      days.push(this.formatDate(cursor));
      cursor.setDate(cursor.getDate() + 1);
    }
    return days;
  },

  dayMeta(dateText) {
    const date = new Date(`${dateText}T00:00:00`);
    const day = date.getDay();
    const holidayName = this.japanHolidayName(dateText);
    return {
      weekday: ['日', '一', '二', '三', '四', '五', '六'][day] || '',
      isWeekend: day === 0 || day === 6,
      isHoliday: Boolean(holidayName) || day === 0 || day === 6,
      holidayName
    };
  },

  japanHolidayName(dateText) {
    if (JAPAN_HOLIDAYS_2026[dateText]) return JAPAN_HOLIDAYS_2026[dateText];
    const date = new Date(`${dateText}T00:00:00`);
    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    const day = date.getDate();
    const week = Math.floor((day - 1) / 7) + 1;
    const weekday = date.getDay();
    if (month === 1 && week === 2 && weekday === 1) return '成人の日';
    if (month === 7 && week === 3 && weekday === 1) return '海の日';
    if (month === 9 && week === 3 && weekday === 1) return '敬老の日';
    if (month === 10 && week === 2 && weekday === 1) return 'スポーツの日';
    const fixed = {
      '01-01': '元日',
      '02-11': '建国記念の日',
      '02-23': '天皇誕生日',
      '04-29': '昭和の日',
      '05-03': '憲法記念日',
      '05-04': 'みどりの日',
      '05-05': 'こどもの日',
      '08-11': '山の日',
      '11-03': '文化の日',
      '11-23': '勤労感謝の日'
    };
    const key = `${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    if (fixed[key]) return fixed[key];
    if (month === 3 && day === this.springEquinoxDay(year)) return '春分の日';
    if (month === 9 && day === this.autumnEquinoxDay(year)) return '秋分の日';
    return '';
  },

  springEquinoxDay(year) {
    return Math.floor(20.8431 + 0.242194 * (year - 1980) - Math.floor((year - 1980) / 4));
  },

  autumnEquinoxDay(year) {
    return Math.floor(23.2488 + 0.242194 * (year - 1980) - Math.floor((year - 1980) / 4));
  },

  statusText(status) {
    return {
      assigned: '待确认',
      confirmed: '已接单',
      departed: '已出库',
      arrived: '已到达',
      in_service: '执行中',
      completed: '已完成',
      returned: '已入库'
    }[status] || status || '-';
  },

  formatDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  }
});
