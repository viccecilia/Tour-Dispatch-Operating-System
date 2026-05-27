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
    notificationExpanded: false,
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
    const account = String(this.data.username || '').trim();
    const isPhone = /^\+?[\d\s-]{6,}$/.test(account);
    const mockOpenid = wx.getStorageSync('super_wechat_openid')
      || wx.getStorageSync('dispatch_mock_openid')
      || `dispatch-miniapp-${account.replace(/\D/g, '')}`;
    if (isPhone && !wx.getStorageSync('dispatch_mock_openid')) wx.setStorageSync('dispatch_mock_openid', mockOpenid);
    const loginTask = isPhone ? api.loginPhone(account, this.data.password, mockOpenid) : api.login(account, this.data.password);
    loginTask
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
        const notificationRows = (notifications.notifications || []).slice(0, 8).map((item) => this.decorateNotification(item));
        this.setData({
          dashboard,
          notifications: notificationRows,
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

  scrollToNotifications() {
    wx.pageScrollTo({ selector: '.notifications-panel', duration: 240 });
  },

  toggleNotifications() {
    this.setData({ notificationExpanded: !this.data.notificationExpanded });
  },

  onNotificationTap(e) {
    const id = Number(e.currentTarget.dataset.id);
    const item = this.data.notifications.find((row) => Number(row.id) === id);
    if (!item) return;
    wx.showModal({
      title: item.title || item.typeText || '通知详情',
      content: [
        item.body || '暂无详细内容',
        '',
        `类型：${item.typeText}`,
        `级别：${item.priorityText}`,
        `状态：${item.statusText}`,
        item.created_at ? `时间：${item.created_at}` : ''
      ].filter(Boolean).join('\n'),
      showCancel: false,
      confirmText: '知道了'
    });
  },

  decorateNotification(item) {
    return {
      ...item,
      typeText: this.notificationTypeText(item.notification_type),
      priorityText: this.priorityText(item.priority),
      statusText: item.status === 'read' ? '已读' : '未读',
      isUnread: item.status !== 'read'
    };
  },

  notificationTypeText(type) {
    return {
      dispatch_assigned: '派车通知',
      driver_report: '司机报备',
      incident: '异常通知',
      resource_reminder: '到期提醒',
      workflow_reminder: '规则提醒',
      workflow_suggestion: '派车建议',
      new_order: '新订单',
      upcoming_start: '即将开始',
      delay_risk: '延误风险',
      system: '系统通知'
    }[type] || type || '系统通知';
  },

  priorityText(priority) {
    return {
      critical: '紧急',
      high: '高',
      normal: '普通',
      low: '低'
    }[priority] || '普通';
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
