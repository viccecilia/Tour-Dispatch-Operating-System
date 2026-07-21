const api = require('../../utils/api');

const STORAGE_KEY = 'dispatch_daily_assignment_draft';
const PUBLISHED_KEY = 'dispatch_daily_assignment_published';

const EXAMPLE_TEXT = `林泽群 3893
1.31 10:00 京都单送关西酒店 3代 绿800
1.31 12:30 关西接机大阪 3代 绿470
1.31 18:20 关西接机大阪 3代 450

姜小涛
1.31 13:00 京都送机关西 3代 司机收24000日元 绿800 指定阿尔法
1.31 18:20 关西接机大阪 3代 450
1.31 21:40 关西接机大阪 3代 绿450

李力
1.31 07:30 大阪送机关西 3代 儿童座椅 绿450
1.31 14:00 东大阪市送机关西 3代 绿470 代收差价2000日元
1.31 18:20 关西接机大阪 3代 450 取消`;

const ORDER_KEYWORDS = ['接机', '送机', '包车', '单送', '日游', '往返', '机场', '关西', '伊丹', '神户'];
const VEHICLE_KEYWORDS = ['10座', '3代', 'Hiace', 'Hiyace', 'Alphard', '阿尔法', '海狮', 'Coaster', '儿童座椅'];

function pad2(value) {
  return String(value).padStart(2, '0');
}

function buildId(prefix) {
  return prefix + '-' + Date.now() + '-' + Math.floor(Math.random() * 100000);
}

function hasOrderSignal(text) {
  return ORDER_KEYWORDS.some((key) => text.indexOf(key) !== -1) ||
    /\d{1,2}[./-]\d{1,2}/.test(text) ||
    /\d{1,2}[:：]\d{2}/.test(text);
}

function normalizeDate(raw) {
  if (!raw) return '';
  const match = String(raw).match(/(\d{1,2})[./-](\d{1,2})/);
  if (!match) return '';
  const year = new Date().getFullYear();
  return `${year}-${pad2(match[1])}-${pad2(match[2])}`;
}

function normalizeTime(raw) {
  if (!raw) return '';
  const match = String(raw).match(/(\d{1,2})[:：](\d{2})/);
  if (!match) return '';
  return `${pad2(match[1])}:${pad2(match[2])}`;
}

function detectType(text) {
  if (/接机|空港迎え|机场接/.test(text)) return '接机';
  if (/送机|空港行き|机场送/.test(text)) return '送机';
  if (/包车|包車|日游|一日游/.test(text)) return '包车';
  if (/往返/.test(text)) return '往返';
  if (/单送|單送|片道/.test(text)) return '单送';
  return '待确认';
}

function detectVehicle(text) {
  const lower = text.toLowerCase();
  if (/10\s*座/.test(text) || lower.indexOf('hiace') !== -1 || text.indexOf('海狮') !== -1) return '10座';
  if (/3\s*代/.test(text) || lower.indexOf('alphard') !== -1 || text.indexOf('阿尔法') !== -1) return '3代';
  if (text.indexOf('Coaster') !== -1 || text.indexOf('中巴') !== -1) return 'Coaster';
  return '';
}

function detectPrice(text) {
  const direct = text.match(/司机收\s*(\d{4,6})\s*日?元?/);
  if (direct) return direct[1];
  const green = text.match(/绿牌?\s*[（(]?\s*(\d{3,6}(?:\+\d{3,6})?)/);
  if (green) return green[1];
  const paren = text.match(/[（(]\s*(\d{3,6}(?:\+\d{3,6})?)\s*[）)]/);
  if (paren) return paren[1];
  const tail = text.match(/(?:^|\s)(\d{3,6}(?:\+\d{3,6})?)\s*(?:取消|作废)?\s*$/);
  return tail ? tail[1] : '';
}

function cleanupRoute(text) {
  let route = text;
  route = route.replace(/\d{1,2}[./-]\d{1,2}/g, '');
  route = route.replace(/\d{1,2}[:：]\d{2}/g, '');
  route = route.replace(/司机收\s*\d{3,6}\s*日?元?/g, '');
  route = route.replace(/绿牌?\s*[（(]?\s*\d{3,6}(?:\+\d{3,6})?\s*[）)]?/g, '');
  route = route.replace(/[（(]\s*\d{3,6}(?:\+\d{3,6})?\s*[）)]/g, '');
  route = route.replace(/(?:^|\s)\d{3,6}(?:\+\d{3,6})?\s*(?:取消|作废)?\s*$/g, '');
  VEHICLE_KEYWORDS.forEach((word) => {
    route = route.replace(new RegExp(word, 'gi'), '');
  });
  route = route.replace(/绿|指定|取消|作废/g, '');
  route = route.replace(/\s+/g, ' ').trim();
  return route || text.trim();
}

function parseOrderLine(line) {
  const dateMatch = line.match(/\d{1,2}[./-]\d{1,2}/);
  const timeMatch = line.match(/\d{1,2}[:：]\d{2}/);
  const status = /取消|作废/.test(line) ? '作废' : '待发布';
  return {
    id: buildId('order'),
    date: normalizeDate(dateMatch ? dateMatch[0] : ''),
    time: normalizeTime(timeMatch ? timeMatch[0] : ''),
    type: detectType(line),
    vehicleType: detectVehicle(line),
    route: cleanupRoute(line),
    price: detectPrice(line),
    status,
    remark: line.trim(),
  };
}

function parseDriverHeader(line) {
  const trimmed = line.trim();
  const codeMatch = trimmed.match(/([A-Za-z]?\d{3,4})\s*$/);
  const vehicleCode = codeMatch ? codeMatch[1] : '';
  const driverName = vehicleCode ? trimmed.slice(0, trimmed.length - vehicleCode.length).trim() : trimmed;
  return {
    id: buildId('driver'),
    driverName: driverName || '未命名司机',
    vehicleCode,
    orders: [],
  };
}

function normalizeGroups(groups) {
  return (groups || []).map((group) => {
    const orders = (group.orders || []).map((order, index) => {
      const next = Object.assign({}, order);
      next.id = next.id || buildId('order');
      next.displayIndex = index + 1;
      return next;
    });
    return Object.assign({}, group, {
      id: group.id || buildId('driver'),
      driverName: group.driverName || '未命名司机',
      vehicleCode: group.vehicleCode || '',
      orders,
    });
  });
}

function calcStats(groups) {
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

function parseGroups(sourceText) {
  const lines = String(sourceText || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const groups = [];
  let current = null;

  lines.forEach((line) => {
    const orderLike = hasOrderSignal(line) &&
      (/\d{1,2}[./-]\d{1,2}/.test(line) ||
        /\d{1,2}[:：]\d{2}/.test(line) ||
        ORDER_KEYWORDS.some((key) => line.indexOf(key) !== -1));

    if (!orderLike) {
      current = parseDriverHeader(line);
      groups.push(current);
      return;
    }

    if (!current) {
      current = parseDriverHeader('未分组司机');
      groups.push(current);
    }

    current.orders.push(parseOrderLine(line));
  });

  return normalizeGroups(groups.filter((group) => group.driverName || (group.orders && group.orders.length)));
}

Page({
  data: {
    sourceText: '',
    groups: [],
    stats: calcStats([]),
    message: '',
    saving: false,
    publishing: false,
  },

  onLoad() {
    this.restoreDraft();
  },

  onShow() {
    if (api.setActiveTab) api.setActiveTab('/package_dispatch/pages/daily/index');
    this.refreshTabBar();
  },

  refreshTabBar() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().refresh && this.getTabBar().refresh();
    }
  },

  updateGroups(groups, message) {
    const next = normalizeGroups(groups);
    const patch = { groups: next, stats: calcStats(next) };
    if (typeof message === 'string') patch.message = message;
    this.setData(patch);
  },

  restoreDraft() {
    const draft = wx.getStorageSync(STORAGE_KEY);
    if (draft && (draft.sourceText || draft.groups)) {
      this.setData({ sourceText: draft.sourceText || '' });
      this.updateGroups(draft.groups || [], '已恢复上次保存的草稿。');
    }
  },

  onSourceInput(event) {
    this.setData({ sourceText: event.detail.value });
  },

  fillExample() {
    this.setData({ sourceText: EXAMPLE_TEXT, message: '已填入示例，可以直接解析。' });
  },

  clearSource() {
    this.setData({ sourceText: '', groups: [], stats: calcStats([]), message: '已清空。' });
  },

  parseText() {
    const text = (this.data.sourceText || '').trim();
    if (!text) {
      wx.showToast({ title: '请先粘贴日配文本', icon: 'none' });
      return;
    }
    const groups = parseGroups(text);
    this.updateGroups(groups, `已解析 ${groups.length} 名司机、${calcStats(groups).orders} 单。`);
  },

  onGroupInput(event) {
    const index = Number(event.currentTarget.dataset.groupIndex);
    const field = event.currentTarget.dataset.key;
    const groups = normalizeGroups(this.data.groups);
    if (!groups[index] || !field) return;
    groups[index][field] = event.detail.value;
    this.updateGroups(groups);
  },

  onOrderInput(event) {
    const groupIndex = Number(event.currentTarget.dataset.groupIndex);
    const orderIndex = Number(event.currentTarget.dataset.orderIndex);
    const field = event.currentTarget.dataset.key;
    const groups = normalizeGroups(this.data.groups);
    if (!groups[groupIndex] || !groups[groupIndex].orders[orderIndex] || !field) return;
    groups[groupIndex].orders[orderIndex][field] = event.detail.value;
    this.updateGroups(groups);
  },

  addGroup() {
    const groups = normalizeGroups(this.data.groups);
    groups.push(parseDriverHeader('未命名司机'));
    this.updateGroups(groups, '已新增司机分组。');
  },

  removeGroup(event) {
    const index = Number(event.currentTarget.dataset.groupIndex);
    const groups = normalizeGroups(this.data.groups);
    if (!groups[index]) return;
    groups.splice(index, 1);
    this.updateGroups(groups, '已删除司机分组。');
  },

  addOrder(event) {
    const groupIndex = Number(event.currentTarget.dataset.groupIndex);
    const groups = normalizeGroups(this.data.groups);
    if (!groups[groupIndex]) return;
    groups[groupIndex].orders.push(parseOrderLine(''));
    this.updateGroups(groups, '已新增订单。');
  },

  removeOrder(event) {
    const groupIndex = Number(event.currentTarget.dataset.groupIndex);
    const orderIndex = Number(event.currentTarget.dataset.orderIndex);
    const groups = normalizeGroups(this.data.groups);
    if (!groups[groupIndex] || !groups[groupIndex].orders[orderIndex]) return;
    groups[groupIndex].orders.splice(orderIndex, 1);
    this.updateGroups(groups, '已删除订单。');
  },

  saveDraft() {
    this.setData({ saving: true });
    const draft = {
      sourceText: this.data.sourceText,
      groups: normalizeGroups(this.data.groups),
      savedAt: new Date().toISOString(),
    };
    wx.setStorageSync(STORAGE_KEY, draft);
    this.setData({ saving: false, message: '草稿已保存。' });
    wx.showToast({ title: '已保存草稿', icon: 'success' });
  },

  publishAssignments() {
    const groups = normalizeGroups(this.data.groups);
    const orderCount = calcStats(groups).orders;
    if (!orderCount) {
      wx.showToast({ title: '没有可发布订单', icon: 'none' });
      return;
    }

    this.setData({ publishing: true });
    const publishedGroups = groups.map((group) => {
      const orders = group.orders.map((order) => {
        if (order.status === '作废') return order;
        return Object.assign({}, order, { status: '已发布' });
      });
      return Object.assign({}, group, { orders });
    });

    const payload = {
      sourceText: this.data.sourceText,
      groups: normalizeGroups(publishedGroups),
      publishedAt: new Date().toISOString(),
    };

    wx.setStorageSync(PUBLISHED_KEY, payload);
    wx.setStorageSync(STORAGE_KEY, payload);
    this.setData({ publishing: false });
    this.updateGroups(payload.groups, '已发布日配，司机端通知接口后续接入后会同步下发。');
    wx.showToast({ title: '已发布日配', icon: 'success' });
  },
});
