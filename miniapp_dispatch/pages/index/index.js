const api = require('../../utils/api');

Page({
  data: {
    username: 'admin',
    password: 'admin123',
    session: null,
    dashboard: {
      counts: {},
      latest_orders: [],
      fleet_status: {}
    },
    driverStats: [],
    visibleDriverStats: [],
    pressureExpanded: false,
    notifications: [],
    error: '',
    loading: false
  },

  onShow() {
    this.setData({ session: api.getSession() });
    if (this.data.session) this.loadDashboard();
  },

  onUsername(e) {
    this.setData({ username: e.detail.value });
  },

  onPassword(e) {
    this.setData({ password: e.detail.value });
  },

  login() {
    this.setData({ loading: true, error: '' });
    api.login(this.data.username, this.data.password)
      .then((res) => {
        api.setSession(res);
        this.setData({ session: res, loading: false });
        return this.loadDashboard();
      })
      .catch(() => this.setData({ loading: false, error: '登录失败，请检查账号密码或后端服务。' }));
  },

  loadDashboard() {
    this.setData({ loading: true, error: '' });
    return Promise.all([
      api.dashboard(),
      api.notifications().catch(() => ({ notifications: [] })),
      api.assignments().catch(() => ({ assignments: [] })),
      api.drivers().catch(() => ({ drivers: [] }))
    ])
      .then(([dashboard, notifications, assignments, drivers]) => {
        const driverStats = this.buildDriverStats(assignments.assignments || [], drivers.drivers || []);
        this.setData({
          dashboard,
          notifications: (notifications.notifications || []).slice(0, 5),
          driverStats,
          visibleDriverStats: this.visibleDriverStats(driverStats, this.data.pressureExpanded),
          loading: false
        });
      })
      .catch(() => this.setData({ loading: false, error: '无法加载移动调度首页。' }));
  },

  goDispatch() {
    wx.switchTab({ url: '/pages/dispatch/index' });
  },

  goFinance() {
    wx.switchTab({ url: '/pages/finance/index' });
  },

  togglePressureList() {
    const pressureExpanded = !this.data.pressureExpanded;
    this.setData({
      pressureExpanded,
      visibleDriverStats: this.visibleDriverStats(this.data.driverStats, pressureExpanded)
    });
  },

  visibleDriverStats(driverStats, expanded) {
    return expanded ? driverStats : driverStats.slice(0, 3);
  },

  buildDriverStats(assignments, drivers) {
    const now = new Date();
    const today = this.formatDate(now);
    const monthPrefix = today.slice(0, 7);
    const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
    const byDriver = {};
    drivers.forEach((driver) => {
      byDriver[driver.id] = {
        driver_id: driver.id,
        driver_name: driver.name,
        today_orders: 0,
        month_orders: 0,
        active_days: new Set()
      };
    });
    assignments.forEach((item) => {
      const driverId = item.driver_id;
      if (!byDriver[driverId]) return;
      const day = item.order_date || '';
      if (day === today) byDriver[driverId].today_orders += 1;
      if (day.indexOf(monthPrefix) === 0) {
        byDriver[driverId].month_orders += 1;
        byDriver[driverId].active_days.add(day);
      }
    });
    return Object.values(byDriver)
      .map((item) => {
        const continuous = this.continuousWorkDays(item.active_days, today);
        return {
          ...item,
          rest_days: Math.max(0, daysInMonth - item.active_days.size),
          continuous_days: continuous,
          alert: continuous > 13
        };
      })
      .sort((a, b) => {
        if (b.continuous_days !== a.continuous_days) return b.continuous_days - a.continuous_days;
        if (b.month_orders !== a.month_orders) return b.month_orders - a.month_orders;
        return b.today_orders - a.today_orders;
      });
  },

  continuousWorkDays(activeDays, today) {
    let count = 0;
    const cursor = new Date(`${today}T00:00:00`);
    while (count < 31) {
      const key = this.formatDate(cursor);
      if (!activeDays.has(key)) break;
      count += 1;
      cursor.setDate(cursor.getDate() - 1);
    }
    return count;
  },

  formatDate(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }
});
