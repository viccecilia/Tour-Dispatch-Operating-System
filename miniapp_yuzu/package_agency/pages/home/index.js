const api = require('../../utils/api');

function emptyStats() {
  return {
    total: 0,
    published: 0,
    claimed: 0,
    pendingSettlement: 0
  };
}

function rawRole(session) {
  return session && session.account ? String(session.account.role || '').toLowerCase() : '';
}

function roleKind(session) {
  const role = rawRole(session);
  if (role.indexOf('guide') >= 0 || role.indexOf('导游') >= 0) return 'guide';
  if (role.indexOf('service') >= 0 || role.indexOf('support') >= 0 || role.indexOf('customer') >= 0 || role.indexOf('客服') >= 0) return 'service';
  return 'admin';
}

function roleLabel(session) {
  const kind = roleKind(session);
  if (kind === 'guide') return '导游';
  if (kind === 'service') return '客服';
  return '管理';
}

function parseDateTime(date, time) {
  const cleanDate = String(date || new Date().toISOString().slice(0, 10)).slice(0, 10);
  const cleanTime = String(time || '00:00').slice(0, 5);
  const parsed = new Date(`${cleanDate}T${cleanTime}:00`);
  return Number.isNaN(parsed.getTime()) ? new Date() : parsed;
}

function addHours(date, hours) {
  return new Date(date.getTime() + hours * 60 * 60 * 1000);
}

function orderEndAt(order) {
  const start = parseDateTime(order.order_date, order.start_time);
  if (order.end_time) return parseDateTime(order.end_date || order.order_date, order.end_time);
  const typeText = String(order.order_type || '');
  return addHours(start, typeText.indexOf('包车') >= 0 || typeText.indexOf('charter') >= 0 ? 10 : 2);
}

function guideOwnOrders(session, orders) {
  if (roleKind(session) !== 'guide') return orders || [];
  const account = session.account || {};
  const phone = String(account.phone || '').replace(/\D/g, '');
  const name = String(account.display_name || '').trim().toLowerCase();
  return (orders || []).filter((order) => {
    const guidePhone = String(order.guide_phone || order.guide_whatsapp || '').replace(/\D/g, '');
    const guideName = String(order.guide_name || '').trim().toLowerCase();
    if (phone && guidePhone && guidePhone.indexOf(phone.slice(-8)) >= 0) return true;
    if (name && guideName && (guideName.indexOf(name) >= 0 || name.indexOf(guideName) >= 0)) return true;
    return false;
  });
}

function decorateOrder(order) {
  return {
    ...order,
    routeText: `${order.pickup_location || '-'} → ${order.dropoff_location || '-'}`,
    timeText: `${order.order_date || '-'} ${order.start_time || '--:--'}${order.end_time ? `-${order.end_time}` : ''}`,
    guestText: `${order.guest_name || '-'} / ${order.guest_contact || '-'}`,
    driverText: order.driver_name || order.assigned_driver_code || '未显示司机',
    vehicleText: order.plate_number || order.plate_no || order.assigned_vehicle_type || '未显示车辆'
  };
}

Page({
  data: {
    loginCode: '',
    password: '',
    resolvedAgencyName: '',
    session: null,
    roleKind: 'admin',
    roleLabel: '管理',
    isGuide: false,
    isService: false,
    stats: emptyStats(),
    currentOrders: [],
    upcomingOrders: [],
    historyOrders: [],
    serviceOrders: [],
    loading: false,
    loginLoading: false,
    message: ''
  },

  onShow() {
    const session = api.getSession();
    const tabBar = typeof this.getTabBar === 'function' && this.getTabBar();
    if (tabBar) tabBar.setData({ selected: 0 });
    this.applySession(session);
    if (session && session.token) {
      this.loadDashboard();
    }
  },

  applySession(session) {
    const kind = roleKind(session);
    const restricted = kind === 'guide' || kind === 'service';
    this.setData({
      session,
      roleKind: kind,
      roleLabel: roleLabel(session),
      isGuide: kind === 'guide',
      isService: kind === 'service'
    });
    if (restricted) {
      wx.hideTabBar();
    } else {
      wx.showTabBar();
    }
    wx.setNavigationBarTitle({
      title: session && session.agency && session.agency.name ? session.agency.name : '旅行社登录'
    });
  },

  loadDashboard() {
    this.setData({ loading: true, message: '' });
    api.orders()
      .then((orders) => {
        const kind = this.data.roleKind;
        if (kind === 'guide') {
          this.buildGuideDashboard(guideOwnOrders(this.data.session, orders).map(decorateOrder));
          return;
        }
        if (kind === 'service') {
          this.buildServiceDashboard((orders || []).map(decorateOrder));
          return;
        }
        const stats = orders.reduce((acc, order) => {
          const dispatchStatus = order.dispatch_status || '';
          const auctionStatus = order.auction_status || '';
          const settlementStatus = order.settlement_status || order.agency_settlement_status || 'pending';
          acc.total += 1;
          if (['auction_listed', 'bidding'].indexOf(dispatchStatus) >= 0 || ['listed', 'bidding'].indexOf(auctionStatus) >= 0) {
            acc.published += 1;
          }
          if (['auction_claimed', 'claimed', 'assigned'].indexOf(dispatchStatus) >= 0 || order.assignment_id) {
            acc.claimed += 1;
          }
          if (['pending', 'payment_requested', 'receipt_uploaded', 'unsettled'].indexOf(settlementStatus) >= 0) {
            acc.pendingSettlement += 1;
          }
          return acc;
        }, emptyStats());
        this.setData({ stats, loading: false });
      })
      .catch((err) => {
        this.setData({ loading: false, message: `首页数据加载失败：${err.error || err.message || '请重新登录'}` });
      });
  },

  buildGuideDashboard(orders) {
    const grouped = this.groupOrdersForWork(orders);
    this.setData({ ...grouped, loading: false });
  },

  buildServiceDashboard(orders) {
    const activeOrders = orders
      .filter((order) => !/completed|returned|paid|settled|cancelled|expired/.test([order.execution_status, order.settlement_status, order.agency_settlement_status, order.dispatch_status].join('|')))
      .sort((a, b) => parseDateTime(a.order_date, a.start_time) - parseDateTime(b.order_date, b.start_time));
    this.setData({
      serviceOrders: activeOrders.slice(0, 12),
      loading: false
    });
  },

  groupOrdersForWork(orders) {
    const now = new Date();
    const currentOrders = [];
    const upcomingOrders = [];
    const historyOrders = [];
    orders.forEach((order) => {
      const start = parseDateTime(order.order_date, order.start_time);
      const end = orderEndAt(order);
      const done = /completed|returned|paid|settled/.test([order.execution_status, order.settlement_status, order.agency_settlement_status].join('|'));
      if (!done && start <= now && end >= now) {
        currentOrders.push(order);
      } else if (!done && start > now) {
        upcomingOrders.push(order);
      } else {
        historyOrders.push(order);
      }
    });
    return {
      currentOrders: currentOrders.sort((a, b) => String(a.start_time || '').localeCompare(String(b.start_time || ''))),
      upcomingOrders: upcomingOrders.sort((a, b) => parseDateTime(a.order_date, a.start_time) - parseDateTime(b.order_date, b.start_time)).slice(0, 8),
      historyOrders: historyOrders.sort((a, b) => parseDateTime(b.order_date, b.start_time) - parseDateTime(a.order_date, a.start_time)).slice(0, 6)
    };
  },

  onLoginCodeInput(e) {
    const loginCode = String(e.detail.value || '').trim();
    this.setData({ loginCode, resolvedAgencyName: '' });
    if (loginCode.length < 2) return;
    api.resolveAccount(loginCode)
      .then((res) => {
        const agency = res.agency || {};
        this.setData({ resolvedAgencyName: agency.name || '' });
      })
      .catch(() => this.setData({ resolvedAgencyName: '' }));
  },

  onPasswordInput(e) {
    this.setData({ password: e.detail.value });
  },

  login() {
    const loginCode = String(this.data.loginCode || '').trim();
    const password = String(this.data.password || '');
    if (!loginCode || !password) {
      wx.showToast({ title: '请输入登录代码和密码', icon: 'none' });
      return;
    }
    this.setData({ loginLoading: true, message: '' });
    api.login(loginCode, password)
      .then((session) => {
        api.setSession(session);
        wx.showToast({ title: '已登录' });
        this.applySession(session);
        this.setData({
          loginLoading: false,
          password: '',
          resolvedAgencyName: session.agency && session.agency.name ? session.agency.name : this.data.resolvedAgencyName
        });
        this.loadDashboard();
      })
      .catch((err) => {
        this.setData({ loginLoading: false, message: `登录失败：${err.error || err.message || '登录代码或密码不正确'}` });
      });
  },

  logout() {
    api.clearSession();
    wx.showTabBar();
    this.setData({
      session: null,
      roleKind: 'admin',
      roleLabel: '管理',
      isGuide: false,
      isService: false,
      stats: emptyStats(),
      currentOrders: [],
      upcomingOrders: [],
      historyOrders: [],
      serviceOrders: [],
      message: '',
      loginCode: '',
      password: '',
      resolvedAgencyName: ''
    });
    wx.setNavigationBarTitle({ title: '旅行社登录' });
  },

  goPage(e) {
    wx.redirectTo({ url: e.currentTarget.dataset.url });
  },

  goWorkPage(e) {
    wx.redirectTo({ url: e.currentTarget.dataset.url });
  },

  reportNode(e) {
    const label = e.currentTarget.dataset.label;
    wx.showToast({ title: `${label}已记录`, icon: 'none' });
  },

  goSettings() {
    wx.navigateTo({ url: '/package_agency/pages/profile/index' });
  }
});

