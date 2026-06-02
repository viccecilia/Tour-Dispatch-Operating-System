const api = require('../../utils/api');

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'];

const LEGEND = [
  { key: 'draft', label: '未发布' },
  { key: 'listed', label: '发布中' },
  { key: 'claimed', label: '已接单' },
  { key: 'active', label: '进行中' },
  { key: 'done', label: '已完成' },
  { key: 'expired', label: '撤回/流拍' }
];

function isGuide(session) {
  const role = session && session.account ? String(session.account.role || '').toLowerCase() : '';
  return role.indexOf('guide') >= 0 || role.indexOf('导游') >= 0;
}

function ownGuideOrders(session, orders) {
  if (!isGuide(session)) return orders || [];
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

function pad(number) {
  return String(number).padStart(2, '0');
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

function ymd(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function monthText(date) {
  return `${date.getFullYear()}年${pad(date.getMonth() + 1)}月`;
}

function parseDate(value) {
  const text = String(value || today()).slice(0, 10);
  const parsed = new Date(`${text}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? new Date(`${today()}T00:00:00`) : parsed;
}

function addDays(date, days) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
}

function addMonths(date, months) {
  return new Date(date.getFullYear(), date.getMonth() + months, 1);
}

function dateRange(startDate, endDate) {
  const start = parseDate(startDate);
  const end = parseDate(endDate || startDate);
  const safeEnd = end >= start ? end : start;
  const dates = [];
  let cursor = start;
  while (cursor <= safeEnd && dates.length < 32) {
    dates.push(ymd(cursor));
    cursor = addDays(cursor, 1);
  }
  return dates;
}

Page({
  data: {
    weekdays: WEEKDAYS,
    legend: LEGEND,
    monthAnchor: parseDate(today()),
    monthTitle: '',
    selectedDate: today(),
    selectedDateLabel: '',
    isGuide: false,
    orders: [],
    calendarDays: [],
    selectedOrders: [],
    loading: false,
    message: ''
  },

  onShow() {
    const session = api.getSession();
    if (!session) {
      wx.switchTab({ url: '/pages/index/index' });
      return;
    }
    const guideMode = isGuide(session);
    if (guideMode) wx.hideTabBar(); else wx.showTabBar();
    const tabBar = typeof this.getTabBar === 'function' && this.getTabBar();
    if (tabBar) tabBar.setData({ selected: 4 });
    this.setData({ isGuide: guideMode });
    wx.setNavigationBarTitle({
      title: session.agency && session.agency.name ? session.agency.name : '订单日历'
    });
    this.loadCalendar();
  },

  loadCalendar() {
    const session = api.getSession();
    this.setData({ loading: true, message: '' });
    api.orders()
      .then((orders) => {
        const decorated = ownGuideOrders(session, orders).map((item) => this.decorateOrder(item));
        this.setData({ orders: decorated, loading: false });
        this.buildMonth(decorated);
      })
      .catch((err) => {
        this.setData({ loading: false, message: `日历加载失败：${err.error || err.message || '请重新登录或确认接口'}` });
      });
  },

  previousMonth() {
    this.setData({ monthAnchor: addMonths(this.data.monthAnchor, -1) }, () => this.buildMonth(this.data.orders));
  },

  nextMonth() {
    this.setData({ monthAnchor: addMonths(this.data.monthAnchor, 1) }, () => this.buildMonth(this.data.orders));
  },

  backToToday() {
    const current = parseDate(today());
    this.setData({ monthAnchor: current, selectedDate: today() }, () => this.buildMonth(this.data.orders));
  },

  selectDate(e) {
    const date = e.currentTarget.dataset.date;
    if (!date) return;
    this.setData({ selectedDate: date }, () => this.pickSelectedOrders(this.data.orders));
  },

  buildMonth(rows) {
    const anchor = this.data.monthAnchor instanceof Date ? this.data.monthAnchor : parseDate(this.data.monthAnchor);
    const monthStart = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    const firstCell = addDays(monthStart, -monthStart.getDay());
    const month = monthStart.getMonth();
    const days = [];
    for (let index = 0; index < 42; index += 1) {
      const date = addDays(firstCell, index);
      const dateText = ymd(date);
      const dayOrders = this.ordersForDate(rows, dateText);
      days.push({
        date: dateText,
        day: date.getDate(),
        inMonth: date.getMonth() === month,
        isToday: dateText === today(),
        count: dayOrders.length,
        dots: this.statusDots(dayOrders)
      });
    }
    this.setData({
      calendarDays: days,
      monthTitle: monthText(monthStart)
    });
    this.pickSelectedOrders(rows);
  },

  pickSelectedOrders(rows) {
    const selectedOrders = this.ordersForDate(rows, this.data.selectedDate);
    this.setData({
      selectedOrders,
      selectedDateLabel: this.data.selectedDate
    });
  },

  ordersForDate(rows, dateText) {
    return (rows || [])
      .filter((order) => dateRange(order.order_date, order.end_date || order.order_date).indexOf(dateText) >= 0)
      .sort((a, b) => String(a.start_time || '').localeCompare(String(b.start_time || '')));
  },

  statusDots(rows) {
    const counts = rows.reduce((acc, order) => {
      acc[order.statusClass] = (acc[order.statusClass] || 0) + 1;
      return acc;
    }, {});
    return LEGEND
      .filter((item) => counts[item.key])
      .slice(0, 4)
      .map((item) => ({ key: item.key, count: counts[item.key] }));
  },

  decorateOrder(order) {
    const dispatchStatus = order.dispatch_status || '';
    const auctionStatus = order.auction_status || '';
    const executionStatus = order.execution_status || '';
    const settlementStatus = order.settlement_status || order.agency_settlement_status || 'pending';
    const statusKey = this.statusKey(auctionStatus, dispatchStatus, executionStatus, settlementStatus);
    const typeText = this.orderType(order.order_type);
    return {
      ...order,
      typeText,
      statusClass: statusKey,
      statusText: this.statusText(statusKey),
      routeText: `${order.pickup_location || '-'} → ${order.dropoff_location || '-'}`,
      timeText: `${order.order_date || '-'} ${order.start_time || '--:--'}${order.end_time ? `-${order.end_time}` : ''}`
    };
  },

  orderType(value) {
    const text = String(value || '');
    if (text.indexOf('接机') >= 0 || text.indexOf('pickup') >= 0) return '接机';
    if (text.indexOf('送机') >= 0 || text.indexOf('dropoff') >= 0) return '送机';
    if (text.indexOf('airport') >= 0) return '接送机';
    return '包车';
  },

  statusText(key) {
    const item = LEGEND.find((entry) => entry.key === key);
    return item ? item.label : '未发布';
  },

  statusKey(auctionStatus, dispatchStatus, executionStatus, settlementStatus) {
    const combined = [auctionStatus, dispatchStatus, executionStatus, settlementStatus].join('|');
    if (/paid|settled|completed|returned/.test(combined)) return 'done';
    if (/in_service|departed|arrived/.test(combined)) return 'active';
    if (/auction_claimed|claimed|assigned/.test(combined)) return 'claimed';
    if (/auction_listed|listed|bidding/.test(combined)) return 'listed';
    if (/expired|cancelled|withdrawn/.test(combined)) return 'expired';
    return 'draft';
  }
});
