const api = require('../../utils/api');

Page({
  data: {
    office: 'all',
    offices: [
      { key: 'all', label: '全部' },
      { key: 'osaka', label: '大阪' },
      { key: 'kyoto', label: '京都' },
      { key: 'unknown', label: '未标注' }
    ],
    summary: { total: 0, working: 0, idle: 0, alerts: 0 },
    workingRows: [],
    idleRows: [],
    alertRows: [],
    allDrivers: [],
    assignments: []
  },

  onShow() {
    api.setActiveTab('/package_company_lite/pages/attendance-drivers/index');
    this.refreshTabBar();
    this.loadData();
  },

  refreshTabBar() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) this.getTabBar().refresh();
  },

  switchOffice(e) {
    const office = e.currentTarget.dataset.office || 'all';
    this.setData({ office });
    this.rebuildRows(office, this.data.allDrivers, this.data.assignments);
  },

  loadData() {
    Promise.all([
      api.drivers().catch(() => ({ drivers: [] })),
      api.assignments().catch(() => ({ assignments: [] }))
    ]).then((results) => {
      const drivers = ((results[0] && results[0].drivers) || []).map((item) => this.decorateDriver(item));
      const assignments = (results[1] && results[1].assignments) || [];
      this.setData({ allDrivers: drivers, assignments });
      this.rebuildRows(this.data.office, drivers, assignments);
    }).catch(() => {
      wx.showToast({ title: '司机出勤读取失败', icon: 'none' });
    });
  },

  rebuildRows(office, drivers, assignments) {
    const today = this.formatDate(new Date());
    const todayAssignments = (assignments || []).filter((item) => {
      return String(item.order_date || item.start_date || '').slice(0, 10) === today;
    });
    const byDriver = {};
    todayAssignments.forEach((item) => {
      const id = Number(item.driver_id || 0);
      if (!id) return;
      if (!byDriver[id]) byDriver[id] = [];
      byDriver[id].push(item);
    });

    const filtered = (drivers || []).filter((item) => this.officeMatches(office, item.officeKey));
    const workingRows = [];
    const idleRows = [];
    const alertRows = [];

    filtered.forEach((driver) => {
      const tasks = byDriver[Number(driver.id || 0)] || [];
      const row = {
        ...driver,
        taskLine: tasks.length ? this.taskLine(tasks[0], tasks.length) : '今天暂无任务',
        statusText: tasks.length ? `${tasks.length} 单` : '空闲'
      };
      if (tasks.length) workingRows.push(row);
      else idleRows.push(row);

      const alerts = this.driverAlerts(driver);
      if (alerts.length) {
        alertRows.push({
          ...driver,
          alertText: alerts.join(' / '),
          alertLevel: alerts.some((text) => text.indexOf('已过期') >= 0) ? '已过期' : '临近'
        });
      }
    });

    this.setData({
      workingRows,
      idleRows,
      alertRows,
      summary: {
        total: filtered.length,
        working: workingRows.length,
        idle: idleRows.length,
        alerts: alertRows.length
      }
    });
  },

  decorateDriver(driver) {
    const officeRaw = driver.office || driver.branch || driver.sales_office || driver.depot || driver.base || '';
    const officeKey = this.officeKey(officeRaw);
    return {
      id: driver.id,
      name: driver.name || driver.driver_name || '-',
      phone: driver.phone || driver.mobile || '-',
      code: driver.driver_code || driver.code || '-',
      officeRaw,
      officeKey,
      officeLabel: this.officeLabel(officeKey),
      healthDue: driver.health_check_due_date || this.addDays(driver.health_check_date, 365),
      licenseDue: driver.license_due_date || driver.license_expiry_date
    };
  },

  taskLine(task, count) {
    const route = `${task.pickup_location || '-'} -> ${task.dropoff_location || '-'}`;
    const time = task.start_time || '--:--';
    const plate = task.plate_number || '未定车辆';
    return `${time} | ${route} | ${plate}${count > 1 ? ` | 共 ${count} 单` : ''}`;
  },

  driverAlerts(driver) {
    return [
      this.dueText('体检', driver.healthDue),
      this.dueText('驾照', driver.licenseDue)
    ].filter(Boolean);
  },

  dueText(label, dateText) {
    const days = this.daysUntil(dateText);
    if (days === null || days > 30) return '';
    if (days < 0) return `${label}已过期${Math.abs(days)}天`;
    return `${label}${days}天后到期`;
  },

  officeMatches(filter, officeKey) {
    return filter === 'all' || filter === officeKey;
  },

  officeKey(value) {
    const text = String(value || '').toLowerCase();
    if (text.indexOf('大阪') >= 0 || text.indexOf('osaka') >= 0) return 'osaka';
    if (text.indexOf('京都') >= 0 || text.indexOf('kyoto') >= 0) return 'kyoto';
    return 'unknown';
  },

  officeLabel(key) {
    return { osaka: '大阪营业所', kyoto: '京都营业所', unknown: '未标注营业所' }[key] || '未标注营业所';
  },

  daysUntil(dateText) {
    if (!dateText) return null;
    const target = new Date(`${dateText}T00:00:00`);
    if (Number.isNaN(target.getTime())) return null;
    const now = new Date();
    const base = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return Math.ceil((target.getTime() - base.getTime()) / 86400000);
  },

  addDays(dateText, days) {
    if (!dateText) return '';
    const date = new Date(`${dateText}T00:00:00`);
    if (Number.isNaN(date.getTime())) return '';
    date.setDate(date.getDate() + days);
    return this.formatDate(date);
  },

  formatDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  }
});
