const api = require('../../utils/api');

const WEEKDAY_LABELS = ['日', '一', '二', '三', '四', '五', '六'];
const MAX_GENERATED_CALENDAR_DAYS = 10000;

const JAPAN_HOLIDAYS_2026 = {
  '2026-01-01': '元日',
  '2026-01-12': '成人日',
  '2026-02-11': '建国纪念日',
  '2026-02-23': '天皇诞生日',
  '2026-03-20': '春分日',
  '2026-04-29': '昭和日',
  '2026-05-03': '宪法纪念日',
  '2026-05-04': '绿之日',
  '2026-05-05': '儿童日',
  '2026-05-06': '振替休日',
  '2026-07-20': '海之日',
  '2026-08-11': '山之日',
  '2026-09-21': '敬老日',
  '2026-09-22': '国民之日',
  '2026-09-23': '秋分日',
  '2026-10-12': '体育日',
  '2026-11-03': '文化日',
  '2026-11-23': '勤劳感谢日'
};

Page({
  data: {
    mode: '30d',
    anchorDate: '',
    selectedDate: '',
    displayMonth: '',
    displayYear: '',
    displayMonthLabel: '',
    rangeStart: '',
    rangeEnd: '',
    visibleRangeStart: '',
    visibleRangeEnd: '',
    timelineMinDate: '',
    timelineMaxDate: '',
    timelineScrollTopTarget: 0,
    viewportStartRowIndex: 0,
    weekScrollLeftTarget: 0,
    weekCardStepPx: 46,
    weekTimelineStart: '',
    calendarMonths: [],
    timelineWeeks: [],
    weekDays: [],
    weekdayHeaders: [
      { label: '一' },
      { label: '二' },
      { label: '三' },
      { label: '四' },
      { label: '五' },
      { label: '六', holiday: true },
      { label: '日', holiday: true }
    ],
    assignments: [],
    drivers: [],
    vehicles: [],
    driverFilterIndex: 0,
    vehicleFilterIndex: 0,
    driverFilterOptions: ['全部司机'],
    vehicleFilterOptions: ['全部车辆'],
    driverGroups: [],
    activeDriverKey: '',
    activeDriverTitle: '',
    activeDriverMeta: '',
    dayRows: [],
    summary: {
      total: 0,
      idleDrivers: 0,
      idleVehicles: 0
    },
    loading: false
  },

  onShow() {
    api.setActiveTab('/package_dispatch/pages/calendar/index');
    this.refreshTabBar();
    const today = this.formatDate(new Date());
    if (!this.data.anchorDate) {
      const initialWindow = this.buildCalendarWindowState(today, this.data.mode);
      this.setData({
        anchorDate: today,
        selectedDate: today,
        displayMonth: initialWindow.displayMonth,
        displayYear: initialWindow.displayYear,
        displayMonthLabel: initialWindow.displayMonthLabel,
        visibleRangeStart: initialWindow.visibleRangeStart,
        visibleRangeEnd: initialWindow.visibleRangeEnd,
        timelineScrollTopTarget: 0,
        viewportStartRowIndex: 0,
        weekScrollLeftTarget: 0,
        weekTimelineStart: ''
      });
    }
    this.loadCalendar();
  },

  onReady() {
    this.measureWeekCardStep();
  },

  onPullDownRefresh() {
    this.loadCalendar().finally(() => wx.stopPullDownRefresh());
  },

  refreshTabBar() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().refresh();
    }
  },

  loadCalendar() {
    this.setData({ loading: true });
    return Promise.all([
      api.assignments().catch((err) => ({
        assignments: [],
        error: err && (err.error || err.errMsg || err.message) || 'assignments_failed'
      })),
      api.drivers().catch(() => ({ drivers: [] })),
      api.vehicles().catch(() => ({ vehicles: [] }))
    ])
      .then(([res, driversRes, vehiclesRes]) => {
        const assignments = (res.assignments || []).map((item) => this.decorateAssignment(item));
        this.setData({
          assignments,
          drivers: driversRes.drivers || [],
          vehicles: vehiclesRes.vehicles || [],
          driverFilterOptions: this.buildFilterOptions(assignments, 'driver'),
          vehicleFilterOptions: this.buildFilterOptions(assignments, 'vehicle'),
          loading: false
        });
        this.rebuildCalendar();
        if (res.error) {
          wx.showToast({ title: '订单接口暂不可用，已显示空日历', icon: 'none' });
        }
      })
      .catch(() => {
        this.setData({ loading: false });
        this.rebuildCalendar();
        wx.showToast({ title: '日历数据暂不可用，已显示空日历', icon: 'none' });
      });
  },

  onAnchorDateChange(e) {
    const date = e.detail.value || this.formatDate(new Date());
    const windowState = this.buildCalendarWindowState(date, this.data.mode);
    this.setData({
      anchorDate: date,
      selectedDate: date,
      displayMonth: windowState.displayMonth,
      displayYear: windowState.displayYear,
      displayMonthLabel: windowState.displayMonthLabel,
      visibleRangeStart: windowState.visibleRangeStart,
      visibleRangeEnd: windowState.visibleRangeEnd,
      timelineScrollTopTarget: 0,
      viewportStartRowIndex: 0,
      weekScrollLeftTarget: 0,
      weekTimelineStart: ''
    });
    this.rebuildCalendar();
  },

  toggleRange() {
    const nextMode = this.data.mode === '30d' ? '7d' : '30d';
    const selectedDate = this.data.selectedDate || this.data.anchorDate || this.formatDate(new Date());
    const windowState = this.buildCalendarWindowState(selectedDate, nextMode);
    this.setData({
      mode: nextMode,
      anchorDate: selectedDate,
      selectedDate,
      displayMonth: windowState.displayMonth,
      displayYear: windowState.displayYear,
      displayMonthLabel: windowState.displayMonthLabel,
      visibleRangeStart: windowState.visibleRangeStart,
      visibleRangeEnd: windowState.visibleRangeEnd,
      timelineScrollTopTarget: 0,
      viewportStartRowIndex: 0,
      weekScrollLeftTarget: 0,
      weekTimelineStart: ''
    });
    this.rebuildCalendar();
    if (nextMode === '7d') {
      wx.nextTick(() => this.measureWeekCardStep());
    }
  },

  onDriverFilterChange(e) {
    this.setData({ driverFilterIndex: Number(e.detail.value || 0) });
    this.rebuildCalendar();
  },

  onVehicleFilterChange(e) {
    this.setData({ vehicleFilterIndex: Number(e.detail.value || 0) });
    this.rebuildCalendar();
  },

  selectDay(e) {
    const date = e.currentTarget.dataset.date;
    if (!date) return;
    if (this.data.mode === '7d') {
      this.setData({
        selectedDate: date,
        anchorDate: date,
        weekDays: this.annotateWeekDays(this.data.weekDays || [], date)
      });
      this.rebuildDriverGroups(date);
      return;
    }
    const windowState = this.buildCalendarWindowState(date, this.data.mode);
    const baseDisplayMonth = this.data.displayMonth || windowState.displayMonth;
    const calendarMonths = this.buildCalendarMonths(baseDisplayMonth, date);
    const firstMonth = calendarMonths[0];
    const lastMonth = calendarMonths[calendarMonths.length - 1];
    this.setData({
      selectedDate: date,
      anchorDate: date,
      displayMonth: baseDisplayMonth,
      displayYear: baseDisplayMonth.slice(0, 4),
      displayMonthLabel: baseDisplayMonth.slice(5, 7),
      visibleRangeStart: firstMonth ? firstMonth.visibleRangeStart : windowState.visibleRangeStart,
      visibleRangeEnd: lastMonth ? lastMonth.visibleRangeEnd : windowState.visibleRangeEnd,
      rangeStart: firstMonth ? firstMonth.visibleRangeStart : windowState.visibleRangeStart,
      rangeEnd: lastMonth ? lastMonth.visibleRangeEnd : windowState.visibleRangeEnd,
      calendarMonths,
      timelineWeeks: this.buildMonthWeeks(baseDisplayMonth, date)
    });
    this.rebuildDriverGroups(date);
  },

  onTimelineScroll(e) {
    if (this.data.mode !== '30d') return;
    return;
    const scrollTop = Number((e.detail && e.detail.scrollTop) || 0);
    const rowHeight = 114;
    const rowIndex = Math.max(0, Math.floor(scrollTop / rowHeight));
    const weeks = this.data.timelineWeeks || [];
    const row = weeks[rowIndex];
    if (!row || !row.cells || !row.cells.length) return;

    const visibleRangeStart = row.cells[0].date;
    if (rowIndex === this.data.viewportStartRowIndex && visibleRangeStart === this.data.visibleRangeStart) return;

    const viewport = this.resolveViewportState(weeks, rowIndex);
    const displayMonth = viewport.displayMonth;
    const visibleRangeEnd = viewport.visibleRangeEnd;

    this.setData({
      viewportStartRowIndex: rowIndex,
      visibleRangeStart,
      visibleRangeEnd,
      rangeStart: viewport.highlightStart,
      rangeEnd: viewport.highlightEnd,
      displayMonth,
      displayYear: displayMonth.slice(0, 4),
      displayMonthLabel: displayMonth.slice(5, 7),
      timelineWeeks: this.annotateTimelineWeeks(weeks, viewport)
    });
  },

  onWeekTimelineScroll(e) {
    if (this.data.mode !== '7d') return;
    const scrollLeft = Number((e.detail && e.detail.scrollLeft) || 0);
    clearTimeout(this.weekScrollTimer);
    this.weekScrollTimer = setTimeout(() => {
      const step = Math.max(1, Number(this.data.weekCardStepPx || 46));
      const index = Math.max(0, Math.round(scrollLeft / step));
      this.applyWeekScrollIndex(index);
    }, 120);
  },

  applyWeekScrollIndex(index) {
    const weekDays = this.data.weekDays || [];
    if (!weekDays.length) return;
    const safeIndex = Math.max(0, Math.min(weekDays.length - 1, Number(index || 0)));
    const startCell = weekDays[safeIndex];
    if (!startCell || !startCell.date || startCell.date === this.data.selectedDate) return;

    const endCell = weekDays[Math.min(weekDays.length - 1, safeIndex + 6)] || startCell;
    const midCell = weekDays[Math.min(weekDays.length - 1, safeIndex + 3)] || startCell;
    const displayMonth = `${midCell.date.slice(0, 7)}-01`;
    const selectedDate = startCell.date;
    this.setData({
      anchorDate: selectedDate,
      selectedDate,
      displayMonth,
      displayYear: displayMonth.slice(0, 4),
      displayMonthLabel: displayMonth.slice(5, 7),
      rangeStart: selectedDate,
      rangeEnd: endCell.date,
      visibleRangeStart: selectedDate,
      visibleRangeEnd: endCell.date,
      weekDays: this.annotateWeekDays(weekDays, selectedDate)
    });
    this.rebuildDriverGroups(selectedDate);
  },

  measureWeekCardStep() {
    wx.nextTick(() => {
      const query = wx.createSelectorQuery();
      query.select('.week-card').boundingClientRect();
      query.exec((res) => {
        const rect = res && res[0];
        if (!rect || !rect.width) return;
        const gapPx = 4;
        const step = Math.max(1, Number(rect.width) + gapPx);
        if (Math.abs(step - Number(this.data.weekCardStepPx || 0)) < 1) return;
        this.setData({ weekCardStepPx: step });
        if (this.data.mode === '7d') {
          const index = Math.max(0, (this.data.weekDays || []).findIndex((item) => item.date === this.data.selectedDate));
          this.setData({ weekScrollLeftTarget: index * step });
        }
      });
    });
  },

  selectDriverGroup(e) {
    const key = e.currentTarget.dataset.key || '';
    this.setData({ activeDriverKey: key });
    this.rebuildDriverGroups(this.data.selectedDate || this.data.anchorDate);
  },

  rebuildCalendar() {
    const anchorDate = this.data.anchorDate || this.formatDate(new Date());
    let selectedDate = this.data.selectedDate || anchorDate;
    const initialVisibleStart = this.data.visibleRangeStart || anchorDate;
    const timelineBounds = this.computeTimelineBounds(anchorDate);
    const range = this.computeRange(this.data.mode, initialVisibleStart);
    const baseWindowState = this.buildCalendarWindowState(initialVisibleStart, this.data.mode);

    let displayMonth = baseWindowState.displayMonth;
    let displayYear = baseWindowState.displayYear;
    let displayMonthLabel = baseWindowState.displayMonthLabel;
    let visibleRangeStart = initialVisibleStart;
    let visibleRangeEnd = baseWindowState.visibleRangeEnd;
    let timelineScrollTopTarget = this.data.timelineScrollTopTarget || 0;
    let viewportStartRowIndex = Math.max(0, Number(this.data.viewportStartRowIndex || 0));
    let weekScrollLeftTarget = this.data.weekScrollLeftTarget || 0;
    let weekTimelineStart = this.data.weekTimelineStart || '';
    let rangeStart = range.start;
    let rangeEnd = range.end;
    let calendarMonths = [];
    let timelineWeeks = [];
    let weekDays = [];

    if (this.data.mode === '30d') {
      displayMonth = selectedDate ? `${selectedDate.slice(0, 7)}-01` : displayMonth;
      displayYear = displayMonth.slice(0, 4);
      displayMonthLabel = displayMonth.slice(5, 7);
      calendarMonths = this.buildCalendarMonths(displayMonth, selectedDate);
      visibleRangeStart = calendarMonths[0] ? calendarMonths[0].visibleRangeStart : this.startOfWeekMonday(displayMonth);
      visibleRangeEnd = calendarMonths[calendarMonths.length - 1]
        ? calendarMonths[calendarMonths.length - 1].visibleRangeEnd
        : this.addDays(visibleRangeStart, 41);
      rangeStart = visibleRangeStart;
      rangeEnd = visibleRangeEnd;
      timelineWeeks = this.buildMonthWeeks(displayMonth, selectedDate);
      viewportStartRowIndex = 0;
      timelineScrollTopTarget = 0;
    } else {
      const weekBounds = this.computeWeekTimelineBounds(anchorDate);
      const baseDays = this.buildWeekTimelineDays(weekBounds.start, weekBounds.end);
      const selectedIndex = Math.max(0, baseDays.findIndex((item) => item.date === selectedDate));
      const weekStartCell = baseDays[selectedIndex] || baseDays[0];
      const weekEndCell = baseDays[Math.min(baseDays.length - 1, selectedIndex + 6)] || weekStartCell;
      const weekMidCell = baseDays[Math.min(baseDays.length - 1, selectedIndex + 3)] || weekStartCell;
      const weekStart = weekStartCell ? weekStartCell.date : selectedDate;
      const weekEnd = weekEndCell ? weekEndCell.date : selectedDate;
      const effectiveSelectedDate = this.isDateWithinRange(selectedDate, weekStart, weekEnd) ? selectedDate : weekStart;
      weekDays = this.annotateWeekDays(baseDays, effectiveSelectedDate);
      rangeStart = weekStart;
      rangeEnd = weekEnd;
      visibleRangeStart = weekStart;
      visibleRangeEnd = weekEnd;
      weekTimelineStart = weekBounds.start;
      weekScrollLeftTarget = selectedIndex * Math.max(1, Number(this.data.weekCardStepPx || 46));
      if (weekMidCell && weekMidCell.date) {
        displayMonth = `${weekMidCell.date.slice(0, 7)}-01`;
        displayYear = displayMonth.slice(0, 4);
        displayMonthLabel = displayMonth.slice(5, 7);
      }
      selectedDate = effectiveSelectedDate;
    }

    this.setData({
      anchorDate,
      selectedDate,
      displayMonth,
      displayYear,
      displayMonthLabel,
      rangeStart,
      rangeEnd,
      visibleRangeStart,
      visibleRangeEnd,
      timelineMinDate: timelineBounds.minDate,
      timelineMaxDate: timelineBounds.maxDate,
      timelineScrollTopTarget,
      viewportStartRowIndex,
      weekScrollLeftTarget,
      weekTimelineStart,
      calendarMonths,
      timelineWeeks,
      weekDays
    });
    this.rebuildDriverGroups(selectedDate);
  },

  rebuildDriverGroups(date) {
    const rows = this.rowsForDate(date);
    const summary = this.buildSummary(date);
    const grouped = this.groupRowsByDriver(rows);
    let activeDriverKey = this.data.activeDriverKey;
    if (!grouped.some((item) => item.key === activeDriverKey)) {
      activeDriverKey = grouped[0] ? grouped[0].key : '';
    }
    const active = grouped.find((item) => item.key === activeDriverKey);
    this.setData({
      summary,
      driverGroups: grouped,
      activeDriverKey,
      activeDriverTitle: active ? active.driver : '',
      activeDriverMeta: active ? `${active.vehicle} · ${active.count} 单` : '',
      dayRows: active ? active.rows : []
    });
  },

  computeRange(mode, anchorText) {
    const anchor = new Date(`${anchorText}T00:00:00`);
    if (mode === '7d') {
      const start = new Date(anchor);
      const end = new Date(anchor);
      end.setDate(end.getDate() + 6);
      return {
        start: this.formatDate(start),
        end: this.formatDate(end)
      };
    }
    return {
      start: anchorText,
      end: this.addDays(anchorText, 34)
    };
  },

  buildCalendarWindowState(startDateText, mode) {
    const seedDate = startDateText || this.formatDate(new Date());
    const displayMonth = mode === '7d'
      ? this.resolveDisplayMonthForWindow(seedDate, mode)
      : `${seedDate.slice(0, 7)}-01`;
    const visibleRangeStart = mode === '7d'
      ? seedDate
      : this.startOfWeekMonday(displayMonth);
    const visibleRangeEnd = mode === '7d'
      ? this.addDays(visibleRangeStart, 6)
      : this.addDays(visibleRangeStart, 41);
    return {
      visibleRangeStart,
      visibleRangeEnd,
      displayMonth,
      displayYear: displayMonth.slice(0, 4),
      displayMonthLabel: displayMonth.slice(5, 7)
    };
  },

  buildMonthWeeks(displayMonth, selectedDate) {
    const gridStart = this.startOfWeekMonday(displayMonth);
    const currentMonth = String(displayMonth || '').slice(0, 7);
    const weeks = [];
    for (let week = 0; week < 6; week += 1) {
      const cells = [];
      for (let dayIndex = 0; dayIndex < 7; dayIndex += 1) {
        const dateText = this.addDays(gridStart, week * 7 + dayIndex);
        const meta = this.dayMeta(dateText);
        const rows = this.rowsForDate(dateText);
        const monthNumber = String(Number(dateText.slice(5, 7)));
        const dayNumber = String(Number(dateText.slice(8, 10)));
        cells.push({
          key: `month-${dateText}`,
          date: dateText,
          label: dayNumber === '1' ? `${monthNumber}/${dayNumber}` : dayNumber,
          attendanceCount: rows.length,
          incidentCount: rows.filter((row) => row.incident).length,
          active: dateText === selectedDate,
          today: dateText === this.formatDate(new Date()),
          holiday: meta.isHoliday,
          outsideMonth: dateText.slice(0, 7) !== currentMonth
        });
      }
      weeks.push({ key: `month-week-${week}`, cells });
    }
    return weeks;
  },

  buildCalendarMonths(baseMonthText, selectedDate) {
    const baseMonth = `${(baseMonthText || selectedDate || this.formatDate(new Date())).slice(0, 7)}-01`;
    const months = [];
    for (let index = 0; index < 6; index += 1) {
      const monthDate = new Date(`${baseMonth}T00:00:00`);
      monthDate.setMonth(monthDate.getMonth() + index);
      const monthText = this.formatDate(monthDate).slice(0, 7) + '-01';
      const weeks = this.buildMonthWeeks(monthText, selectedDate);
      months.push({
        key: `calendar-month-${monthText}`,
        isFirst: index === 0,
        displayMonth: monthText,
        year: monthText.slice(0, 4),
        monthLabel: monthText.slice(5, 7),
        visibleRangeStart: weeks[0] && weeks[0].cells && weeks[0].cells[0] ? weeks[0].cells[0].date : monthText,
        visibleRangeEnd: weeks[5] && weeks[5].cells && weeks[5].cells[6] ? weeks[5].cells[6].date : this.addDays(monthText, 41),
        weeks
      });
    }
    return months;
  },

  resolveDisplayMonthForWindow(startDateText, mode) {
    const centerOffset = mode === '7d' ? 3 : 17;
    const seedDate = this.addDays(startDateText || this.formatDate(new Date()), centerOffset);
    return `${seedDate.slice(0, 7)}-01`;
  },

  buildTimelineWeeks(baseDateText, selectedDate, bounds) {
    const baseDate = new Date(`${baseDateText}T00:00:00`);
    const safeBounds = bounds || this.computeTimelineBounds(baseDateText);
    const gridStart = new Date(`${safeBounds.minDate}T00:00:00`);
    const gridEnd = new Date(`${safeBounds.maxDate}T00:00:00`);
    const monthKey = this.formatMonth(baseDate);
    const weeks = [];
    let week = 0;

    while (true) {
      const rowStart = new Date(gridStart);
      rowStart.setDate(gridStart.getDate() + week * 7);
      if (rowStart > gridEnd) break;

      const cells = [];
      for (let dayIndex = 0; dayIndex < 7; dayIndex += 1) {
        const cursor = new Date(rowStart);
        cursor.setDate(rowStart.getDate() + dayIndex);
        if (cursor > gridEnd) break;
        const dateText = this.formatDate(cursor);
        const meta = this.dayMeta(dateText);
        const rows = this.rowsForDate(dateText);
        const monthNumber = String(Number(dateText.slice(5, 7)));
        const dayNumber = String(Number(dateText.slice(8, 10)));
        cells.push({
          key: `${monthKey}-${dateText}`,
          date: dateText,
          label: dayNumber === '1' ? `${monthNumber}/${dayNumber}` : dayNumber,
          attendanceCount: rows.length,
          incidentCount: rows.filter((row) => row.incident).length,
          active: dateText === selectedDate,
          today: dateText === this.formatDate(new Date()),
          holiday: meta.isHoliday
        });
      }

      if (cells.length) {
        weeks.push({
          key: `${monthKey}-week-${week}`,
          cells
        });
      }
      week += 1;
    }

    return weeks;
  },

  annotateTimelineWeeks(weeks, viewport) {
    return (weeks || []).map((week) => ({
      key: week.key,
      cells: (week.cells || []).map((cell) => ({
        ...cell
      }))
    }));
  },

  computeTimelineBounds(anchorDate) {
    const candidates = [];
    const collect = (value) => {
      const dateText = this.extractDateText(value);
      if (dateText) candidates.push(dateText);
    };

    (this.data.assignments || []).forEach((item) => {
      collect(item.date);
      collect(item.created_at);
    });
    (this.data.drivers || []).forEach((item) => {
      collect(item.company_registration_date);
      collect(item.company_join_date);
      collect(item.created_at);
    });
    (this.data.vehicles || []).forEach((item) => {
      collect(item.company_registration_date);
      collect(item.company_join_date);
      collect(item.created_at);
    });

    const today = this.formatDate(new Date());
    const earliestDate = candidates.sort()[0] || anchorDate || today;
    const futureAnchor = (anchorDate || today) > today ? (anchorDate || today) : today;
    return {
      minDate: this.startOfWeekMonday(earliestDate),
      maxDate: this.endOfWeekSunday(this.addDays(futureAnchor, 365))
    };
  },

  extractDateText(value) {
    const text = String(value || '').trim();
    if (!text) return '';
    const match = text.match(/(\d{4}-\d{2}-\d{2})/);
    return match ? match[1] : '';
  },

  startOfWeekMonday(dateText) {
    const cursor = new Date(`${dateText}T00:00:00`);
    const leading = cursor.getDay() === 0 ? 6 : cursor.getDay() - 1;
    cursor.setDate(cursor.getDate() - leading);
    return this.formatDate(cursor);
  },

  endOfWeekSunday(dateText) {
    const cursor = new Date(`${dateText}T00:00:00`);
    const trailing = cursor.getDay() === 0 ? 0 : 7 - cursor.getDay();
    cursor.setDate(cursor.getDate() + trailing);
    return this.formatDate(cursor);
  },

  resolveViewportState(weeks, startRowIndex) {
    const safeIndex = Math.max(0, Number(startRowIndex || 0));
    const visibleRangeStart = this.firstDateForWeekRow(weeks, safeIndex);
    const visibleRangeEnd = this.lastVisibleDateForRows(weeks, safeIndex, 5);
    const displayMonth = this.resolveDisplayMonthFromViewport(weeks, safeIndex, visibleRangeStart);
    return {
      visibleRangeStart,
      visibleRangeEnd,
      displayMonth,
      highlightStart: visibleRangeStart,
      highlightEnd: visibleRangeEnd
    };
  },

  firstDateForWeekRow(weeks, rowIndex) {
    const row = (weeks || [])[Math.max(0, Number(rowIndex || 0))];
    if (row && row.cells && row.cells.length) {
      return row.cells[0].date;
    }
    return '';
  },

  resolveDisplayMonthFromViewport(weeks, startRowIndex, fallbackDate) {
    const centerRow = (weeks || [])[Math.max(0, Number(startRowIndex || 0)) + 2];
    const centerCells = centerRow && centerRow.cells ? centerRow.cells : [];
    const centerCell = centerCells[3] || centerCells[Math.floor(centerCells.length / 2)] || null;
    const seedDate = centerCell && centerCell.date
      ? centerCell.date
      : (fallbackDate || this.formatDate(new Date()));
    return `${seedDate.slice(0, 7)}-01`;
  },

  lastVisibleDateForRows(weeks, startRowIndex, rowCount) {
    const start = Math.max(0, Number(startRowIndex || 0));
    const end = Math.min((weeks || []).length, start + Math.max(1, Number(rowCount || 5)));
    let lastDate = '';
    for (let rowIndex = start; rowIndex < end; rowIndex += 1) {
      const row = weeks[rowIndex];
      const cells = row && row.cells ? row.cells : [];
      if (cells.length) {
        lastDate = cells[cells.length - 1].date;
      }
    }
    return lastDate || '';
  },

  computeWeekTimelineBounds(anchorText) {
    return {
      start: this.addDays(anchorText, -365),
      end: this.addDays(anchorText, 365)
    };
  },

  buildWeekTimelineDays(startText, endText) {
    return this.datesBetween(startText, endText).map((dateText) => {
      const meta = this.dayMeta(dateText);
      const rows = this.rowsForDate(dateText);
      const monthNumber = String(Number(dateText.slice(5, 7)));
      const dayNumber = String(Number(dateText.slice(8, 10)));
      return {
        key: `week-${dateText}`,
        date: dateText,
        dayNumber,
        shortLabel: dayNumber === '1' ? `${monthNumber}/${dayNumber}` : dayNumber,
        weekday: meta.weekday,
        attendanceCount: rows.length,
        active: false,
        today: dateText === this.formatDate(new Date()),
        holiday: meta.isHoliday
      };
    });
  },

  annotateWeekDays(days, selectedDate) {
    return (days || []).map((item) => ({
      ...item,
      active: item.date === selectedDate
    }));
  },

  isDateWithinRange(dateText, startText, endText) {
    if (!dateText || !startText || !endText) return false;
    return dateText >= startText && dateText <= endText;
  },

  findWeekIndexForDate(weeks, dateText) {
    for (let i = 0; i < (weeks || []).length; i += 1) {
      const row = weeks[i];
      if ((row.cells || []).some((item) => item.date === dateText)) return i;
    }
    return 0;
  },

  addDays(dateText, days) {
    const cursor = new Date(`${dateText}T00:00:00`);
    cursor.setDate(cursor.getDate() + days);
    return this.formatDate(cursor);
  },

  rowsForDate(date) {
    const driverKeyword = this.selectedDriverKeyword();
    const vehicleKeyword = this.selectedVehicleKeyword();
    return (this.data.assignments || []).filter((item) => {
      if (item.date !== date) return false;
      if (driverKeyword && item.driver !== driverKeyword) return false;
      if (vehicleKeyword && item.vehicle !== vehicleKeyword) return false;
      return true;
    });
  },

  groupRowsByDriver(rows) {
    const groups = [];
    rows.forEach((item) => {
      const key = `${item.driver}__${item.vehicle}`;
      let target = groups.find((group) => group.key === key);
      if (!target) {
        target = {
          key,
          driver: item.driver,
          vehicle: item.vehicle,
          count: 0,
          firstTime: item.time || '99:99',
          rows: []
        };
        groups.push(target);
      }
      target.rows.push(item);
      target.count += 1;
      if ((item.time || '99:99') < target.firstTime) target.firstTime = item.time || '99:99';
    });
    groups.forEach((group) => {
      group.rows.sort((a, b) => String(a.time || '').localeCompare(String(b.time || '')));
      group.meta = `${group.count}单 · ${group.vehicle}`;
    });
    return groups.sort((a, b) => String(a.firstTime).localeCompare(String(b.firstTime)));
  },

  decorateAssignment(item) {
    const status = String(item.execution_status || item.status || '');
    const orderStatus = String(item.order_status || '');
    const incident = ['incident', 'exception', 'delayed'].includes(orderStatus || status);
    const guestLine = [
      item.guest_name || '',
      item.guest_contact ? this.formatGuestContact(item.guest_contact) : '',
      item.passenger_count ? `${item.passenger_count}人` : '',
      (item.luggage_count || item.luggage_count === 0) ? `行李 ${item.luggage_count}` : ''
    ].filter(Boolean).join(' · ');
    return {
      id: item.assignment_id || item.id || item.oid || item.order_id,
      date: String(item.order_date || '').slice(0, 10),
      created_at: item.created_at || '',
      time: item.start_time || '--:--',
      driver: item.driver_name || '未安排司机',
      vehicle: item.plate_number || '未安排车辆',
      route: `${item.pickup_location || '-'} -> ${item.dropoff_location || '-'}`,
      status: this.statusText(status),
      rawStatus: status,
      guestLine,
      agency: item.agency_name || '',
      remark: item.remark || '',
      sleep: item.sleep_hours || item.sleep_time || '-',
      departCall: item.depart_call_time || '-',
      departTime: item.departure_time || item.vehicle_out_time || '-',
      returnTime: item.return_time || item.vehicle_in_time || '-',
      rest: item.rest_time || item.break_time || '-',
      incident
    };
  },

  buildFilterOptions(assignments, field) {
    const source = field === 'vehicle'
      ? (assignments || []).map((item) => item.vehicle).filter(Boolean)
      : (assignments || []).map((item) => item.driver).filter(Boolean);
    const unique = [];
    source.forEach((item) => {
      if (!unique.includes(item)) unique.push(item);
    });
    return [field === 'vehicle' ? '全部车辆' : '全部司机'].concat(unique);
  },

  selectedDriverKeyword() {
    const options = this.data.driverFilterOptions || ['全部司机'];
    const value = options[this.data.driverFilterIndex] || '全部司机';
    return value === '全部司机' ? '' : value;
  },

  selectedVehicleKeyword() {
    const options = this.data.vehicleFilterOptions || ['全部车辆'];
    const value = options[this.data.vehicleFilterIndex] || '全部车辆';
    return value === '全部车辆' ? '' : value;
  },

  buildSummary(date) {
    const allRows = (this.data.assignments || []).filter((item) => item.date === date);
    const totalDrivers = (this.data.drivers || []).filter((item) => !this.isRetiredStatus(item.status)).length;
    const totalVehicles = (this.data.vehicles || []).filter((item) => !this.isRetiredStatus(item.status || item.vehicle_status)).length;
    const busyDrivers = [];
    const busyVehicles = [];
    allRows.forEach((item) => {
      if (item.driver && !busyDrivers.includes(item.driver)) busyDrivers.push(item.driver);
      if (item.vehicle && !busyVehicles.includes(item.vehicle)) busyVehicles.push(item.vehicle);
    });
    return {
      total: allRows.length,
      idleDrivers: Math.max(0, totalDrivers - busyDrivers.length),
      idleVehicles: Math.max(0, totalVehicles - busyVehicles.length)
    };
  },

  isRetiredStatus(status) {
    const text = String(status || '').toLowerCase();
    return text.includes('retired') || text.includes('deleted') || text.includes('removed');
  },

  formatGuestContact(value) {
    const phone = String(value || '').trim();
    const region = this.detectPhoneRegion(phone);
    return region ? `${phone} (${region})` : phone;
  },

  detectPhoneRegion(phone) {
    const compact = String(phone || '').trim().replace(/\s+/g, '');
    if (!compact) return '';
    if (compact.indexOf('+81') === 0) return '日本';
    if (compact.indexOf('+86') === 0) return '中国';
    if (compact.indexOf('+852') === 0) return '香港';
    if (compact.indexOf('+853') === 0) return '澳门';
    if (compact.indexOf('+886') === 0) return '台湾';
    if (compact.indexOf('+82') === 0) return '韩国';
    if (compact.indexOf('+60') === 0) return '马来西亚';
    if (compact.indexOf('+65') === 0) return '新加坡';
    if (compact.indexOf('+66') === 0) return '泰国';
    if (compact.indexOf('+1') === 0) return '北美';
    if (compact.indexOf('+44') === 0) return '英国';
    if (compact.indexOf('+61') === 0) return '澳大利亚';
    if (compact.indexOf('+971') === 0) return '阿联酋';
    return '';
  },

  datesBetween(fromText, toText) {
    const from = new Date(`${fromText}T00:00:00`);
    const to = new Date(`${toText}T00:00:00`);
    if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime()) || from > to) return [];
    const days = [];
    const cursor = new Date(from);
    while (cursor <= to && days.length < MAX_GENERATED_CALENDAR_DAYS) {
      days.push(this.formatDate(cursor));
      cursor.setDate(cursor.getDate() + 1);
    }
    return days;
  },

  dayMeta(dateText) {
    const date = new Date(`${dateText}T00:00:00`);
    const day = date.getDay();
    const weekday = WEEKDAY_LABELS[day] || '';
    return {
      weekday,
      isWeekend: day === 0 || day === 6,
      isHoliday: Boolean(this.japanHolidayName(dateText)) || day === 0 || day === 6
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
    if (month === 1 && week === 2 && weekday === 1) return '成人日';
    if (month === 7 && week === 3 && weekday === 1) return '海之日';
    if (month === 9 && week === 3 && weekday === 1) return '敬老日';
    if (month === 10 && week === 2 && weekday === 1) return '体育日';
    if (month === 3 && day === this.springEquinoxDay(year)) return '春分日';
    if (month === 9 && day === this.autumnEquinoxDay(year)) return '秋分日';
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
      assigned: '已分配',
      confirmed: '已确认',
      departed: '已出库',
      arrived: '已到达',
      in_service: '服务中',
      completed: '已完成',
      returned: '已回库'
    }[status] || status || '-';
  },

  formatDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  },

  formatMonth(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-01`;
  }
});
