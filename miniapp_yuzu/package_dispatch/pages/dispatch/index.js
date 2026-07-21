const api = require('../../utils/api');

const SAMPLE_TEXT = [
  '5.29 08:00 KIX接机大阪市内 3代 绿450',
  '5.29 10:20 大阪市内-京都市内 包车 3代 1500',
  '5.29 13:30 京都酒店-关西机场 3代 儿童座椅 绿600'
].join('\n');

const DAILY_STORAGE_KEY = 'dispatch_daily_assignment_draft';
const DAILY_PUBLISHED_KEY = 'dispatch_daily_assignment_published';
const DAILY_CONFIRM_QUEUE_KEY = 'dispatch_daily_driver_confirm_queue';
const YUZU_DEV_TENANT_ID = 529;
const HIDDEN_DRIVER_NAMES = [
  '刘明海',
  '劉明海',
  '刘晟',
  '劉晟',
  '王爽',
  '楊増福',
  '滝澤雅禾',
  '富塚紀子',
  '陳鈴',
  '唐洋洲',
  '谷口張延瑾',
  '谷口延瑾',
  '福田弘一'
];
const DAILY_EXAMPLE_TEXT = `林泽群 3893
1.31 10:00 京都单送关西酒店 3代 绿800
1.31 12:30 关西接机大阪 3代 绿470
1.31 18:20 关西接机大阪 3代 450

姜小涛
1.31 13:00 京都送机关西 3代 司机收24000日元 绿800 指定阿尔法
1.31 18:20 关西接机大阪 3代 450
1.31 21:40 关西接机大阪 3代 绿450`;

const AIRPORT_WORDS = ['kix', '机场', '空港', '关西', '关空', '羽田', '成田', '伊丹', '神户机场'];
const DAILY_ORDER_KEYWORDS = ['接机', '送机', '包车', '单送', '日游', '往返', '机场', '关西', '伊丹', '神户'];
const DAILY_VEHICLE_KEYWORDS = ['10座', '3代', 'Hiace', 'Hiyace', 'Alphard', '阿尔法', '海狮', 'Coaster', '儿童座椅'];
const PHONE_REGION_MAP = [
  [/^\+86\b/, '中国'],
  [/^\+81\b/, '日本'],
  [/^\+852\b/, '香港'],
  [/^\+853\b/, '澳门'],
  [/^\+886\b/, '台湾'],
  [/^\+971\b/, '阿联酋'],
  [/^\+60\b/, '马来西亚'],
  [/^\+91\b/, '印度'],
  [/^\+65\b/, '新加坡'],
  [/^\+66\b/, '泰国'],
  [/^\+82\b/, '韩国'],
  [/^\+1\b/, '美国/加拿大'],
  [/^\+44\b/, '英国'],
  [/^\+33\b/, '法国'],
  [/^\+49\b/, '德国']
];
const DAILY_DRIVER_ALIAS_MAP = {
  周传波: '周伝波',
  周傳波: '周伝波',
  胡东锴: '胡東鍇',
  胡東锴: '胡東鍇',
  吕云龙: '呂雲龍',
  呂云龍: '呂雲龍',
  王启超: '王啓超',
  万强: '万強',
  白石贤志: '白石賢志',
  先山: '先山武志'
};

function normalizeHiddenDriverName(value) {
  return String(value || '').replace(/[\s\u3000()（）·・]/g, '');
}

function isHiddenDispatchDriver(driver) {
  const text = [
    driver && driver.name,
    driver && driver.driver_name,
    driver && driver.display_name,
    driver && driver.title,
    driver && driver['運転手名']
  ].filter(Boolean).join('');
  const normalized = normalizeHiddenDriverName(text);
  if (!normalized) return false;
  return HIDDEN_DRIVER_NAMES.some((name) => {
    const target = normalizeHiddenDriverName(name);
    return normalized === target || normalized.indexOf(target) >= 0 || target.indexOf(normalized) >= 0;
  });
}

function pad2(value) {
  return String(value).padStart(2, '0');
}

function plateShortCode(value) {
  const digits = String(value || '').replace(/\D/g, '');
  return digits.slice(-4).replace(/^0+(?=\d)/, '');
}

function buildDailyId(prefix) {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 100000)}`;
}

function hasDailyOrderSignal(text) {
  return DAILY_ORDER_KEYWORDS.some((key) => text.indexOf(key) !== -1) ||
    /\d{1,2}[./-]\d{1,2}/.test(text) ||
    /\d{1,2}[:：]\d{2}/.test(text);
}

function normalizeDailyDate(raw) {
  if (!raw) return '';
  const match = String(raw).match(/(\d{1,2})[./-](\d{1,2})/);
  if (!match) return '';
  const year = new Date().getFullYear();
  return `${year}-${pad2(match[1])}-${pad2(match[2])}`;
}

function normalizeDailyTime(raw) {
  if (!raw) return '';
  const match = String(raw).match(/(\d{1,2})[:：](\d{2})/);
  if (!match) return '';
  return `${pad2(match[1])}:${match[2]}`;
}

function detectDailyType(text) {
  if (/接机|空港迎え|机场接/.test(text)) return '接机';
  if (/送机|空港行き|机场送/.test(text)) return '送机';
  if (/包车|包車|日游|一日游/.test(text)) return '包车';
  if (/往返/.test(text)) return '往返';
  if (/单送|單送|片道/.test(text)) return '单送';
  return '待确认';
}

function detectDailyVehicle(text) {
  const lower = text.toLowerCase();
  const tenSeat = text.match(/10\s*座(?:\s*[×x*]\s*\d+)?/i);
  if (tenSeat) return tenSeat[0].replace(/\s+/g, '');
  const threeGen = text.match(/3\s*代(?:\s*[×x*]\s*\d+)?/i);
  if (threeGen) return threeGen[0].replace(/\s+/g, '');
  if (lower.indexOf('hiace') !== -1 || text.indexOf('海狮') !== -1) return '10座';
  if (lower.indexOf('alphard') !== -1 || text.indexOf('阿尔法') !== -1) return '3代';
  if (text.indexOf('Coaster') !== -1 || text.indexOf('中巴') !== -1) return 'Coaster';
  return '';
}

function detectDailyPrice(text) {
  const direct = text.match(/司机收\s*(\d{4,6})\s*日?元?/);
  if (direct) return direct[1];
  const amountPattern = '([0-9]{3,6}(?:\\+[0-9]{3,6})?(?:\\s*[×x*]\\s*[0-9]+|\\s*[*])?)';
  const green = text.match(new RegExp(`绿牌?\\s*[（(]?\\s*${amountPattern}`));
  if (green) return green[1];
  const paren = text.match(new RegExp(`[（(]\\s*${amountPattern}\\s*[）)]`));
  if (paren) return paren[1];
  const tail = text.match(new RegExp(`(?:^|\\s)${amountPattern}\\s*(?:取消|作废)?\\s*$`));
  return tail ? tail[1].replace(/\s+/g, '') : '';
}

function cleanupDailyRoute(text) {
  let route = text;
  route = route.replace(/\d{1,2}[./-]\d{1,2}/g, '');
  route = route.replace(/\d{1,2}[:：]\d{2}/g, '');
  route = route.replace(/司机收\s*\d{3,6}\s*日?元?/g, '');
  route = route.replace(/绿牌?\s*[（(]?\s*\d{3,6}(?:\+\d{3,6})?(?:\s*[×x*]\s*\d+|\s*[*])?\s*[）)]?/g, '');
  route = route.replace(/[（(]\s*\d{3,6}(?:\+\d{3,6})?(?:\s*[×x*]\s*\d+|\s*[*])?\s*[）)]/g, '');
  route = route.replace(/(?:^|\s)\d{3,6}(?:\+\d{3,6})?(?:\s*[×x*]\s*\d+|\s*[*])?\s*(?:取消|作废)?\s*$/g, '');
  route = route.replace(/10\s*座(?:\s*[×x*]\s*\d+)?/gi, '');
  route = route.replace(/3\s*代(?:\s*[×x*]\s*\d+)?/gi, '');
  DAILY_VEHICLE_KEYWORDS.forEach((word) => {
    route = route.replace(new RegExp(word, 'gi'), '');
  });
  route = route.replace(/绿|指定|取消|作废/g, '');
  route = route.replace(/\s+/g, ' ').trim();
  return route || text.trim();
}

function parseDailyOrderLine(line) {
  const dateMatch = line.match(/\d{1,2}[./-]\d{1,2}/);
  const timeMatch = line.match(/\d{1,2}[:：]\d{2}/);
  return {
    id: buildDailyId('order'),
    date: normalizeDailyDate(dateMatch ? dateMatch[0] : ''),
    time: normalizeDailyTime(timeMatch ? timeMatch[0] : ''),
    type: detectDailyType(line),
    vehicleType: detectDailyVehicle(line),
    route: cleanupDailyRoute(line),
    price: detectDailyPrice(line),
    status: /取消|作废/.test(line) ? '作废' : '待发布',
    remark: line.trim()
  };
}

function parseDailyDriverHeader(line) {
  const trimmed = line.trim();
  const codeMatch = trimmed.match(/([A-Za-z]?\d{3,4})\s*$/);
  const vehicleCode = codeMatch ? codeMatch[1] : '';
  const driverName = vehicleCode ? trimmed.slice(0, trimmed.length - vehicleCode.length).replace(/[-－—–·\s]+$/g, '').trim() : trimmed;
  return {
    id: buildDailyId('driver'),
    driverName: driverName || '未命名司机',
    vehicleCode,
    orders: []
  };
}

function splitDailyDriverVehicle(value) {
  const text = String(value || '').trim();
  if (!text) return { driverName: '', vehicleCode: '' };
  const explicit = text.match(/^(.+?)[-－—–]\s*([A-Za-z]?\d{3,4})$/);
  if (explicit) {
    return {
      driverName: explicit[1].trim(),
      vehicleCode: explicit[2].trim()
    };
  }
  const tail = text.match(/^(.+?)\s+([A-Za-z]?\d{3,4})$/);
  if (tail) {
    return {
      driverName: tail[1].trim(),
      vehicleCode: tail[2].trim()
    };
  }
  return { driverName: text, vehicleCode: '' };
}

function normalizeDailyGroups(groups) {
  return (groups || []).map((group) => {
    const orders = (group.orders || []).map((order, index) => ({
      ...order,
      id: order.id || buildDailyId('order'),
      displayIndex: index + 1
    }));
    const serviceDate = group.serviceDate || ((orders.find((order) => order.date) || {}).date) || '';
    const driverName = group.driverName || '未命名司机';
    const vehicleCode = group.vehicleCode || '';
    return {
      ...group,
      id: group.id || buildDailyId('driver'),
      driverName,
      vehicleCode,
      driverVehicleLabel: vehicleCode ? `${driverName}-${vehicleCode}` : driverName,
      serviceDate,
      orders
    };
  });
}

function calcDailyStats(groups) {
  const drivers = groups.length;
  const orders = groups.reduce((sum, group) => sum + (group.orders || []).length, 0);
  const voided = groups.reduce((sum, group) => {
    return sum + (group.orders || []).filter((order) => order.status === '作废').length;
  }, 0);
  const unpublished = groups.reduce((sum, group) => {
    return sum + (group.orders || []).filter((order) => order.status !== '已发布' && order.status !== '作废').length;
  }, 0);
  return { drivers, orders, unpublished, voided };
}

function shouldPublishDailyOrder(order) {
  return order && order.status !== '作废' && !order.backendOrderId;
}

function blankDailyOverview() {
  return {
    assignedDrivers: 0,
    assignedOrders: 0,
    idleDrivers: 0,
    idleVehicles: 0,
    missingDriverGroups: [],
    missingVehicleGroups: [],
    driverNav: []
  };
}

function parseDailyGroups(sourceText) {
  const lines = String(sourceText || '').split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const groups = [];
  let current = null;
  lines.forEach((line) => {
    const orderLike = hasDailyOrderSignal(line) &&
      (/\d{1,2}[./-]\d{1,2}/.test(line) ||
        /\d{1,2}[:：]\d{2}/.test(line) ||
        DAILY_ORDER_KEYWORDS.some((key) => line.indexOf(key) !== -1));
    if (!orderLike) {
      current = parseDailyDriverHeader(line);
      groups.push(current);
      return;
    }
    if (!current) {
      current = parseDailyDriverHeader('未分组司机');
      groups.push(current);
    }
    current.orders.push(parseDailyOrderLine(line));
  });
  return normalizeDailyGroups(groups.filter((group) => group.driverName || (group.orders && group.orders.length)));
}

function isIsoDate(value) {
  return /^\d{4}-\d{2}-\d{2}$/.test(String(value || '').trim());
}

function normalizeTimeText(value) {
  const text = String(value || '').trim().replace(/[：]/g, ':');
  if (!text) return '';
  const match = text.match(/^(\d{1,2}):(\d{2})$/);
  if (!match) return text;
  return `${String(Number(match[1])).padStart(2, '0')}:${match[2]}`;
}

function addHoursToDateTime(dateText, timeText, hours) {
  if (!isIsoDate(dateText)) return { end_date: dateText, end_time: normalizeTimeText(timeText) };
  const normalizedTime = normalizeTimeText(timeText);
  if (!/^\d{2}:\d{2}$/.test(normalizedTime)) return { end_date: dateText, end_time: normalizedTime };
  const dt = new Date(`${dateText}T${normalizedTime}:00`);
  if (Number.isNaN(dt.getTime())) return { end_date: dateText, end_time: normalizedTime };
  dt.setHours(dt.getHours() + hours);
  return {
    end_date: `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`,
    end_time: `${String(dt.getHours()).padStart(2, '0')}:${String(dt.getMinutes()).padStart(2, '0')}`
  };
}

function normalizeDailyMatchValue(value) {
  return String(value || '')
    .replace(/[\s\-－—–·・／/()（）]/g, '')
    .toLowerCase();
}

function dailyDriverNameCandidates(name) {
  const raw = String(name || '').trim();
  return [raw, DAILY_DRIVER_ALIAS_MAP[raw]]
    .filter(Boolean)
    .map((item) => normalizeDailyMatchValue(item));
}

function getDailyDriverName(driver) {
  return String(driver && (driver.displayName || driver.display_name || driver.driver_name || driver.name || driver.driver_code) || '').trim();
}

function matchDailyDriver(drivers, driverName) {
  const candidates = dailyDriverNameCandidates(driverName);
  if (!candidates.length) return null;
  return (drivers || []).find((driver) => {
    const name = normalizeDailyMatchValue(getDailyDriverName(driver));
    return candidates.some((candidate) => name === candidate || name.indexOf(candidate) >= 0 || candidate.indexOf(name) >= 0);
  }) || null;
}

function matchDailyVehicle(vehicles, vehicleCode) {
  const code = normalizeDailyMatchValue(vehicleCode);
  if (!code) return null;
  return (vehicles || []).find((vehicle) => {
    const values = [
      vehicle && vehicle.plate_short_code,
      vehicle && vehicle.shortPlate,
      vehicle && vehicle.plate_number,
      vehicle && vehicle.license_plate,
      vehicle && vehicle.plateNo,
      vehicle && vehicle.vehicle_code,
      vehicle && vehicle.code
    ].map((item) => normalizeDailyMatchValue(item)).filter(Boolean);
    const plateTail = normalizeDailyMatchValue(plateShortCode(vehicle && vehicle.plate_number));
    if (plateTail) values.push(plateTail);
    const whole = normalizeDailyMatchValue(JSON.stringify(vehicle || {}));
    return values.some((value) => value === code || value.indexOf(code) >= 0) || whole.indexOf(code) >= 0;
  }) || null;
}

function summarizeDailyVehicleSamples(vehicles) {
  const samples = (vehicles || []).slice(0, 8).map((vehicle) => (
    vehicle.plate_short_code ||
    vehicle.shortPlate ||
    plateShortCode(vehicle.plate_number) ||
    vehicle.plate_number ||
    vehicle.id
  )).filter(Boolean);
  return samples.length ? samples.join(',') : '空';
}

function splitDailyRouteForOrder(routeText) {
  const route = String(routeText || '').trim();
  const markers = ['接机', '送机', '单送'];
  for (let i = 0; i < markers.length; i += 1) {
    const marker = markers[i];
    const index = route.indexOf(marker);
    if (index > 0) {
      return {
        pickup_location: route.slice(0, index).trim() || route,
        dropoff_location: route.slice(index + marker.length).trim() || marker
      };
    }
  }
  return {
    pickup_location: route || '待确认',
    dropoff_location: ''
  };
}

function dailyPriceToNumber(value) {
  const text = String(value || '').replace(/\s+/g, '');
  const multiply = text.match(/^(\d+(?:\+\d+)?)\*(\d+)$/);
  if (multiply) {
    const base = multiply[1].split('+').reduce((sum, item) => sum + Number(item || 0), 0);
    return base * Number(multiply[2]);
  }
  const plus = text.match(/^(\d+(?:\+\d+)+)\*?$/);
  if (plus) return plus[1].split('+').reduce((sum, item) => sum + Number(item || 0), 0);
  const direct = text.match(/\d+/);
  return direct ? Number(direct[0]) : 0;
}

function buildDailyOrderText(order) {
  const parts = [order.date, order.time, order.route, order.vehicleType, order.price ? `绿${order.price}` : '']
    .filter(Boolean);
  return order.remark || parts.join(' ');
}

function buildDailyOrderPayload(order) {
  const end = addHoursToDateTime(order.date, order.time, order.type === '包车' ? 8 : 2);
  const route = splitDailyRouteForOrder(order.route);
  return {
    order_date: order.date || '',
    end_date: end.end_date || order.date || '',
    start_time: normalizeTimeText(order.time || ''),
    end_time: end.end_time || normalizeTimeText(order.time || ''),
    order_type: order.type || '待确认',
    vehicle_type: order.vehicleType || '',
    pickup_location: route.pickup_location,
    dropoff_location: route.dropoff_location,
    price: dailyPriceToNumber(order.price),
    remark: order.remark || buildDailyOrderText(order),
    fee_remark: order.price ? `日配价格 ${order.price}` : '',
    source_channel: 'daily_assignment'
  };
}

function normalizeDailyRouteValue(value) {
  return normalizeDailyMatchValue(value).replace(/t1|t2|terminal/g, '');
}

function findExistingDailyAssignment(order, item, assignments) {
  const payload = buildDailyOrderPayload(order);
  const pickup = normalizeDailyRouteValue(payload.pickup_location);
  const dropoff = normalizeDailyRouteValue(payload.dropoff_location);
  return (assignments || []).find((assignment) => {
    if (Number(assignment.driver_id) !== Number(item.driver.id)) return false;
    if (Number(assignment.vehicle_id) !== Number(item.vehicle.id)) return false;
    if (String(assignment.order_date || '') !== String(payload.order_date || '')) return false;
    if (normalizeTimeText(assignment.start_time || '') !== normalizeTimeText(payload.start_time || '')) return false;
    const activePickup = normalizeDailyRouteValue(assignment.pickup_location || '');
    const activeDropoff = normalizeDailyRouteValue(assignment.dropoff_location || '');
    const pickupMatch = !pickup || !activePickup || activePickup.indexOf(pickup) >= 0 || pickup.indexOf(activePickup) >= 0;
    const dropoffMatch = !dropoff || !activeDropoff || activeDropoff.indexOf(dropoff) >= 0 || dropoff.indexOf(activeDropoff) >= 0;
    return pickupMatch && dropoffMatch;
  }) || null;
}

function mergeDailyResources(primary, fallback) {
  const seen = {};
  return []
    .concat(primary || [], fallback || [])
    .filter((item) => item && item.id)
    .filter((item) => {
      const key = String(item.id);
      if (seen[key]) return false;
      seen[key] = true;
      return true;
    });
}

function normalizeResourceStatus(value) {
  return String(value || '').trim().toLowerCase();
}

function isVehicleUsable(vehicle) {
  const status = normalizeResourceStatus(vehicle && vehicle.status);
  if (!status) return true;
  return ['available', 'idle', 'ready', '空闲', '可用'].indexOf(status) >= 0;
}

function isDriverUsable(driver) {
  const status = normalizeResourceStatus(driver && driver.status);
  if (!status) return true;
  return ['available', 'idle', 'ready', '空闲', '可用'].indexOf(status) >= 0;
}

function isAirportTransferOrder(orderType) {
  const text = String(orderType || '').trim();
  return text === '接机' || text === '送机';
}

function mergeSingleRemark(draft) {
  return [draft && draft.fee_remark, draft && draft.remark]
    .map((item) => String(item || '').trim())
    .filter(Boolean)
    .filter((item, index, list) => list.indexOf(item) === index)
    .join('\n');
}

function blankSingleForm() {
  return {
    order_date: '',
    end_date: '',
    start_time: '',
    end_time: '',
    order_type: '包车',
    vehicle_type: 'A-3',
    pickup_location: '',
    dropoff_location: '',
    agency_name: '',
    guest_name: '',
    guest_contact: '',
    passenger_count: '',
    luggage_count: '',
    price: '',
    remark: ''
  };
}

Page({
  data: {
    importOpen: true,
    importMode: 'daily',
    importText: SAMPLE_TEXT,
    dailySourceText: '',
    dailyGroups: [],
    dailyStats: calcDailyStats([]),
    dailyOverview: blankDailyOverview(),
    dailyMessage: '',
    singleParsed: false,
    singleDraftId: '',
    singleForm: blankSingleForm(),
    pendingRows: [],
    charterRows: [],
    pickupRows: [],
    dropoffRows: [],
    drivers: [],
    vehicles: [],
    assignments: [],
    publishedRows: [],
    publishedEditOpen: false,
    publishedEditOrderId: '',
    publishedEditAssignmentId: '',
    publishedEditTitle: '',
    publishedEditForm: {},
    publishedHistoryRows: [],
    publishedHistoryLoading: false,
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
    helpTip: null,
    canAuction: false,
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
    api.syncEnvironmentBaseUrl();
    api.setActiveTab('/package_dispatch/pages/dispatch/index');
    this.setData({ canAuction: api.canAccess('auction') });
    this.restoreDailyDraft();
    this.refreshTabBar();
    if (!api.canAccess('dispatch')) {
      wx.showToast({ title: '当前账号没有派车权限', icon: 'none' });
      wx.reLaunch({ url: '/package_dispatch/pages/home/index' });
      return;
    }
    this.loadAll();
  },

  ensureYuzuDevTenant() {
    const tenantId = this.currentTenantId();
    if (!api.isLocalBaseUrl || !api.isLocalBaseUrl() || !tenantId || tenantId === YUZU_DEV_TENANT_ID) return true;
    this.setData({
      loading: false,
      conflictText: `当前登录租户是 ${tenantId}，不是 yuzu 车公司租户 ${YUZU_DEV_TENANT_ID}。请退出后登录 yuzu_dispatch_100 / Test2026!。`,
      dailyMessage: `当前账号不属于 yuzu 车公司，请重新登录 yuzu_dispatch_100。`
    });
    wx.showModal({
      title: '账号租户不匹配',
      content: `当前租户 ${tenantId} 没有 yuzu 车辆。请重新登录 yuzu_dispatch_100 / Test2026!。`,
      confirmText: '去登录',
      cancelText: '先不',
      success: (res) => {
        if (res.confirm) {
          api.clearSession({ manual: true });
          wx.reLaunch({ url: '/package_dispatch/pages/home/index' });
        }
      }
    });
    return false;
  },

  refreshTabBar() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().refresh();
    }
  },

  openImport(e) {
    const mode = (e && e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.mode) || 'batch';
    this.setData({
      importOpen: true,
      importMode: mode
    });
  },

  toggleCharter() {
    this.setData({ charterCollapsed: !this.data.charterCollapsed });
  },

  onImportText(e) {
    this.setData({ importText: e.detail.value });
  },

  updateDailyGroups(groups, dailyMessage) {
    const next = normalizeDailyGroups(groups);
    const patch = {
      dailyGroups: next,
      dailyStats: calcDailyStats(next),
      dailyOverview: this.buildDailyOverview(next)
    };
    if (typeof dailyMessage === 'string') patch.dailyMessage = dailyMessage;
    this.setData(patch);
  },

  updateDailyOverview(resources = {}) {
    this.setData({ dailyOverview: this.buildDailyOverview(this.data.dailyGroups, resources) });
  },

  buildDailyOverview(groups = [], resources = {}) {
    const normalized = normalizeDailyGroups(groups);
    const currentDrivers = resources.drivers || this.data.drivers || [];
    const currentVehicles = resources.vehicles || this.data.vehicles || [];
    const missingDriverGroups = [];
    const missingVehicleGroups = [];
    const driverNav = [];
    normalized.forEach((group, index) => {
      const driverName = String(group.driverName || '').trim();
      const vehicleCode = String(group.vehicleCode || '').trim();
      const orderCount = (group.orders || []).filter((order) => order.status !== '作废').length;
      if (!driverName || driverName === '未命名司机' || driverName === '未分组司机') {
        missingDriverGroups.push({ index, label: `第 ${index + 1} 组`, orderCount });
      } else {
        driverNav.push({ index, name: driverName, orderCount, vehicleCode: vehicleCode || '未填车辆' });
      }
      if (!vehicleCode) {
        missingVehicleGroups.push({ index, label: driverName || `第 ${index + 1} 组`, orderCount });
      }
    });
    const assignedOrders = normalized.reduce((sum, group) => {
      return sum + (group.orders || []).filter((order) => order.status !== '作废').length;
    }, 0);
    const filledVehicleCodes = new Set(
      normalized
        .map((group) => String(group.vehicleCode || '').trim())
        .filter(Boolean)
    );
    const idleVehicleCount = currentVehicles.filter((vehicle) => isVehicleUsable(vehicle) && !vehicle.disabled).length;
    return {
      assignedDrivers: driverNav.length,
      assignedOrders,
      idleDrivers: currentDrivers.filter((driver) => isDriverUsable(driver) && !driver.disabled).length,
      idleVehicles: currentVehicles.length ? idleVehicleCount : filledVehicleCodes.size,
      missingDriverGroups,
      missingVehicleGroups,
      driverNav
    };
  },

  restoreDailyDraft() {
    const draft = wx.getStorageSync(DAILY_STORAGE_KEY);
    if (!draft || (!draft.sourceText && !draft.groups)) return;
    this.setData({ dailySourceText: draft.sourceText || '' });
    this.updateDailyGroups(draft.groups || [], '已恢复上次保存的日配草稿。');
  },

  onDailySourceInput(e) {
    this.setData({ dailySourceText: e.detail.value });
  },

  fillDailyExample() {
    this.setData({ dailySourceText: DAILY_EXAMPLE_TEXT, dailyMessage: '已填入示例，可以直接解析。' });
  },

  clearDailySource() {
    this.setData({
      dailySourceText: '',
      dailyGroups: [],
      dailyStats: calcDailyStats([]),
      dailyOverview: blankDailyOverview(),
      dailyMessage: '已清空。'
    });
  },

  focusDailyGroup(e) {
    const index = Number(e.currentTarget.dataset.groupIndex);
    if (Number.isNaN(index)) return;
    wx.pageScrollTo({
      selector: `#daily-group-${index}`,
      duration: 240,
      offsetTop: 120
    });
  },

  parseDailyText() {
    const text = String(this.data.dailySourceText || '').trim();
    if (!text) {
      wx.showToast({ title: '请先粘贴日配文本', icon: 'none' });
      return;
    }
    const groups = parseDailyGroups(text);
    this.updateDailyGroups(groups, `已解析 ${groups.length} 名司机、${calcDailyStats(groups).orders} 单。`);
  },

  onDailyGroupInput(e) {
    const index = Number(e.currentTarget.dataset.groupIndex);
    const field = e.currentTarget.dataset.key;
    const groups = normalizeDailyGroups(this.data.dailyGroups);
    if (!groups[index] || !field) return;
    groups[index][field] = e.detail.value;
    this.updateDailyGroups(groups);
  },

  onDailyDriverVehicleInput(e) {
    const index = Number(e.currentTarget.dataset.groupIndex);
    const groups = normalizeDailyGroups(this.data.dailyGroups);
    if (!groups[index]) return;
    const parsed = splitDailyDriverVehicle(e.detail.value);
    groups[index].driverName = parsed.driverName;
    groups[index].vehicleCode = parsed.vehicleCode;
    this.updateDailyGroups(groups);
  },

  onDailyOrderInput(e) {
    const groupIndex = Number(e.currentTarget.dataset.groupIndex);
    const orderIndex = Number(e.currentTarget.dataset.orderIndex);
    const field = e.currentTarget.dataset.key;
    const groups = normalizeDailyGroups(this.data.dailyGroups);
    if (!groups[groupIndex] || !groups[groupIndex].orders[orderIndex] || !field) return;
    groups[groupIndex].orders[orderIndex][field] = e.detail.value;
    this.updateDailyGroups(groups);
  },

  addDailyGroup() {
    const groups = normalizeDailyGroups(this.data.dailyGroups);
    groups.push(parseDailyDriverHeader('未命名司机'));
    this.updateDailyGroups(groups, '已新增司机分组。');
  },

  removeDailyGroup(e) {
    const index = Number(e.currentTarget.dataset.groupIndex);
    const groups = normalizeDailyGroups(this.data.dailyGroups);
    if (!groups[index]) return;
    groups.splice(index, 1);
    this.updateDailyGroups(groups, '已删除司机分组。');
  },

  addDailyOrder(e) {
    const groupIndex = Number(e.currentTarget.dataset.groupIndex);
    const groups = normalizeDailyGroups(this.data.dailyGroups);
    if (!groups[groupIndex]) return;
    groups[groupIndex].orders.push(parseDailyOrderLine(''));
    this.updateDailyGroups(groups, '已新增订单。');
  },

  removeDailyOrder(e) {
    const groupIndex = Number(e.currentTarget.dataset.groupIndex);
    const orderIndex = Number(e.currentTarget.dataset.orderIndex);
    const groups = normalizeDailyGroups(this.data.dailyGroups);
    if (!groups[groupIndex] || !groups[groupIndex].orders[orderIndex]) return;
    groups[groupIndex].orders.splice(orderIndex, 1);
    this.updateDailyGroups(groups, '已删除订单。');
  },

  saveDailyDraft() {
    const draft = {
      sourceText: this.data.dailySourceText,
      groups: normalizeDailyGroups(this.data.dailyGroups),
      savedAt: new Date().toISOString()
    };
    wx.setStorageSync(DAILY_STORAGE_KEY, draft);
    this.setData({ dailyMessage: '日配草稿已保存。' });
    wx.showToast({ title: '已保存草稿', icon: 'success' });
  },

  loadDailyPublishResources() {
    return Promise.all([
      api.drivers(),
      api.vehicles(),
      api.assignments().catch(() => ({ assignments: [] }))
    ]).then(([driversRes, vehiclesRes, assignmentsRes]) => ({
      drivers: mergeDailyResources((driversRes && driversRes.drivers) || [], this.data.drivers)
        .filter((driver) => !isHiddenDispatchDriver(driver)),
      vehicles: mergeDailyResources((vehiclesRes && vehiclesRes.vehicles) || [], this.data.vehicles),
      assignments: (assignmentsRes && assignmentsRes.assignments) || this.data.assignments || []
    }));
  },

  validateDailyPublishPlan(groups, resources) {
    const errors = [];
    const vehicleSampleText = summarizeDailyVehicleSamples(resources.vehicles);
    const requestedVehicleCodes = normalizeDailyGroups(groups)
      .map((group) => group.vehicleCode)
      .filter(Boolean)
      .join(',');
    console.log('[daily publish resources]', {
      drivers: resources.drivers.length,
      vehicles: resources.vehicles.length,
      vehicleSamples: vehicleSampleText,
      requestedVehicleCodes
    });
    const plan = normalizeDailyGroups(groups)
      .map((group, groupIndex) => {
        const orders = (group.orders || []).filter((order) => shouldPublishDailyOrder(order));
        const driver = matchDailyDriver(resources.drivers, group.driverName);
        const vehicle = matchDailyVehicle(resources.vehicles, group.vehicleCode);
        if (!orders.length) return null;
        if (!driver) errors.push(`${group.driverName || `第 ${groupIndex + 1} 组`} 未匹配司机账号`);
        if (!vehicle) errors.push(`${group.driverName || `第 ${groupIndex + 1} 组`} 未匹配车辆 ${group.vehicleCode || '未填尾号'}`);
        return { groupIndex, group, orders, driver, vehicle, assignments: resources.assignments || [] };
      })
      .filter(Boolean);
    if (errors.length) {
      errors.push(`当前车辆列表 ${resources.vehicles.length} 台，样本 ${vehicleSampleText}`);
    }
    return { plan, errors };
  },

  createDailyBackendOrders(item) {
    const text = item.orders.map((order) => buildDailyOrderText(order)).join('\n');
    return api.parseText(text, true)
      .then((res) => {
        const drafts = (res && res.drafts) || [];
        if (drafts.length < item.orders.length) {
          throw new Error(`${item.group.driverName} 解析只生成 ${drafts.length}/${item.orders.length} 单`);
        }
        return item.orders.reduce((chain, order, index) => {
          return chain.then((orderIds) => {
            const draft = drafts[index];
            const draftId = draft && draft.id;
            if (!draftId) throw new Error(`${item.group.driverName} 第 ${index + 1} 单草稿缺失`);
            return api.updateDraft(draftId, buildDailyOrderPayload(order))
              .then(() => api.confirmDraft(draftId))
              .then((confirmed) => {
                const orderId = confirmed && (confirmed.order_id || (confirmed.order && confirmed.order.id) || confirmed.id);
                if (!orderId) throw new Error(`${item.group.driverName} 第 ${index + 1} 单确认失败`);
                return orderIds.concat(Number(orderId));
              });
          });
        }, Promise.resolve([]));
      });
  },

  publishDailyGroupToBackend(item) {
    const orderedOrderIds = [];
    const missingOrders = [];
    const missingIndexes = [];
    item.orders.forEach((order) => {
      const existing = findExistingDailyAssignment(order, item, item.assignments);
      const orderId = existing && (existing.order_id || existing.id);
      if (orderId) {
        orderedOrderIds.push(Number(orderId));
      } else {
        orderedOrderIds.push(null);
        missingIndexes.push(orderedOrderIds.length - 1);
        missingOrders.push(order);
      }
    });
    if (!missingOrders.length) {
      return Promise.resolve({
        groupIndex: item.groupIndex,
        orderIds: orderedOrderIds,
        driverId: Number(item.driver.id),
        vehicleId: Number(item.vehicle.id),
        reused: true
      });
    }
    return this.createDailyBackendOrders({ ...item, orders: missingOrders })
      .then((orderIds) => api.assignOrders({
        order_ids: orderIds,
        driver_id: Number(item.driver.id),
        vehicle_id: Number(item.vehicle.id)
      }).then((res) => {
        if (res && res.success === false) {
          const message = this.formatConflicts(res.conflicts || []) || `${item.group.driverName} 存在时间冲突`;
          throw new Error(message);
        }
        orderIds.forEach((orderId, index) => {
          orderedOrderIds[missingIndexes[index]] = Number(orderId);
        });
        return {
          groupIndex: item.groupIndex,
          orderIds: orderedOrderIds.filter(Boolean),
          driverId: Number(item.driver.id),
          vehicleId: Number(item.vehicle.id)
        };
      }));
  },

  formatDailyPublishError(err) {
    if (!err) return '发送失败，请检查后端连接。';
    if (err.message) return err.message;
    if (err.error === 'network_timeout') return '后端请求超时，请稍后重试。';
    if (err.error === 'network_failed') return '连接后端失败，请确认 API 已启动。';
    if (typeof err === 'string') return err;
    return '发送失败，请检查后端连接。';
  },

  publishDailyAssignments() {
    if (!this.ensureYuzuDevTenant()) return;
    const groups = normalizeDailyGroups(this.data.dailyGroups);
    const orderCount = groups.reduce((sum, group) => {
      return sum + (group.orders || []).filter((order) => shouldPublishDailyOrder(order)).length;
    }, 0);
    if (!orderCount) {
      wx.showToast({ title: '没有待发布订单', icon: 'none' });
      return;
    }
    this.setData({
      loading: true,
      dailyMessage: '正在创建订单并发送司机确认...',
      conflictText: ''
    });
    this.loadDailyPublishResources()
      .then((resources) => {
        const result = this.validateDailyPublishPlan(groups, resources);
        if (result.errors.length) {
          const mainErrors = result.errors.slice(0, 4);
          const diagnostic = result.errors[result.errors.length - 1];
          throw new Error(mainErrors.concat(diagnostic).join('；'));
        }
        return result.plan.reduce((chain, item) => {
          return chain.then((published) => this.publishDailyGroupToBackend(item).then((record) => published.concat(record)));
        }, Promise.resolve([]));
      })
      .then((publishedRecords) => {
        const publishedByGroup = {};
        publishedRecords.forEach((item) => {
          publishedByGroup[item.groupIndex] = (item.orderIds || []).slice();
        });
        const publishedGroups = groups.map((group, index) => ({
          ...group,
          orders: group.orders.map((order) => {
            if (order.status === '作废' || order.backendOrderId) return order;
            const backendOrderId = (publishedByGroup[index] || []).shift();
            return backendOrderId ? { ...order, status: '已发布', backendOrderId } : order;
          })
        }));
        const payload = {
          sourceText: this.data.dailySourceText,
          groups: normalizeDailyGroups(publishedGroups),
          backendPublished: publishedRecords,
          publishedAt: new Date().toISOString(),
          overview: this.buildDailyOverview(publishedGroups)
        };
        wx.setStorageSync(DAILY_PUBLISHED_KEY, payload);
        wx.setStorageSync(DAILY_STORAGE_KEY, payload);
        wx.setStorageSync(DAILY_CONFIRM_QUEUE_KEY, payload);
        this.updateDailyGroups(payload.groups, `已发送 ${publishedRecords.length} 名司机、${orderCount} 单，司机端刷新后可见。`);
        this.setData({ loading: false });
        wx.showToast({ title: '已发送确认', icon: 'success' });
        this.loadAll();
      })
      .catch((err) => {
        const message = this.formatDailyPublishError(err);
        this.setData({
          loading: false,
          dailyMessage: message,
          conflictText: message
        });
        wx.showToast({ title: '发送失败', icon: 'none' });
      });
  },

  onSingleField(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [`singleForm.${field}`]: e.detail.value });
  },

  noop() {},

  showHelp(e) {
    const type = e.currentTarget.dataset.type;
    const contentMap = {
      hero: '粘贴订单文本后后台解析，确认内容后选择司机和车辆派单，也可以把暂时无法执行的订单放入大厅。',
      import: '支持微信、LINE 等文本批量导入。解析后可以在卡片中双击修改订单字段。',
      charter: '包车信息较多，横向占满显示。双击订单可以展开修改。',
      pickup: '接机订单按时间排列，选择后可派车或放入订单大厅。',
      dropoff: '送机订单按时间排列，选择后可派车或放入订单大厅。',
      drivers: '司机列表空闲优先，冲突或忙碌司机会排在后面。',
      vehicles: '车辆列表空闲优先，冲突或忙碌车辆会排在后面。'
    };
    const titleMap = {
      hero: '导入与派车',
      import: '订单文本',
      charter: '包车',
      pickup: '接机',
      dropoff: '送机',
      drivers: '司机',
      vehicles: '车辆'
    };
    this.setData({
      helpTip: {
        title: titleMap[type] || '说明',
        content: contentMap[type] || '暂无说明'
      }
    });
  },

  hideHelp() {
    this.setData({ helpTip: null });
  },

  parseOrders() {
    const text = String(this.data.importText || '').trim();
    if (!text) {
      wx.showToast({ title: '请先粘贴订单文本', icon: 'none' });
      return;
    }
    this.setData({ loading: true, message: '', conflictText: '' });
    api.parseText(text, true)
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

  submitImport() {
    if (this.data.importMode === 'single') {
      this.parseSingleOrder();
      return;
    }
    this.parseOrders();
  },

  parseSingleOrder() {
    const text = String(this.data.importText || '').trim();
    if (!text) {
      wx.showToast({ title: '请先输入单条订单', icon: 'none' });
      return;
    }
    this.setData({ loading: true, message: '', conflictText: '' });
    api.parseText(text, false)
      .then((res) => {
        const draft = (res && res.draft) || (res && res.drafts && res.drafts[0]) || null;
        this.setData({
          loading: false,
          importOpen: true,
          singleParsed: true,
          message: '单条订单已解析，可直接校对后确认或派车。'
        });
        if (draft) {
          this.setData({
            singleDraftId: String(draft.id || ''),
            singleForm: this.singleFormFromDraft(draft)
          });
        }
        this.loadAll();
        setTimeout(() => {
          const normalized = text.replace(/\s+/g, ' ').trim();
          const match = (this.data.pendingRows || []).find((item) => (
            item.kind === 'draft'
            && String(item.raw_text || '').replace(/\s+/g, ' ').trim() === normalized
          )) || (this.data.pendingRows || []).find((item) => item.kind === 'draft');
          if (match) {
            this.setData({
              singleDraftId: String(match.id || ''),
              singleForm: this.singleFormFromDraft(match)
            });
          }
        }, 260);
      })
      .catch(() => {
        this.setData({ loading: false, conflictText: '单条订单解析失败，请检查文本结构后重试。' });
      });
  },

  singleFormFromDraft(draft) {
    const orderDate = draft.order_date || '';
    const startTime = normalizeTimeText(draft.start_time || '');
    const orderType = draft.order_type || '包车';
    const validEndDate = isIsoDate(draft.end_date) ? draft.end_date : '';
    const validEndTime = /^\d{1,2}:\d{2}$/.test(String(draft.end_time || '').trim()) ? normalizeTimeText(draft.end_time || '') : '';
    const derivedEnd = isAirportTransferOrder(orderType) && orderDate && startTime
      ? addHoursToDateTime(orderDate, startTime, 2)
      : null;
    return {
      order_date: orderDate,
      end_date: (derivedEnd && derivedEnd.end_date) || validEndDate || orderDate,
      start_time: startTime,
      end_time: (derivedEnd && derivedEnd.end_time) || validEndTime,
      order_type: orderType,
      vehicle_type: draft.vehicle_type || 'A-3',
      pickup_location: draft.pickup_location || '',
      dropoff_location: draft.dropoff_location || '',
      agency_name: draft.agency_name || '',
      guest_name: draft.guest_name || '',
      guest_contact: draft.guest_contact || '',
      passenger_count: draft.passenger_count == null ? '' : String(draft.passenger_count),
      luggage_count: draft.luggage_count == null ? '' : String(draft.luggage_count),
      price: draft.price == null ? '' : String(draft.price),
      remark: mergeSingleRemark(draft)
    };
  },

  singlePayload() {
    const form = this.data.singleForm || {};
    const payload = {
      order_date: form.order_date || '',
      end_date: form.end_date || form.order_date || '',
      start_time: form.start_time || '',
      end_time: form.end_time || '',
      order_type: form.order_type || '',
      vehicle_type: form.vehicle_type || '',
      pickup_location: form.pickup_location || '',
      dropoff_location: form.dropoff_location || '',
      agency_name: form.agency_name || '',
      guest_name: form.guest_name || '',
      guest_contact: form.guest_contact || '',
      passenger_count: form.passenger_count === '' ? null : Number(form.passenger_count),
      luggage_count: form.luggage_count === '' ? null : Number(form.luggage_count),
      price: form.price === '' ? null : Number(form.price),
      remark: form.remark || ''
    };
    return payload;
  },

  saveSingleDraft() {
    const draftId = Number(this.data.singleDraftId || 0);
    if (!draftId) {
      wx.showToast({ title: '请先解析单条订单', icon: 'none' });
      return;
    }
    this.setData({ loading: true, message: '', conflictText: '' });
    api.updateDraft(draftId, this.singlePayload())
      .then(() => {
        this.setData({ loading: false, message: '单条订单草稿已保存。' });
        this.loadAll();
      })
      .catch(() => {
        this.setData({ loading: false, conflictText: '保存单条草稿失败，请重试。' });
      });
  },

  confirmSingleDraft() {
    const draftId = Number(this.data.singleDraftId || 0);
    if (!draftId) {
      wx.showToast({ title: '请先解析单条订单', icon: 'none' });
      return;
    }
    this.setData({ loading: true, message: '', conflictText: '' });
    api.updateDraft(draftId, this.singlePayload())
      .then(() => api.confirmDraft(draftId))
      .then(() => {
        this.setData({
          loading: false,
          singleParsed: false,
          singleDraftId: '',
          singleForm: blankSingleForm(),
          importText: '',
          importOpen: false,
          message: '单条订单已确认入池，可继续派车或放入大厅。'
        });
        this.loadAll();
      })
      .catch(() => {
        this.setData({ loading: false, conflictText: '确认单条订单失败，请检查字段后重试。' });
      });
  },

  clearSingleForm() {
    this.setData({
      singleParsed: false,
      singleDraftId: '',
      singleForm: blankSingleForm(),
      importText: '',
      message: '',
      conflictText: ''
    });
  },

  loadAll() {
    this.setData({ loading: true });
    const tenantId = this.currentTenantId();
    Promise.all([
      api.drafts().catch(() => ({ drafts: [] })),
      api.unassignedOrders().catch(() => ({ orders: [] })),
      api.drivers().catch((err) => {
        console.warn('[dispatch load drivers failed]', err);
        return { drivers: this.data.drivers || [] };
      }),
      api.vehicles().catch((err) => {
        console.warn('[dispatch load vehicles failed]', err);
        return { vehicles: this.data.vehicles || [] };
      }),
      api.assignments().catch((err) => {
        console.warn('[dispatch load assignments failed]', err);
        return { assignments: this.data.assignments || [] };
      })
    ])
      .then((results) => {
        const draftsRes = results && results[0] || { drafts: [] };
        const ordersRes = results && results[1] || { orders: [] };
        const driversRes = results && results[2] || { drivers: [] };
        const vehiclesRes = results && results[3] || { vehicles: [] };
        const assignmentsRes = results && results[4] || { assignments: [] };
        const drafts = (draftsRes.drafts || [])
          .filter((item) => !tenantId || !item.tenant_id || Number(item.tenant_id) === tenantId)
          .filter((item) => item.parse_status !== 'confirmed' && item.parse_status !== 'discarded')
          .map((item) => this.decoratePendingRow({ ...item, kind: 'draft' }));
        const orders = (ordersRes.orders || [])
          .filter((item) => !tenantId || !item.tenant_id || Number(item.tenant_id) === tenantId)
          .map((item) => this.decoratePendingRow({ ...item, kind: 'order' }));
        const pendingRows = this.sortPendingRows(drafts.concat(orders)).slice(0, 160);
        const assignments = assignmentsRes.assignments || [];
        const publishedRows = this.decoratePublishedAssignments(assignments);
        const decoratedDrivers = this.decorateDrivers(driversRes.drivers || [], assignments);
        const decoratedVehicles = this.decorateVehicles(vehiclesRes.vehicles || [], assignments);
        console.log('[dispatch resources loaded]', {
          drivers: decoratedDrivers.length,
          vehicles: decoratedVehicles.length,
          idleVehicles: decoratedVehicles.filter((vehicle) => isVehicleUsable(vehicle) && !vehicle.disabled).length,
          vehicleSamples: decoratedVehicles.slice(0, 8).map((vehicle) => vehicle.shortPlate || vehicle.plate_short_code || vehicle.plate_number)
        });
        this.setData({
          pendingRows,
          ...this.groupPendingRows(pendingRows),
          drivers: decoratedDrivers,
          vehicles: decoratedVehicles,
          assignments,
          publishedRows,
          dailyOverview: this.buildDailyOverview(this.data.dailyGroups, {
            drivers: decoratedDrivers,
            vehicles: decoratedVehicles
          }),
          loading: false
        });
        this.updatePreview();
      })
      .catch((err) => {
        console.warn('[dispatch loadAll failed]', err);
        this.setData({ loading: false, conflictText: '加载派车数据失败，请确认后端在线。' });
      });
  },

  currentTenantId() {
    const session = api.getSession() || {};
    return Number(
      (session.user && session.user.tenant_id)
      || (session.dispatcher && session.dispatcher.tenant_id)
      || 0
    );
  },

  decoratePublishedAssignments(assignments) {
    return (assignments || [])
      .slice()
      .sort((a, b) => {
        const left = `${b.order_date || ''} ${b.start_time || ''} ${b.id || b.assignment_id || ''}`;
        const right = `${a.order_date || ''} ${a.start_time || ''} ${a.id || a.assignment_id || ''}`;
        return left.localeCompare(right, 'zh-Hans-CN');
      })
      .slice(0, 80)
      .map((item) => ({
        ...item,
        assignmentId: item.assignment_id || item.id,
        orderId: item.order_id,
        displayOrderNo: item.oid || item.order_id || '订单',
        displayTime: this.formatAssignmentTime(item),
        displayRoute: `${item.pickup_location || '-'} → ${item.dropoff_location || '-'}`,
        displayResource: `${item.driver_name || '未定司机'} · ${item.plate_number || '未定车辆'}`,
        displayPublisher: item.published_by_name ? `发布：${item.published_by_name}` : '发布：未记录',
        statusText: this.assignmentStatusText(item.execution_status || item.status)
      }));
  },

  formatAssignmentTime(item) {
    const start = `${item.order_date || '-'} ${item.start_time || '--:--'}`;
    if (!item.end_time) return start;
    if (item.end_date && item.end_date !== item.order_date) return `${start} - ${item.end_date} ${item.end_time}`;
    return `${start} - ${item.end_time}`;
  },

  assignmentStatusText(status) {
    const map = {
      assigned: '待司机确认',
      confirmed: '司机已确认',
      departed: '已出库',
      arrived: '已到达',
      in_service: '服务中',
      completed: '已完成',
      returned: '已归库'
    };
    return map[status] || status || '-';
  },

  selectPublishedOrder(e) {
    const orderId = Number(e.currentTarget.dataset.orderId || 0);
    const assignmentId = Number(e.currentTarget.dataset.assignmentId || 0);
    const row = this.data.publishedRows.find((item) => Number(item.orderId) === orderId && Number(item.assignmentId) === assignmentId);
    if (!row) return;
    this.setData({
      publishedEditOpen: true,
      publishedEditOrderId: row.orderId,
      publishedEditAssignmentId: row.assignmentId,
      publishedEditTitle: `${row.displayTime} · ${row.displayRoute}`,
      publishedEditForm: {
        order_date: row.order_date || '',
        end_date: row.end_date || row.order_date || '',
        start_time: row.start_time || '',
        end_time: row.end_time || '',
        pickup_location: row.pickup_location || '',
        dropoff_location: row.dropoff_location || '',
        order_type: row.order_type || '',
        vehicle_type: row.order_vehicle_type || row.vehicle_type || '',
        price: row.price || '',
        remark: row.remark || ''
      },
      publishedHistoryRows: [],
      publishedHistoryLoading: true
    });
    this.loadPublishedOrderHistory(row.orderId);
  },

  loadPublishedOrderHistory(orderId) {
    api.orderHistory(orderId)
      .then((res) => {
        this.setData({
          publishedHistoryRows: this.decorateHistoryRows((res && res.history) || []),
          publishedHistoryLoading: false
        });
      })
      .catch(() => {
        this.setData({ publishedHistoryRows: [], publishedHistoryLoading: false });
      });
  },

  refreshPublishedHistory() {
    const orderId = this.data.publishedEditOrderId;
    if (!orderId) return;
    this.setData({ publishedHistoryLoading: true });
    this.loadPublishedOrderHistory(orderId);
  },

  decorateHistoryRows(rows) {
    return (rows || []).map((item) => ({
      ...item,
      title: item.summary || this.historyActionText(item.action),
      actorText: item.actor || 'system',
      timeText: this.formatHistoryTime(item.created_at),
      diffLines: this.formatHistoryDiff(item.diff || {})
    }));
  },

  formatHistoryDiff(diff) {
    const labels = {
      order_date: '日期',
      end_date: '结束日期',
      start_time: '开始',
      end_time: '结束',
      pickup_location: '起点',
      dropoff_location: '终点',
      order_type: '类型',
      vehicle_type: '车型',
      price: '价格',
      remark: '备注'
    };
    return Object.keys(diff || {})
      .filter((key) => labels[key])
      .slice(0, 8)
      .map((key) => ({
        key,
        label: labels[key] || key,
        before: this.displayHistoryValue(diff[key] && diff[key].before),
        after: this.displayHistoryValue(diff[key] && diff[key].after)
      }));
  },

  displayHistoryValue(value) {
    const text = String(value === null || value === undefined ? '' : value).trim();
    return text || '-';
  },

  formatHistoryTime(value) {
    return String(value || '').replace('T', ' ').slice(0, 19);
  },

  historyActionText(action) {
    if (action === 'order_update') return '订单修改';
    if (action === 'order_create') return '订单创建';
    if (action === 'dispatch_assign') return '发布派单';
    return action || '履历';
  },

  onPublishedEditField(e) {
    const field = e.currentTarget.dataset.field;
    if (!field) return;
    this.setData({ [`publishedEditForm.${field}`]: e.detail.value });
  },

  closePublishedEditor() {
    this.setData({
      publishedEditOpen: false,
      publishedEditOrderId: '',
      publishedEditAssignmentId: '',
      publishedEditTitle: '',
      publishedEditForm: {},
      publishedHistoryRows: [],
      publishedHistoryLoading: false
    });
  },

  savePublishedOrder() {
    const orderId = this.data.publishedEditOrderId;
    if (!orderId) return;
    this.setData({ loading: true, message: '', conflictText: '' });
    api.updateOrder(orderId, this.data.publishedEditForm)
      .then(() => {
        wx.showToast({ title: '已保存并通知', icon: 'success' });
        this.setData({ message: '订单已修改，并已发送司机变更通知。' });
        this.loadPublishedOrderHistory(orderId);
        this.loadAll();
      })
      .catch((err) => {
        console.warn('[published order update failed]', err);
        this.setData({ loading: false, conflictText: '修改失败，请检查后端或字段内容。' });
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
      sourceText: row.kind === 'draft' ? '待确认' : '订单',
      typeText: dispatchKind === 'charter' ? '包车' : dispatchKind === 'dropoff' ? '送机' : '接机',
      timeText: `${row.order_date || '待确认日期'} ${row.start_time || '--:--'}-${row.end_time || '--:--'}`,
      compactTimeText: `${row.order_date || '待确认日期'} ${row.start_time || '--:--'}`,
      routeText: `${row.pickup_location || '待确认'} → ${row.dropoff_location || '待确认'}`,
      priceText: row.price ? `¥${row.price}` : '',
      charterDetailText: this.buildCharterDetail(row, risks),
      guestSummaryText: this.buildGuestSummary(row)
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

  buildGuestSummary(row) {
    const parts = [];
    if (row.guest_name) parts.push(`客人 ${row.guest_name}`);
    if (row.guest_contact) parts.push(this.formatGuestContact(row.guest_contact));
    return parts.join(' · ');
  },

  detectPhoneRegion(value) {
    const text = String(value || '').trim();
    if (!text || text.indexOf('+') !== 0) return '';
    const matched = PHONE_REGION_MAP.find((entry) => entry[0].test(text));
    return matched ? matched[1] : '';
  },

  formatGuestContact(value) {
    const text = String(value || '').trim();
    if (!text) return '';
    const region = this.detectPhoneRegion(text);
    return region ? `${text} (${region})` : text;
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
      const usable = isDriverUsable(driver);
      const conflict = this.hasConflict(assignments, 'driver_id', driver.id, selectedWindows);
      const disabled = !usable || conflict;
      return {
        ...driver,
        displayName: this.formatDriverDisplayName(driver),
        selected: String(this.data.driverId) === String(driver.id),
        disabled,
        statusText: !usable ? '不可用' : (conflict ? '冲突' : '空闲'),
        statusClass: disabled ? 'danger' : 'ok'
      };
    }).sort((a, b) => {
      if (a.disabled !== b.disabled) return a.disabled ? 1 : -1;
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
      const usable = isVehicleUsable(vehicle);
      const conflict = this.hasConflict(assignments, 'vehicle_id', vehicle.id, selectedWindows);
      const disabled = !usable || conflict;
      return {
        ...vehicle,
        selected: String(this.data.vehicleId) === String(vehicle.id),
        disabled,
        shortPlate: plateShortCode(vehicle.plate_number) || vehicle.plate_number,
        statusText: !usable ? '不可用' : (conflict ? '冲突' : '空闲'),
        statusClass: disabled ? 'danger' : 'ok'
      };
    }).sort((a, b) => {
      if (a.disabled !== b.disabled) return a.disabled ? 1 : -1;
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
        wx.showToast({ title: '已保存待派' });
        this.loadAll();
      })
      .catch(() => wx.showToast({ title: '确认失败', icon: 'none' }));
  },

  confirmSelectedDrafts() {
    const rows = this.selectedRows().filter((item) => item.kind === 'draft');
    if (!rows.length) {
      wx.showToast({ title: '请选择待确认订单', icon: 'none' });
      return;
    }
    this.setData({ loading: true, conflictText: '', message: '' });
    rows.reduce((chain, row) => chain.then(() => this.ensureOrder(row)), Promise.resolve())
      .then(() => {
        wx.showToast({ title: '已确认' });
        this.setData({
          loading: false,
          selectedKeys: this.data.selectedKeys.filter((key) => !rows.some((row) => row.key === key)),
          message: `已确认 ${rows.length} 条订单，可继续派车。`
        });
        this.loadAll();
      })
      .catch(() => {
        this.setData({ loading: false, conflictText: '确认失败，请检查字段。' });
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
    return api.confirmDraft(row.id).then((res) => {
      const orderId = res && (res.order_id || (res.order && res.order.id) || res.id);
      if (!orderId) throw new Error('missing_order_id');
      return orderId;
    });
  },

  ensureOrderForAuction(row, payload) {
    if (row.kind === 'order') {
      return Promise.resolve({
        ...payload,
        id: Number(row.id),
        oid: payload.oid || row.oid,
        kind: 'order'
      });
    }
    return api.confirmDraft(row.id).then((res) => {
      const order = (res && res.order) || {};
      const orderId = res && (res.order_id || order.id || res.id);
      if (!orderId) throw new Error('missing_order_id');
      return {
        ...payload,
        ...order,
        id: Number(orderId),
        oid: order.oid || payload.oid || row.oid,
        kind: 'order'
      };
    });
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

  publishSelectedToAuction() {
    if (!api.canAccess('auction')) {
      wx.showToast({ title: '当前账号无订单大厅权限', icon: 'none' });
      return;
    }
    const rows = this.selectedRows();
    if (!rows.length) {
      wx.showToast({ title: '请先选择订单', icon: 'none' });
      return;
    }
    wx.showModal({
      title: '放入订单大厅',
      content: `确认将 ${rows.length} 单放入订单大厅？下一步填写起拍价和一口价。`,
      confirmText: '继续',
      success: (modal) => {
        if (!modal.confirm) return;
        this.setData({ loading: true, conflictText: '', message: '' });
        rows.reduce((chain, row) => {
          return chain.then((items) => {
            const payload = row.key === this.data.editingKey ? this.data.editing : row;
            return this.saveRow(row, payload)
              .then(() => this.ensureOrderForAuction(row, payload))
              .then((order) => items.concat(order));
          });
        }, Promise.resolve([]))
          .then((orders) => {
            wx.setStorageSync('auction_publish_draft', {
              order_ids: orders.map((item) => item.id),
              order_oids: orders.map((item) => item.oid).filter(Boolean),
              orders
            });
            this.setData({ loading: false, selectedKeys: [], editingKey: '', editing: {} });
            wx.reLaunch({ url: '/package_dispatch/pages/auction/index' });
          })
          .catch((err) => this.setData({
            loading: false,
            conflictText: `放入订单大厅失败：${this.humanError(err)}`
          }));
      }
    });
  },

  humanError(err) {
    const code = err && (err.error || err.message || err.errMsg);
    const map = {
      draft_not_found: '待确认订单不存在，请刷新后重试。',
      order_not_found: '订单不存在或不属于当前公司，请刷新后重试。',
      unauthorized: '登录已失效，请重新登录。',
      internal_server_error: '后端处理异常，请稍后重试。'
    };
    return map[code] || code || '请检查订单或后端连接。';
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

