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
  林泽群: '林澤群',
  万强: '万強',
  白石贤志: '白石賢志',
  先山: '先山武志'
};

function pad2(value) {
  return String(value).padStart(2, '0');
}

function splitNodeDateTime(value, fallbackDate) {
  const text = String(value || '').trim();
  const match = text.match(/^(\d{4}-\d{2}-\d{2})[T\s](\d{2}:\d{2})/);
  return {
    date: match ? match[1] : String(fallbackDate || ''),
    time: match ? match[2] : ''
  };
}

function composeNodeDateTime(date, time) {
  const cleanDate = String(date || '').trim();
  const cleanTime = String(time || '').trim();
  return cleanDate && cleanTime ? `${cleanDate}T${cleanTime}:00` : '';
}

function nodeTypeLabel(value) {
  const labels = {
    garage_out: '出库', pickup: '接客', waypoint: '途经', dropoff: '送达', garage_in: '归库'
  };
  return labels[String(value || '')] || '行程节点';
}

function nodeValidationLabel(value) {
  const code = String(value || '');
  if (code === 'invalid_datetime') return '日期或时间格式不正确';
  if (code.indexOf('segment_time_order:') === 0) return '同一地点的离开时间不能早于到达时间';
  if (code.indexOf('route_time_order:') === 0) return '行程时间顺序前后冲突';
  if (code.indexOf('route_node_location_missing:') === 0) return '行程地点不能为空';
  return code;
}

function documentValidationItem(value) {
  const code = String(value || '');
  const orderMatch = code.match(/^order_(\d+)_/);
  const orderLabel = orderMatch ? `第${orderMatch[1]}单 · ` : '';
  const confirmation = code.indexOf('_confirmation_required') >= 0 || code.indexOf('_validation_required') >= 0;
  let category = '其他';
  let field = '文书信息';
  if (/pickup|arrival|dropoff|operation_|route_|segment_|datetime/.test(code)) { category = '行程'; field = /time|arrival|datetime/.test(code) ? '时间' : '地点'; }
  else if (/applicant/.test(code)) { category = '申请者'; field = '申请者编号'; }
  else if (/price|fare|fee|advance|tax/.test(code)) { category = '费用'; field = /tax/.test(code) ? '税费状态' : '金额明细'; }
  else if (/area|office/.test(code)) { category = '营业区域'; field = /office/.test(code) ? '营业所' : '营业区域'; }
  else if (/safe|operations_manager/.test(code)) { category = '安全与运行管理'; field = /manager/.test(code) ? '运行管理者' : '安全指示'; }
  else if (/driver|vehicle|plate/.test(code)) { category = '司机与车辆'; field = /driver/.test(code) ? '司机' : '车辆'; }
  else if (code === 'invalid_datetime') { category = '行程'; field = '日期或时间'; }
  const message = code.indexOf(':') >= 0
    ? nodeValidationLabel(code)
    : `${orderLabel}${field}${confirmation ? '已有内容，尚未确认' : '缺少必要信息'}`;
  return { code, category, message, kind: confirmation ? 'confirmation' : 'missing' };
}

function buildValidationPresentation(values) {
  const raw = Array.from(new Set((values || []).map((item) => String(item || '')).filter(Boolean)));
  const seen = new Set();
  const issues = raw.map(documentValidationItem).filter((item) => {
    const key = `${item.category}|${item.message}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  const buckets = {};
  issues.forEach((item) => {
    if (!buckets[item.category]) buckets[item.category] = { label: item.category, count: 0, missing: 0, confirmation: 0 };
    buckets[item.category].count += 1;
    buckets[item.category][item.kind] += 1;
  });
  const summary = Object.values(buckets).map((item) => ({
    ...item,
    detail: [item.missing ? `${item.missing}项缺少值` : '', item.confirmation ? `${item.confirmation}项待确认` : ''].filter(Boolean).join(' · ')
  }));
  return { raw, issues, summary };
}

function stripDailyOrdinal(value) {
  return String(value || '')
    .replace(/^\s*(?:\d+\uFE0F?\u20E3|[①-⑳❶-❿])\s*/, '')
    .replace(/^\s*\d+[、)）]\s*/, '')
    .trim();
}

function plateShortCode(value) {
  const digits = String(value || '').replace(/\D/g, '');
  return digits.slice(-4).replace(/^0+(?=\d)/, '');
}

function buildDailyId(prefix) {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 100000)}`;
}

function dailyImportRequestId() {
  return `daily-${Date.now()}-${Math.floor(Math.random() * 1000000)}`;
}

function hasDailyOrderSignal(text) {
  return DAILY_ORDER_KEYWORDS.some((key) => text.indexOf(key) !== -1) ||
    /\d{1,2}[./-]\d{1,2}/.test(text) ||
    /\d{1,2}[:：]\d{2}/.test(text);
}

function normalizeDailyDate(raw, baseYear = new Date().getFullYear()) {
  if (!raw) return '';
  const match = String(raw).match(/(\d{1,2})[./-](\d{1,2})/);
  if (!match) return '';
  const year = Number(baseYear) || new Date().getFullYear();
  return `${year}-${pad2(match[1])}-${pad2(match[2])}`;
}

function normalizeDailyTime(raw) {
  if (!raw) return '';
  const match = String(raw).trim().match(/(\d{1,2})[:：](\d{2})\s*(am|pm)?/i);
  if (!match) return '';
  let hour = Number(match[1]);
  const meridiem = String(match[3] || '').toLowerCase();
  if (meridiem === 'pm' && hour < 12) hour += 12;
  if (meridiem === 'am' && hour === 12) hour = 0;
  return `${pad2(hour)}:${match[2]}`;
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
  let route = stripDailyOrdinal(text);
  route = route.replace(/\d{1,2}[./-]\d{1,2}/g, '');
  route = route.replace(/\d{1,2}[:：]\d{2}\s*(?:am|pm)?/gi, '');
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
  const normalizedLine = stripDailyOrdinal(line);
  const dateMatch = normalizedLine.match(/\d{1,2}[./-]\d{1,2}/);
  const timeMatch = normalizedLine.match(/\d{1,2}[:：]\d{2}\s*(?:am|pm)?/i);
  return {
    id: buildDailyId('order'),
    date: normalizeDailyDate(dateMatch ? dateMatch[0] : ''),
    time: normalizeDailyTime(timeMatch ? timeMatch[0] : ''),
    type: detectDailyType(normalizedLine),
    vehicleType: detectDailyVehicle(normalizedLine),
    route: cleanupDailyRoute(normalizedLine),
    price: detectDailyPrice(normalizedLine),
    status: /取消|作废/.test(normalizedLine) ? '作废' : '待发布',
    remark: normalizedLine
  };
}

function parseDailyDriverHeader(line) {
  const trimmed = stripDailyOrdinal(line);
  const dateMatch = trimmed.match(/^\s*(\d{1,2}[./-]\d{1,2})\s*/);
  const serviceDate = normalizeDailyDate(dateMatch ? dateMatch[1] : '');
  let body = dateMatch ? trimmed.slice(dateMatch[0].length).trim() : trimmed;
  const officeMatch = body.match(/\s*[（(]([^）)]*)[）)]\s*$/);
  const officeNote = officeMatch ? officeMatch[1].trim() : '';
  if (officeMatch) body = body.slice(0, officeMatch.index).trim();
  const codeMatch = body.match(/([A-Za-z]?\d{3,4})\s*$/);
  const vehicleCode = codeMatch ? codeMatch[1] : '';
  const driverName = vehicleCode ? body.slice(0, body.length - vehicleCode.length).replace(/[-－—–·\s]+$/g, '').trim() : body;
  return {
    id: buildDailyId('driver'),
    driverName: driverName || '未命名司机',
    vehicleCode,
    serviceDate,
    officeNote,
    orders: []
  };
}

function looksLikeDailyDriverHeader(line, nextLine) {
  const text = stripDailyOrdinal(line);
  if (!text || /\d{1,2}[:：]\d{2}/.test(text)) return false;
  if (/追加|补充|備考|备注|說明|说明|注意|待定|有合适|在群/.test(text)) return false;
  const withoutOffice = text.replace(/\s*[（(][^）)]*[）)]\s*$/, '').trim();
  const withoutDate = withoutOffice.replace(/^\s*\d{1,2}[./-]\d{1,2}\s*/, '').trim();
  if (/^.+?[A-Za-z]?\d{3,4}$/.test(withoutDate) && !DAILY_ORDER_KEYWORDS.some((key) => withoutDate.indexOf(key) !== -1)) {
    return true;
  }
  const next = stripDailyOrdinal(nextLine);
  return !!next &&
    text.length <= 12 &&
    !/\s/.test(text) &&
    !hasDailyOrderSignal(text) &&
    hasDailyOrderSignal(next);
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
    const sourceOrders = group.orders || [];
    const serviceDate = group.serviceDate || ((sourceOrders.find((order) => order.date) || {}).date) || '';
    const orders = sourceOrders.map((order, index) => ({
      ...order,
      id: order.id || buildDailyId('order'),
      date: order.date || serviceDate,
      displayIndex: index + 1
    }));
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
    driverTotal: 0,
    idleVehicles: 0,
    vehicleTotal: 0,
    idleTenSeat: 0,
    tenSeatTotal: 0,
    idleAlphard: 0,
    alphardTotal: 0,
    missingDriverGroups: [],
    missingVehicleGroups: [],
    driverNav: []
  };
}

function parseDailyGroups(sourceText) {
  const lines = String(sourceText || '').split(/\r?\n/);
  const groups = [];
  let current = null;
  lines.forEach((rawLine, index) => {
    const line = String(rawLine || '').trim();
    if (!line) return;
    const nextLine = lines.slice(index + 1).find((item) => String(item || '').trim()) || '';
    if (looksLikeDailyDriverHeader(line, nextLine)) {
      current = parseDailyDriverHeader(line);
      groups.push(current);
      return;
    }
    const normalizedLine = stripDailyOrdinal(line);
    const orderLike = hasDailyOrderSignal(normalizedLine) &&
      (/\d{1,2}[./-]\d{1,2}/.test(normalizedLine) ||
        /\d{1,2}[:：]\d{2}/.test(normalizedLine) ||
        DAILY_ORDER_KEYWORDS.some((key) => normalizedLine.indexOf(key) !== -1));
    if (!orderLike) {
      if (current && current.orders.length) {
        const lastOrder = current.orders[current.orders.length - 1];
        lastOrder.remark = [lastOrder.remark, normalizedLine].filter(Boolean).join('\n');
        return;
      }
      current = parseDailyDriverHeader(normalizedLine);
      groups.push(current);
      return;
    }
    if (!current) {
      current = parseDailyDriverHeader('未分组司机');
      groups.push(current);
    }
    const order = parseDailyOrderLine(normalizedLine);
    if (!order.date && current.serviceDate) order.date = current.serviceDate;
    current.orders.push(order);
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
  const explicit = route.match(/^(.+?)\s*(?:->|→|⇒|－|-)\s*(.+)$/);
  if (explicit) {
    return {
      pickup_location: explicit[1].trim(),
      dropoff_location: explicit[2].replace(/\s*(?:LINE|WeChat|WhatsApp|Kakao|微信|携程)\s*$/i, '').trim()
    };
  }
  const markers = ['接机', '送机', '单送'];
  for (let i = 0; i < markers.length; i += 1) {
    const marker = markers[i];
    const index = route.indexOf(marker);
    if (index > 0) {
      return {
        pickup_location: route.slice(0, index).trim() || route,
        dropoff_location: route.slice(index + marker.length).replace(/\s*(?:LINE|WeChat|WhatsApp|Kakao|微信|携程)\s*$/i, '').trim() || marker
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
  const raw = stripDailyOrdinal(order.rawText || '');
  if (raw) return [order.date, raw].filter(Boolean).join(' ');
  const parts = [order.date, order.time, order.route, order.vehicleType, order.price ? `绿${order.price}` : '']
    .filter(Boolean);
  return parts.join(' ');
}

function buildDailyOrderPayload(order) {
  const parsed = order.parsed || {};
  const end = addHoursToDateTime(order.date, order.time, order.type === '包车' ? 8 : 2);
  const route = splitDailyRouteForOrder(order.route);
  const pickupLocation = parsed.pickup_location || route.pickup_location || '待补';
  const dropoffLocation = parsed.dropoff_location || route.dropoff_location || '待补';
  const feeNotes = [
    parsed.fee_remark,
    order.price ? `日配价格 ${order.price}` : ''
  ].map((item) => String(item || '').trim()).filter(Boolean);
  return {
    order_source: parsed.order_source || null,
    order_note_code: parsed.order_note_code || null,
    vehicle_class: parsed.vehicle_class || null,
    vehicle_type_code: parsed.vehicle_type_code || null,
    driver_language: parsed.driver_language || null,
    vehicle_color: parsed.vehicle_color || null,
    snow_tire: parsed.snow_tire || null,
    passenger_count: parsed.passenger_count || 0,
    luggage_count: parsed.luggage_count || 0,
    guest_name: parsed.guest_name || null,
    guest_contact: parsed.guest_contact || null,
    agency_name: parsed.agency_name || null,
    price_rmb: parsed.price_rmb || null,
    price_jpy: parsed.price_jpy || null,
    collection_amount_jpy: parsed.collection_amount_jpy || null,
    parking_fee_jpy: parsed.parking_fee_jpy || null,
    other_fee_jpy: parsed.other_fee_jpy || null,
    flight_number: parsed.flight_number || null,
    driver_settlement_note: parsed.driver_settlement_note || null,
    operations_business_area: parsed.operations_business_area || null,
    order_date: order.date || '',
    end_date: end.end_date || order.date || '',
    start_time: normalizeTimeText(order.time || ''),
    end_time: end.end_time || normalizeTimeText(order.time || ''),
    order_type: order.type || '待确认',
    vehicle_type: order.vehicleType || '',
    pickup_location: pickupLocation === '接机 · 地点待补' ? '待补' : pickupLocation,
    dropoff_location: dropoffLocation || '待补',
    price: dailyPriceToNumber(order.price),
    remark: order.remark || buildDailyOrderText(order),
    fee_remark: feeNotes.filter((item, index, list) => list.indexOf(item) === index).join('；'),
    source_channel: parsed.source_channel || order.sourceChannel || 'daily_assignment'
  };
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

function vehicleTypeBucket(vehicle) {
  const text = [
    vehicle && vehicle.vehicle_type,
    vehicle && vehicle.vehicle_model,
    vehicle && vehicle.model,
    vehicle && vehicle.body_type,
    vehicle && vehicle.seat_count,
    vehicle && vehicle.capacity,
    vehicle && vehicle.note,
    vehicle && vehicle.remark
  ].filter(Boolean).join(' ').toLowerCase();
  if (text.indexOf('alphard') >= 0 || text.indexOf('アルファ') >= 0 || text.indexOf('阿尔法') >= 0 || text.indexOf('3代') >= 0 || text.indexOf('7座') >= 0) {
    return 'Alphard';
  }
  return '10座';
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

function isoToday() {
  const now = new Date();
  return `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`;
}

function shiftIsoDate(value, delta) {
  const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})$/);
  const date = match
    ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
    : new Date();
  date.setDate(date.getDate() + Number(delta || 0));
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

const FIXED_TOUR_EDITOR_STORAGE_KEY = 'dispatch-fixed-tour-editor-v014';

function fixedTourRequestId(prefix = 'charter') {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 1000000)}`;
}

function blankFixedTourNode(dayIndex = 1) {
  return {
    client_node_id: fixedTourRequestId('node'),
    route_node_id: '',
    preset_node_id: '',
    day_index: dayIndex,
    location_name: '',
    default_arrival_time: '',
    default_departure_time: '',
    note: ''
  };
}

function blankFixedTourEditor(mode = 'preset', businessStartDate = isoToday()) {
  return {
    mode,
    route_id: '',
    route_name: mode === 'custom' ? '私人订制行程' : '',
    description: '',
    trip_type: 'day',
    duration_days: 1,
    business_start_date: businessStartDate,
    client_request_id: fixedTourRequestId(mode === 'custom' ? 'custom' : 'preset'),
    days: [{ day_index: 1, nodes: [blankFixedTourNode(1), blankFixedTourNode(1)] }]
  };
}

function fixedTourEditorFromRoute(route, mode = 'preset', businessStartDate = isoToday()) {
  const stops = Array.isArray(route && route.stops) ? route.stops : [];
  const dayIndexes = [...new Set(stops.map((item) => Number(item.day_index || 1)))].sort((a, b) => a - b);
  const days = (dayIndexes.length ? dayIndexes : [1]).map((dayIndex) => ({
    day_index: dayIndex,
    nodes: stops.filter((item) => Number(item.day_index || 1) === dayIndex).map((item) => ({
      client_node_id: fixedTourRequestId('node'),
      route_node_id: item.route_node_id || '',
      preset_node_id: item.preset_node_id || item.source_preset_node_id || '',
      day_index: dayIndex,
      location_name: item.location_name || item.location || '',
      default_arrival_time: item.default_arrival_time || item.arrival_time || '',
      default_departure_time: item.default_departure_time || item.departure_time || '',
      note: item.note || ''
    }))
  }));
  return {
    mode,
    route_id: mode === 'preset' ? String(route && route.id || '') : '',
    route_name: route && (route.route_name || route.name) || '',
    description: route && route.description || '',
    trip_type: route && route.trip_type || (days.length > 1 ? 'multi_day' : 'day'),
    duration_days: Math.max(Number(route && route.duration_days || 1), days.length),
    business_start_date: businessStartDate,
    client_request_id: fixedTourRequestId(mode === 'custom' ? 'custom' : 'preset'),
    days
  };
}

function fixedTourRoutePayload(editor) {
  const days = Array.isArray(editor && editor.days) ? editor.days : [];
  const stops = [];
  days.forEach((day, dayOffset) => {
    const dayIndex = Number(day.day_index || dayOffset + 1);
    (day.nodes || []).forEach((node) => stops.push({
      route_node_id: node.route_node_id || '',
      preset_node_id: node.preset_node_id || '',
      day_index: dayIndex,
      location_name: String(node.location_name || ''),
      default_arrival_time: String(node.default_arrival_time || ''),
      default_departure_time: String(node.default_departure_time || ''),
      note: String(node.note || '')
    }));
  });
  return {
    route_name: String(editor && editor.route_name || '').trim(),
    description: String(editor && editor.description || '').trim(),
    trip_type: editor && editor.trip_type || 'day',
    duration_days: Math.max(1, days.length),
    route_summary: stops.map((item) => item.location_name.trim()).filter(Boolean).join(' → '),
    default_start_time: stops[0] && (stops[0].default_departure_time || stops[0].default_arrival_time) || '',
    default_end_time: stops.length && (stops[stops.length - 1].default_arrival_time || stops[stops.length - 1].default_departure_time) || '',
    stops
  };
}

function fixedTourRouteCard(route) {
  const stops = Array.isArray(route.stops) ? route.stops : [];
  const preview = route.route_summary || stops.map((item) => item.location_name).filter(Boolean).join(' → ');
  const durationDays = Math.max(Number(route.duration_days || 1), ...stops.map((item) => Number(item.day_index || 1)), 1);
  return {
    ...route,
    route_preview: preview,
    main_places: stops.slice(0, 4).map((item) => item.location_name).filter(Boolean).join(' · '),
    duration_label: durationDays > 1 ? `${durationDays}天` : (route.standard_duration_minutes ? `约${Math.round(Number(route.standard_duration_minutes) / 60)}小时` : '日归')
  };
}

function plateTail(value) {
  const text = String(value || '').trim();
  const digits = text.replace(/\D/g, '');
  return digits.slice(-4) || text || '未定车辆';
}

function blankDailyReviewForm() {
  return {
    order_date: '',
    start_time: '',
    business_area: '',
    order_type: '',
    pickup_location: '',
    dropoff_location: '',
    price: ''
  };
}

const DAILY_BUSINESS_AREAS = ['大阪市域交通圏', '京都市域交通圏', '関西国際空港', '上記以外'];
const DAILY_ORDER_TYPES = ['接机', '送机', '包车'];

Page({
  data: {
    workbenchMode: 'daily',
    fixedTourDate: isoToday(),
    fixedTourView: 'quick',
    fixedTourPickerOpen: '',
    fixedTourReturnToQuick: false,
    fixedTourVisibleRoutes: [],
    fixedTourVisibleDrivers: [],
    fixedTourVisibleVehicles: [],
    fixedTourPickerNotice: '',
    fixedTourSummary: '请选择线路、司机和车辆',
    fixedTourEditor: null,
    fixedTourEditorDirty: false,
    fixedTourTripTypeIndex: 0,
    fixedTourTripTypeLabels: ['日归', '多日'],
    fixedTourCurrentDraft: null,
    fixedTourGeneratedDocument: null,
    fixedTourDraftAssociationText: '',
    fixedTourPendingRequestId: '',
    fixedTourQuery: '',
    fixedTourRoutes: [],
    fixedTourSelectedRoute: null,
    fixedTourSelectedDriver: null,
    fixedTourSelectedVehicle: null,
    fixedTourRoutePreview: '',
    fixedTourRouteQuery: '',
    fixedTourDriverQuery: '',
    fixedTourVehicleQuery: '',
    fixedTourTimelineStops: [],
    fixedTourPreSummary: '无',
    fixedTourPostSummary: '无',
    fixedTourRouteIndex: 0,
    fixedTourDriverIndex: 0,
    fixedTourVehicleIndex: 0,
    fixedTourRouteWheel: [0],
    fixedTourDriverWheel: [0],
    fixedTourVehicleWheel: [0],
    fixedTourDriverId: '',
    fixedTourVehicleId: '',
    fixedTourRouteId: '',
    fixedTourMessage: '',
    fixedTourSegments: [],
    fixedTourSegmentTypes: ['airport_pickup', 'airport_dropoff', 'transfer', 'custom'],
    fixedTourSegmentTypeLabels: ['机场接机', '机场送机', '普通接送', '自定义'],
    fixedTourStep: 1,
    fixedTourDraftReady: false,
    fixedTourSubmitting: false,
    fixedTourSuggestedPrice: '',
    fixedTourEffectivePrice: '',
    fixedTourPriceEdited: false,
    fixedTourPriceHint: '',
    fixedTourEditingSegmentIndex: -1,
    fixedTourAcceptanceCount: 1,
    fixedTourInstructionCount: 1,
    dailyDate: isoToday(),
    dailyStatusFilter: 'all',
    dailyStatusOptions: [
      { value: 'all', label: '全部' },
      { value: 'pending', label: '待审核' },
      { value: 'ready', label: '可发布' }
    ],
    dailyRunGroups: [],
    serverRunGroups: [],
    dailyRunSummary: { vehicles: 0, orders: 0, published: 0, pending: 0 },
    dailySelectedGroupKeys: [],
    dailyPdfLoadingKey: '',
    dailyPdfReviewOpen: false,
    dailyPdfReviewGroup: null,
    dailyPdfReviewDocument: null,
    dailyPdfReviewCanConfirm: false,
    dailyPdfPreviewUnavailable: false,
    dailyPdfDraftOnly: false,
    dailyPdfSourceMode: '',
    dailyPdfCurrentDraftId: '',
    dailyPdfDocumentTab: 'acceptance',
    dailyPdfReviewIndex: 0,
    dailyPdfReviewTotal: 0,
    dailyPdfValidationIssues: [],
    dailyPdfValidationRaw: [],
    dailyPdfIssueSummary: [],
    dailyPdfIssuesExpanded: false,
    dailyPdfNodesExpanded: false,
    dailyPdfNodes: [],
    dailyPdfFields: [],
    dailyPdfSourceHash: '',
    dailyPdfDocumentRevision: '',
    dailyFieldEditOpen: false,
    dailyFieldEditIndex: -1,
    dailyFieldEditForm: null,
    dailyNodeEditOpen: false,
    dailyNodeEditIndex: -1,
    dailyNodeEditForm: null,
    dailyImportOpen: false,
    dailyImportSubmitting: false,
    dailyImportDefaultDate: isoToday(),
    dailyImportBatchId: '',
    dailyImportLastResult: null,
    dailyImportedHighlightKey: '',
    dailyImportDefaultDate: isoToday(),
    dailyImportBatchId: '',
    dailyImportLastResult: null,
    dailyImportedHighlightKey: '',
    dailyReviewOpen: false,
    dailyReviewGroupKey: '',
    dailyReviewOrderIndex: 0,
    dailyReviewEdit: false,
    dailyReviewGroup: null,
    dailyReviewOrder: null,
    dailyReviewConfirmedCount: 0,
    dailyReviewForm: blankDailyReviewForm(),
    dailyBusinessAreas: DAILY_BUSINESS_AREAS,
    dailyOrderTypes: DAILY_ORDER_TYPES,
    importOpen: true,
    importMode: 'daily',
    importText: SAMPLE_TEXT,
    batchFullscreen: false,
    batchFullscreenText: '',
    dailySourceText: '',
    dailyGroups: [],
    dailyStats: calcDailyStats([]),
    dailyOverview: blankDailyOverview(),
    dailyMessage: '',
    dailySwipeGroupIndex: -1,
    dailySwipeOrderIndex: -1,
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

  switchWorkbenchMode(e) {
    const asked = (e.currentTarget.dataset || {}).mode;
    const mode = ['daily', 'fixed', 'batch'].includes(asked) ? asked : 'daily';
    if (this.data.workbenchMode === 'fixed' && mode !== 'fixed' && this.data.fixedTourEditorDirty) {
      wx.showModal({
        title: '行程尚未保存',
        content: '输入内容已暂存在本机。离开后再次进入“日游行程”仍可继续编辑。',
        cancelText: '继续编辑',
        confirmText: '离开',
        success: (res) => { if (res.confirm) this.applyWorkbenchMode(mode); }
      });
      return;
    }
    this.applyWorkbenchMode(mode);
  },

  applyWorkbenchMode(mode) {
    this.setData({ workbenchMode: mode, importOpen: mode === 'batch' });
    if (mode === 'fixed') {
      this.restoreFixedTourEditor();
      this.loadFixedTours();
    }
  },

  loadFixedTours() {
    api.mobileFixedTourRoutes()
      .then((result) => {
        const routes = (result.routes || []).map(fixedTourRouteCard);
        this.setData({ fixedTourRoutes: routes, fixedTourMessage: '' }, () => this.applyFixedTourRouteFilter());
      })
      .catch((error) => this.setData({ fixedTourMessage: api.errorMessage(error) }));
  },

  applyFixedTourRouteFilter() {
    const needle = String(this.data.fixedTourRouteQuery || '').trim().toLowerCase().replace(/[\s\-－_]+/g, '');
    const routes = (this.data.fixedTourRoutes || []).filter((route) => {
      if (!needle) return true;
      const searchable = [
        route.route_code, route.route_name, route.description, route.route_summary,
        ...(route.stops || []).map((item) => item.location_name)
      ].join(' ').toLowerCase().replace(/[\s\-－_]+/g, '');
      return searchable.indexOf(needle) >= 0;
    });
    this.setData({ fixedTourVisibleRoutes: routes });
  },

  applyFixedTourDriverFilter() {
    const needle = normalizeDailyMatchValue(this.data.fixedTourDriverQuery);
    const dispatchDrivers = this.data.fixedTourDispatchDrivers || [];
    const sourceDrivers = dispatchDrivers.length ? dispatchDrivers : (this.data.drivers || []);
    const drivers = sourceDrivers.filter((driver) => {
      if (!needle) return true;
      return normalizeDailyMatchValue([driver.name, driver.display_name, driver.driver_code, driver.office].filter(Boolean).join(' ')).indexOf(needle) >= 0;
    });
    this.setData({ fixedTourVisibleDrivers: drivers });
  },

  applyFixedTourVehicleFilter() {
    const needle = normalizeDailyMatchValue(this.data.fixedTourVehicleQuery);
    const dispatchVehicles = this.data.fixedTourDispatchVehicles || [];
    const sourceVehicles = dispatchVehicles.length ? dispatchVehicles : (this.data.vehicles || []);
    const vehicles = sourceVehicles.map((vehicle) => ({
      ...vehicle,
      plate_tail: plateTail(vehicle.plate_number || vehicle.plate_no),
      distinction: [vehicle.vehicle_type, vehicle.office].filter(Boolean).join(' · ') || '车型待核'
    })).filter((vehicle) => {
      if (!needle) return true;
      return normalizeDailyMatchValue([vehicle.plate_number, vehicle.plate_no, vehicle.plate_tail, vehicle.vehicle_type, vehicle.office].filter(Boolean).join(' ')).indexOf(needle) >= 0;
    });
    this.setData({ fixedTourVisibleVehicles: vehicles });
  },

  refreshFixedTourSummary() {
    const route = this.data.fixedTourSelectedRoute;
    const driver = this.data.fixedTourSelectedDriver;
    const vehicle = this.data.fixedTourSelectedVehicle;
    const parts = [
      route && route.route_name,
      driver && (driver.name || driver.display_name),
      vehicle && (vehicle.plate_number || vehicle.plate_no)
    ].filter(Boolean);
    this.setData({ fixedTourSummary: parts.length ? parts.join(' · ') : '请选择线路、司机和车辆' });
  },

  openFixedTourPicker(e) {
    const type = String((e.currentTarget.dataset || {}).type || '');
    if (!['route', 'driver', 'vehicle'].includes(type)) return;
    const initial = { fixedTourPickerOpen: type, fixedTourMessage: '', fixedTourPickerNotice: '' };
    if (type === 'driver') {
      initial.fixedTourDriverQuery = '';
      initial.fixedTourDispatchDrivers = this.data.drivers || [];
    } else if (type === 'vehicle') {
      initial.fixedTourVehicleQuery = '';
      initial.fixedTourDispatchVehicles = this.data.vehicles || [];
    }
    this.setData(initial, () => {
      if (type === 'driver') this.applyFixedTourDriverFilter();
      if (type === 'vehicle') this.applyFixedTourVehicleFilter();
    });
    if (type === 'route') {
      this.applyFixedTourRouteFilter();
      return;
    }
    api.fixedTourDispatchOptions(
      this.data.fixedTourDate,
      this.data.fixedTourCurrentDraft && this.data.fixedTourCurrentDraft.id,
      this.data.fixedTourRouteId
    ).then((result) => {
      this.setData({
        fixedTourDispatchDrivers: result.drivers || [],
        fixedTourDispatchVehicles: result.vehicles || []
      }, () => {
        if (type === 'driver') this.applyFixedTourDriverFilter();
        else this.applyFixedTourVehicleFilter();
      });
    }).catch((error) => {
      const unavailable = Number(error && error.statusCode || 0) === 404;
      this.setData({
        fixedTourPickerNotice: unavailable
          ? '已显示当前可用列表；当日冲突状态需人工核对。'
          : `冲突状态读取失败：${api.errorMessage(error)}`
      });
    });
  },

  closeFixedTourPicker() {
    this.setData({ fixedTourPickerOpen: '', fixedTourPickerNotice: '' });
  },

  onFixedTourRouteSearch(e) {
    this.setData({ fixedTourRouteQuery: e.detail.value }, () => this.applyFixedTourRouteFilter());
  },

  restoreFixedTourEditor() {
    if (this.data.fixedTourEditor) return;
    try {
      const saved = wx.getStorageSync(FIXED_TOUR_EDITOR_STORAGE_KEY);
      if (saved && saved.editor && saved.view === 'editor') {
        this.setData({
          fixedTourView: saved.view,
          fixedTourEditor: saved.editor,
          fixedTourEditorDirty: true,
          fixedTourTripTypeIndex: saved.editor.trip_type === 'multi_day' ? 1 : 0
        });
        if (typeof wx.enableAlertBeforeUnload === 'function') wx.enableAlertBeforeUnload({ message: '日游行程尚未保存，确定离开吗？' });
      }
    } catch (error) {
      console.warn('[fixed-tour editor restore failed]', error);
    }
  },

  persistFixedTourEditor(editor, view = this.data.fixedTourView) {
    try { wx.setStorageSync(FIXED_TOUR_EDITOR_STORAGE_KEY, { editor, view }); } catch (error) { console.warn('[fixed-tour editor persist failed]', error); }
  },

  markFixedTourEditor(editor, view = this.data.fixedTourView) {
    this.setData({ fixedTourEditor: editor, fixedTourEditorDirty: true, fixedTourView: view, fixedTourMessage: '' });
    this.persistFixedTourEditor(editor, view);
    if (typeof wx.enableAlertBeforeUnload === 'function') wx.enableAlertBeforeUnload({ message: '日游行程尚未保存，确定离开吗？' });
  },

  clearFixedTourEditorPersistence() {
    try { wx.removeStorageSync(FIXED_TOUR_EDITOR_STORAGE_KEY); } catch (error) { console.warn('[fixed-tour editor clear failed]', error); }
    if (typeof wx.disableAlertBeforeUnload === 'function') wx.disableAlertBeforeUnload();
  },

  openNewFixedTourPreset() {
    const editor = blankFixedTourEditor('preset', this.data.fixedTourDate);
    this.setData({ fixedTourPickerOpen: '', fixedTourReturnToQuick: true, fixedTourTripTypeIndex: 0 }, () => {
      this.markFixedTourEditor(editor, 'editor');
    });
  },

  openCustomFixedTourDraft() {
    const editor = blankFixedTourEditor('custom', this.data.fixedTourDate);
    this.setData({ fixedTourPickerOpen: '', fixedTourReturnToQuick: true, fixedTourTripTypeIndex: 0 }, () => {
      this.markFixedTourEditor(editor, 'editor');
    });
  },

  editFixedTourPreset(e) {
    const route = (this.data.fixedTourRoutes || []).find((item) => String(item.id) === String(e.currentTarget.dataset.id));
    if (!route) return;
    const editor = fixedTourEditorFromRoute(route, 'preset', this.data.fixedTourDate);
    this.markFixedTourEditor(editor, 'editor');
    this.setData({ fixedTourTripTypeIndex: editor.trip_type === 'multi_day' ? 1 : 0 });
  },

  copyFixedTourPreset(e) {
    const route = (this.data.fixedTourRoutes || []).find((item) => String(item.id) === String(e.currentTarget.dataset.id));
    if (!route) return;
    const editor = fixedTourEditorFromRoute({ ...route, id: '', route_name: `${route.route_name}（副本）` }, 'preset', this.data.fixedTourDate);
    editor.route_id = '';
    editor.client_request_id = fixedTourRequestId('preset-copy');
    editor.days.forEach((day) => day.nodes.forEach((node) => { node.preset_node_id = ''; node.route_node_id = ''; }));
    this.markFixedTourEditor(editor, 'editor');
    this.setData({ fixedTourTripTypeIndex: editor.trip_type === 'multi_day' ? 1 : 0 });
  },

  deactivateFixedTourPreset(e) {
    const routeId = String(e.currentTarget.dataset.id || '');
    if (!routeId || this.data.fixedTourSubmitting) return;
    wx.showModal({
      title: '停用预设路线',
      content: '停用后不会影响已经创建的行程或历史PDF。',
      cancelText: '取消',
      confirmText: '停用',
      success: (res) => {
        if (!res.confirm) return;
        this.setData({ fixedTourSubmitting: true });
        api.setMobileFixedTourRouteStatus(routeId, 'inactive')
          .then(() => this.loadFixedTours())
          .catch((error) => this.setData({ fixedTourMessage: api.errorMessage(error) }))
          .finally(() => this.setData({ fixedTourSubmitting: false }));
      }
    });
  },

  openFixedTourPresetMenu(e) {
    const routeId = String(e.currentTarget.dataset.id || '');
    if (!routeId || this.data.fixedTourSubmitting) return;
    wx.showActionSheet({
      itemList: ['编辑预设', '另存副本', '停用预设'],
      success: (res) => {
        const event = { currentTarget: { dataset: { id: routeId } } };
        if (res.tapIndex === 0) this.editFixedTourPreset(event);
        else if (res.tapIndex === 1) this.copyFixedTourPreset(event);
        else this.deactivateFixedTourPreset(event);
      }
    });
  },

  useFixedTourPreset(e) {
    const routeId = String(e.currentTarget.dataset.id || '');
    if (!routeId || this.data.fixedTourSubmitting) return;
    const requestId = this.data.fixedTourPendingRequestId || fixedTourRequestId(`use-${routeId}`);
    this.setData({ fixedTourSubmitting: true, fixedTourPendingRequestId: requestId, fixedTourMessage: '' });
    api.createFixedTourCharterDraft({
      source_preset_id: routeId,
      business_start_date: this.data.fixedTourDate,
      client_request_id: requestId
    }).then((result) => this.openFixedTourDraft(result.draft))
      .catch((error) => this.setData({ fixedTourMessage: api.errorMessage(error) }))
      .finally(() => this.setData({ fixedTourSubmitting: false }));
  },

  openFixedTourDraft(draft) {
    if (!draft || !draft.route_snapshot) return;
    const route = { ...draft.route_snapshot, stops: draft.route_snapshot.stops || [] };
    const editor = fixedTourEditorFromRoute(route, 'draft', draft.business_start_date || this.data.fixedTourDate);
    editor.client_request_id = draft.client_request_id || editor.client_request_id;
    this.clearFixedTourEditorPersistence();
    this.setData({
      fixedTourView: 'editor',
      fixedTourEditor: editor,
      fixedTourEditorDirty: false,
      fixedTourCurrentDraft: draft,
      fixedTourPendingRequestId: '',
      fixedTourTripTypeIndex: editor.trip_type === 'multi_day' ? 1 : 0,
      fixedTourDraftAssociationText: draft.source_preset_id
        ? `已复制预设 #${draft.source_preset_id} V${draft.source_preset_version}；修改本次行程不会改变预设。`
        : '一次性私人订制，不会加入公司预设路线库。',
      fixedTourMessage: '包车文书草稿数据已建立；正式PDF审核将在 Phase 2C-2 接入。'
    });
  },

  backFixedTourList() {
    const leave = () => {
      this.clearFixedTourEditorPersistence();
      this.setData({ fixedTourView: 'quick', fixedTourPickerOpen: '', fixedTourEditor: null, fixedTourEditorDirty: false, fixedTourReturnToQuick: false, fixedTourMessage: '' });
      this.loadFixedTours();
    };
    if (!this.data.fixedTourEditorDirty) { leave(); return; }
    wx.showModal({ title: '放弃未保存修改？', content: '本机暂存内容将被清除。', cancelText: '继续编辑', confirmText: '放弃', success: (res) => { if (res.confirm) leave(); } });
  },

  onFixedTourEditorField(e) {
    const editor = JSON.parse(JSON.stringify(this.data.fixedTourEditor || {}));
    editor[e.currentTarget.dataset.key] = e.detail.value;
    this.markFixedTourEditor(editor);
  },

  onFixedTourEditorDate(e) {
    const editor = JSON.parse(JSON.stringify(this.data.fixedTourEditor || {}));
    editor.business_start_date = e.detail.value;
    this.setData({ fixedTourDate: e.detail.value });
    this.markFixedTourEditor(editor);
  },

  onFixedTourEditorTripType(e) {
    const nextType = Number(e.detail.value) === 1 ? 'multi_day' : 'day';
    const editor = JSON.parse(JSON.stringify(this.data.fixedTourEditor || {}));
    const apply = () => {
      editor.trip_type = nextType;
      if (nextType === 'day') editor.days = editor.days.slice(0, 1).map((day) => ({ ...day, day_index: 1, nodes: (day.nodes || []).map((node) => ({ ...node, day_index: 1 })) }));
      editor.duration_days = editor.days.length;
      this.setData({ fixedTourTripTypeIndex: nextType === 'multi_day' ? 1 : 0 });
      this.markFixedTourEditor(editor);
    };
    if (nextType === 'day' && editor.days.length > 1) {
      wx.showModal({ title: '切换为日归', content: '第2天及之后的地点将被移除。', cancelText: '取消', confirmText: '确认', success: (res) => { if (res.confirm) apply(); } });
      return;
    }
    apply();
  },

  onFixedTourNodeInput(e) {
    const dayIndex = Number(e.currentTarget.dataset.day);
    const nodeIndex = Number(e.currentTarget.dataset.node);
    const key = e.currentTarget.dataset.key;
    const editor = JSON.parse(JSON.stringify(this.data.fixedTourEditor || {}));
    if (!editor.days[dayIndex] || !editor.days[dayIndex].nodes[nodeIndex]) return;
    editor.days[dayIndex].nodes[nodeIndex][key] = e.detail.value;
    this.markFixedTourEditor(editor);
  },

  addFixedTourNode(e) {
    const dayIndex = Number(e.currentTarget.dataset.day);
    const editor = JSON.parse(JSON.stringify(this.data.fixedTourEditor || {}));
    if (!editor.days[dayIndex]) return;
    editor.days[dayIndex].nodes.push(blankFixedTourNode(Number(editor.days[dayIndex].day_index || dayIndex + 1)));
    this.markFixedTourEditor(editor);
  },

  moveFixedTourNode(e) {
    const dayIndex = Number(e.currentTarget.dataset.day);
    const nodeIndex = Number(e.currentTarget.dataset.node);
    const delta = Number(e.currentTarget.dataset.delta);
    const editor = JSON.parse(JSON.stringify(this.data.fixedTourEditor || {}));
    const nodes = editor.days[dayIndex] && editor.days[dayIndex].nodes;
    const target = nodeIndex + delta;
    if (!nodes || target < 0 || target >= nodes.length) return;
    [nodes[nodeIndex], nodes[target]] = [nodes[target], nodes[nodeIndex]];
    this.markFixedTourEditor(editor);
  },

  removeFixedTourNode(e) {
    const dayIndex = Number(e.currentTarget.dataset.day);
    const nodeIndex = Number(e.currentTarget.dataset.node);
    const editor = JSON.parse(JSON.stringify(this.data.fixedTourEditor || {}));
    if (!editor.days[dayIndex]) return;
    editor.days[dayIndex].nodes.splice(nodeIndex, 1);
    this.markFixedTourEditor(editor);
  },

  addFixedTourDay() {
    const editor = JSON.parse(JSON.stringify(this.data.fixedTourEditor || {}));
    const dayIndex = editor.days.length + 1;
    editor.trip_type = 'multi_day';
    editor.duration_days = dayIndex;
    editor.days.push({ day_index: dayIndex, nodes: [blankFixedTourNode(dayIndex), blankFixedTourNode(dayIndex)] });
    this.setData({ fixedTourTripTypeIndex: 1 });
    this.markFixedTourEditor(editor);
  },

  fixedTourEditorError(editor) {
    if (!String(editor && editor.route_name || '').trim()) return '请填写行程名称。';
    const nodes = (editor.days || []).reduce((all, day) => all.concat(day.nodes || []), []);
    if (nodes.length < 2) return '行程至少需要两个地点。';
    if (nodes.some((node) => !String(node.location_name || '').trim())) return '请补全所有地点名称。';
    const timePattern = /^(?:[01]\d|2[0-3]):[0-5]\d$/;
    for (const node of nodes) {
      const arrival = String(node.default_arrival_time || '').trim();
      const departure = String(node.default_departure_time || '').trim();
      if ((arrival && !timePattern.test(arrival)) || (departure && !timePattern.test(departure))) return '时间必须使用24小时制 HH:mm，例如 09:30。';
      if (arrival && departure && departure < arrival) return '同一地点的出发时间不能早于到达时间。';
    }
    return '';
  },

  saveAndUseFixedTourEditor() {
    const editor = this.data.fixedTourEditor;
    const validation = this.fixedTourEditorError(editor);
    if (validation) { this.setData({ fixedTourMessage: validation }); return; }
    if (this.data.fixedTourSubmitting) return;
    const route = fixedTourRoutePayload(editor);
    this.setData({ fixedTourSubmitting: true, fixedTourMessage: '' });
    const request = editor.mode === 'custom'
      ? api.createFixedTourCharterDraft({ route, business_start_date: editor.business_start_date, client_request_id: editor.client_request_id })
      : api.saveAndUseMobileFixedTourRoute({ route_id: editor.route_id || undefined, route, business_start_date: editor.business_start_date, client_request_id: editor.client_request_id });
    request.then((result) => {
      if (!this.data.fixedTourReturnToQuick) {
        this.openFixedTourDraft(result.draft);
        return;
      }
      const routeCard = fixedTourRouteCard(result.route || (result.draft && result.draft.route_snapshot) || route);
      this.clearFixedTourEditorPersistence();
      this.setData({
        fixedTourView: 'quick',
        fixedTourPickerOpen: '',
        fixedTourReturnToQuick: false,
        fixedTourEditor: null,
        fixedTourEditorDirty: false,
        fixedTourCurrentDraft: result.draft || null,
        fixedTourRouteId: String((result.route && result.route.id) || (result.draft && result.draft.source_preset_id) || ''),
        fixedTourSelectedRoute: routeCard,
        fixedTourMessage: editor.mode === 'custom'
          ? '私人订制已保存为本次行程，不会加入预设库。'
          : '路线已保存并自动选中；原有日期、司机和车辆选择已保留。'
      }, () => {
        this.refreshFixedTourSummary();
        this.loadFixedTours();
      });
    })
      .catch((error) => this.setData({ fixedTourMessage: api.errorMessage(error) }))
      .finally(() => this.setData({ fixedTourSubmitting: false }));
  },

  saveFixedTourCurrentDraft() {
    const editor = this.data.fixedTourEditor;
    const draft = this.data.fixedTourCurrentDraft;
    const validation = this.fixedTourEditorError(editor);
    if (validation) { this.setData({ fixedTourMessage: validation }); return; }
    if (!draft || this.data.fixedTourSubmitting) return;
    this.setData({ fixedTourSubmitting: true, fixedTourMessage: '' });
    api.updateFixedTourCharterDraft(draft.id, { business_start_date: editor.business_start_date, route: fixedTourRoutePayload(editor) })
      .then((result) => {
        this.clearFixedTourEditorPersistence();
        this.setData({ fixedTourCurrentDraft: result.draft, fixedTourEditorDirty: false, fixedTourMessage: '本次行程草稿已保存；原预设和历史订单未改变。' });
      })
      .catch((error) => this.setData({ fixedTourMessage: api.errorMessage(error) }))
      .finally(() => this.setData({ fixedTourSubmitting: false }));
  },

  onFixedTourQuery(e) { this.setData({ fixedTourQuery: e.detail.value }); },
  onFixedTourRouteQuery(e) { this.setData({ fixedTourRouteQuery: e.detail.value }); },
  onFixedTourDriverQuery(e) { this.setData({ fixedTourDriverQuery: e.detail.value }, () => this.applyFixedTourDriverFilter()); },
  onFixedTourVehicleQuery(e) { this.setData({ fixedTourVehicleQuery: e.detail.value }, () => this.applyFixedTourVehicleFilter()); },
  searchFixedTours() { this.loadFixedTours(); },
  onFixedTourDateChange(e) {
    this.setData({ fixedTourDate: e.detail.value, fixedTourGeneratedDocument: null }, () => this.loadFixedTours());
  },
  pickFixedTourRoute(e) {
    const route = this.data.fixedTourRoutes.find((item) => String(item.id) === String(e.currentTarget.dataset.id)) || this.data.fixedTourRoutes[Number(e.detail?.value ?? 0)];
    if (!route) return;
    const index = this.data.fixedTourRoutes.indexOf(route);
    this.setData({ fixedTourRouteIndex: index, fixedTourRouteWheel: [index], fixedTourRouteId: String(route.id), fixedTourSelectedRoute: route, fixedTourPickerOpen: '', fixedTourPriceHint: '', fixedTourGeneratedDocument: null }, () => {
      this.refreshFixedTourPresentation();
      this.refreshFixedTourPrice();
      this.refreshFixedTourSummary();
    });
  },
  pickFixedTourDriver(e) {
    const dispatchDrivers = this.data.fixedTourDispatchDrivers || [];
    const drivers = dispatchDrivers.length ? dispatchDrivers : (this.data.drivers || []);
    const driver = drivers.find((item) => String(item.id) === String(e.currentTarget.dataset.id)) || drivers[Number(e.detail?.value ?? 0)]; const index = drivers.indexOf(driver);
    if (driver) this.setData({ fixedTourDriverIndex: index, fixedTourDriverWheel: [index], fixedTourDriverId: String(driver.id), fixedTourSelectedDriver: driver, fixedTourPickerOpen: '', fixedTourGeneratedDocument: null }, () => this.refreshFixedTourSummary());
  },
  pickFixedTourVehicle(e) {
    const dispatchVehicles = this.data.fixedTourDispatchVehicles || [];
    const vehicles = dispatchVehicles.length ? dispatchVehicles : (this.data.vehicles || []);
    const vehicle = vehicles.find((item) => String(item.id) === String(e.currentTarget.dataset.id)) || vehicles[Number(e.detail?.value ?? 0)]; const index = vehicles.indexOf(vehicle);
    if (!vehicle) return;
    this.setData({ fixedTourVehicleIndex: index, fixedTourVehicleWheel: [index], fixedTourVehicleId: String(vehicle.id), fixedTourSelectedVehicle: vehicle, fixedTourPickerOpen: '', fixedTourPriceHint: '', fixedTourGeneratedDocument: null }, () => { this.refreshFixedTourPrice(); this.refreshFixedTourSummary(); });
  },

  ensureFixedTourDraftForGeneration() {
    const routeId = String(this.data.fixedTourRouteId || '');
    const businessDate = String(this.data.fixedTourDate || '');
    const current = this.data.fixedTourCurrentDraft;
    const currentRouteId = String(current && current.source_preset_id || '');
    const currentDate = String(current && (current.business_start_date || (current.order && current.order.order_date)) || '').slice(0, 10);
    const currentMatches = !!current && currentDate === businessDate && (
      (!routeId && !currentRouteId) || (routeId && currentRouteId === routeId)
    );
    if (currentMatches) return Promise.resolve(current);
    if (!routeId) return Promise.reject({ error: 'fixed_tour_route_not_found' });
    const requestId = this.data.fixedTourPendingRequestId || fixedTourRequestId(`dispatch-${routeId}`);
    this.setData({ fixedTourPendingRequestId: requestId });
    return api.createFixedTourCharterDraft({
      source_preset_id: routeId,
      business_start_date: businessDate,
      client_request_id: requestId
    }).then((result) => {
      const draft = result && result.draft;
      if (!draft || !draft.id) throw new Error('本次包车草稿创建结果无效');
      this.setData({ fixedTourCurrentDraft: draft, fixedTourPendingRequestId: '' });
      return draft;
    });
  },

  generateFixedTourDocuments() {
    if (this.data.fixedTourSubmitting) return;
    const route = this.data.fixedTourSelectedRoute;
    const driver = this.data.fixedTourSelectedDriver;
    const vehicle = this.data.fixedTourSelectedVehicle;
    if (!route) { wx.showToast({ title: '请选择线路', icon: 'none' }); return; }
    if (!driver) { wx.showToast({ title: '请选择司机', icon: 'none' }); return; }
    if (!vehicle) { wx.showToast({ title: '请选择车辆', icon: 'none' }); return; }
    this.setData({ fixedTourSubmitting: true, fixedTourMessage: '' });
    let activeDraft = null;
    this.ensureFixedTourDraftForGeneration()
      .then((draft) => {
        activeDraft = draft;
        return api.generateFixedTourDraftDocuments(draft.id, {
          driver_id: Number(driver.id),
          vehicle_id: Number(vehicle.id)
        });
      })
      .then((result) => {
        const document = result && result.document;
        const preview = result && result.preview || {};
        if (!document || !document.file_url) throw new Error('PDF 草稿生成结果无效');
        const validation = buildValidationPresentation(preview.validation_issues || []);
        const nodes = (preview.nodes || []).map((node) => ({
          ...node,
          type_label: nodeTypeLabel(node.node_type),
          time_text: `${String(node.planned_arrival_at || '').slice(0, 16).replace('T', ' ')}${node.planned_departure_at ? ` → ${String(node.planned_departure_at).slice(0, 16).replace('T', ' ')}` : ''}`
        }));
        const group = {
          key: result.group_key || '',
          driver_id: Number(driver.id),
          vehicle_id: Number(vehicle.id),
          driver: driver.name || driver.display_name || '司机',
          driver_name: driver.name || driver.display_name || '司机',
          vehicle: plateTail(vehicle.plate_number || vehicle.plate_no),
          vehicleFull: vehicle.plate_number || vehicle.plate_no || '车辆',
          plate_number: vehicle.plate_number || vehicle.plate_no || '',
          business_date: this.data.fixedTourDate,
          order_count: 1,
          orders: [],
          workflowStatus: 'draft',
          validation_issues: validation.raw
        };
        this.setData({
          fixedTourCurrentDraft: result.draft || activeDraft,
          fixedTourGeneratedDocument: document,
          fixedTourPendingRequestId: '',
          fixedTourMessage: `PDF草稿已生成 · ${Number(document.page_count || 0)}页`,
          dailyPdfReviewOpen: true,
          dailyPdfDraftOnly: true,
          dailyPdfSourceMode: 'fixed',
          dailyPdfCurrentDraftId: String((result.draft || activeDraft || {}).id || ''),
          dailyPdfDocumentTab: 'acceptance',
          dailyPdfReviewGroup: group,
          dailyPdfReviewDocument: document,
          dailyPdfReviewCanConfirm: false,
          dailyPdfPreviewUnavailable: false,
          dailyPdfReviewIndex: 0,
          dailyPdfReviewTotal: 1,
          dailyPdfValidationIssues: validation.issues,
          dailyPdfValidationRaw: validation.raw,
          dailyPdfSourceHash: preview.source_sha256 || '',
          dailyPdfDocumentRevision: preview.document_revision || '',
          dailyPdfIssueSummary: validation.summary,
          dailyPdfIssuesExpanded: false,
          dailyPdfNodes: nodes,
          dailyPdfFields: preview.document_fields || [],
          dailyPdfNodesExpanded: false,
          dailyNodeEditOpen: false,
          dailyNodeEditIndex: -1,
          dailyNodeEditForm: null
        });
        wx.showToast({ title: `PDF草稿已生成 · ${Number(document.page_count || 0)}页`, icon: 'success' });
      })
      .catch((error) => {
        const unavailable = Number(error && error.statusCode || 0) === 404 || error && error.backendError === 'fixed_tour_service_unavailable';
        const draftSaved = !!(activeDraft && activeDraft.id);
        this.setData({
          fixedTourCurrentDraft: activeDraft || this.data.fixedTourCurrentDraft,
          fixedTourMessage: unavailable
            ? `${draftSaved ? '本次行程草稿已保存；' : ''}当前 Trial 后端尚未部署 PDF 草稿生成接口，选择内容已保留。`
            : `${api.errorMessage(error)}；选择内容和本次草稿已保留，可安全重试。`
        });
        wx.showToast({ title: unavailable ? 'Trial 后端待更新' : 'PDF 草稿生成失败', icon: 'none' });
      })
      .finally(() => this.setData({ fixedTourSubmitting: false }));
  },

  openFixedTourGeneratedPdf() {
    const document = this.data.fixedTourGeneratedDocument;
    if (!document || !document.file_url) return;
    api.downloadAndOpenDocument(document.file_url).catch((error) => {
      console.warn('[fixed tour PDF reopen failed]', error);
      wx.showToast({ title: '文书已生成，打开失败，请重试', icon: 'none' });
    });
  },

  refreshFixedTourPrice() {
    const route = this.data.fixedTourRoutes.find((item) => String(item.id) === String(this.data.fixedTourRouteId));
    const vehicle = this.data.vehicles.find((item) => String(item.id) === String(this.data.fixedTourVehicleId));
    if (!route || !vehicle) return;
    const normalized = (value) => String(value || '').toLowerCase().replace(/[\s_-]/g, '');
    const priceRow = (route.prices || []).find((item) => normalized(item.vehicle_type) === normalized(vehicle.vehicle_type));
    const suggested = priceRow && priceRow.price_jpy !== undefined && priceRow.price_jpy !== null ? String(Math.round(Number(priceRow.price_jpy))) : '';
    const next = { fixedTourSuggestedPrice: suggested };
    if (!suggested) {
      if (!this.data.fixedTourPriceEdited) next.fixedTourEffectivePrice = '';
      next.fixedTourPriceHint = this.data.fixedTourPriceEdited && this.data.fixedTourEffectivePrice
        ? '该车型没有建议价；当前使用手动填写的实际金额。'
        : '该车型没有建议价，请填写实际金额。';
    } else if (!this.data.fixedTourPriceEdited) {
      next.fixedTourEffectivePrice = suggested;
      next.fixedTourPriceHint = '';
    } else {
      next.fixedTourPriceHint = '建议价已随路线或车型更新；当前保留手动实际金额。';
    }
    this.setData(next);
  },
  onFixedTourPrice(e) { this.setData({ fixedTourEffectivePrice: String(e.detail.value || '').replace(/\D/g, ''), fixedTourPriceEdited: true, fixedTourPriceHint: '' }); },
  useFixedTourSuggestedPrice() { this.setData({ fixedTourEffectivePrice: this.data.fixedTourSuggestedPrice, fixedTourPriceEdited: false, fixedTourPriceHint: '' }); },
  goFixedTourStep(e) { const step=Number(e.currentTarget.dataset.step); if (step < this.data.fixedTourStep) this.setData({ fixedTourStep: step }); },
  buildFixedTourDraft() {
    const { fixedTourRouteId, fixedTourDriverId, fixedTourVehicleId, fixedTourEffectivePrice } = this.data;
    if (!fixedTourRouteId || !fixedTourDriverId || !fixedTourVehicleId) { this.setData({ fixedTourMessage:'请选择路线、司机和车辆。' }); return; }
    if (!fixedTourEffectivePrice) { this.setData({ fixedTourMessage:'请填写实际金额后继续。' }); return; }
    this.setData({ fixedTourDraftReady:true, fixedTourStep:2, fixedTourMessage:'' });
  },
  continueFixedTourConfirm() { this.setData({ fixedTourStep:3, fixedTourEditingSegmentIndex: -1 }, () => this.updateFixedTourDocumentCounts()); },
  fixedTourSegmentLabel(type) {
    const index = this.data.fixedTourSegmentTypes.indexOf(type);
    return this.data.fixedTourSegmentTypeLabels[index] || '自定义';
  },
  refreshFixedTourPresentation(rows = this.data.fixedTourSegments) {
    const route = this.data.fixedTourSelectedRoute;
    const stops = (route && route.stops) || [];
    const first = stops[0] && stops[0].location_name || '';
    const last = stops.length && stops[stops.length - 1].location_name || '';
    const routePreview = route ? `${route.default_start_time || '时间待定'}–${route.default_end_time || '时间待定'} · ${stops.map((item) => item.location_name).filter(Boolean).join(' → ')}` : '';
    const timeline = stops.map((item, index) => ({ ...item, display_time: item.default_arrival_time || item.default_departure_time || (index === 0 ? route.default_start_time : index === stops.length - 1 ? route.default_end_time : '') }));
    const segments = rows.map((item) => ({ ...item, typeLabel: this.fixedTourSegmentLabel(item.type), connection_warning: item.position === 'pre' && item.dropoff_location && first && item.dropoff_location !== first ? '行程连接需确认：前置终点与主路线首点不同。' : item.position === 'post' && item.pickup_location && last && item.pickup_location !== last ? '行程连接需确认：后置起点与主路线末点不同。' : '' }));
    const segmentSummary = (position) => segments.filter((item) => item.position === position).map((item) => `${item.pickup_location || '未填起点'}→${item.dropoff_location || '未填终点'}`).join('；') || '无';
    this.setData({ fixedTourSegments: segments, fixedTourRoutePreview: routePreview, fixedTourTimelineStops: timeline, fixedTourPreSummary: segmentSummary('pre'), fixedTourPostSummary: segmentSummary('post') });
  },
  addFixedTourSegment(e) {
    const position = e.currentTarget.dataset.position || 'pre';
    const stops = (this.data.fixedTourSelectedRoute && this.data.fixedTourSelectedRoute.stops) || [];
    const mainEdge = position === 'pre' ? (stops[0] && stops[0].location_name || '') : (stops[stops.length - 1] && stops[stops.length - 1].location_name || '');
    const type = position === 'pre' ? 'airport_pickup' : 'airport_dropoff';
    const row = { position, type, typeLabel: this.fixedTourSegmentLabel(type), pickup_location: position === 'post' ? mainEdge : '', dropoff_location: position === 'pre' ? mainEdge : '', start_time: '', end_time: '', flight_number: '', terminal: '', note: '', same_passenger: true, connection_warning: '' };
    const rows = [...this.data.fixedTourSegments, row];
    this.setData({ fixedTourSegments: rows, fixedTourEditingSegmentIndex: rows.length - 1 }, () => { this.refreshFixedTourPresentation(rows); this.updateFixedTourDocumentCounts(); });
  },
  onFixedTourSegmentInput(e) { const i = Number(e.currentTarget.dataset.index); const key = e.currentTarget.dataset.key; const rows = [...this.data.fixedTourSegments]; rows[i] = { ...rows[i], [key]: e.detail.value }; this.refreshFixedTourPresentation(rows); },
  onFixedTourSegmentType(e) { const i = Number(e.currentTarget.dataset.index); const type = this.data.fixedTourSegmentTypes[Number(e.detail.value)] || 'custom'; const rows = [...this.data.fixedTourSegments]; rows[i] = { ...rows[i], type, typeLabel: this.fixedTourSegmentLabel(type) }; this.refreshFixedTourPresentation(rows); },
  toggleFixedTourSamePassenger(e) { const i = Number(e.currentTarget.dataset.index); const rows = [...this.data.fixedTourSegments]; rows[i] = { ...rows[i], same_passenger: e.detail ? !!e.detail.value : !rows[i].same_passenger }; this.setData({ fixedTourSegments: rows }, () => this.updateFixedTourDocumentCounts()); },
  fillFixedTourAirport(e) { const i = Number(e.currentTarget.dataset.index); const place = e.currentTarget.dataset.place; const rows = [...this.data.fixedTourSegments]; const row = rows[i]; rows[i] = { ...row, [row.type === 'airport_dropoff' ? 'dropoff_location' : 'pickup_location']: place }; this.refreshFixedTourPresentation(rows); },
  editFixedTourSegment(e) { this.setData({ fixedTourEditingSegmentIndex: Number(e.currentTarget.dataset.index) }); },
  closeFixedTourSegmentEditor() { this.setData({ fixedTourEditingSegmentIndex: -1 }); },
  removeFixedTourSegment(e) { const i = Number(e.currentTarget.dataset.index); this.setData({ fixedTourSegments: this.data.fixedTourSegments.filter((_, index) => index !== i), fixedTourEditingSegmentIndex: -1 }, () => this.updateFixedTourDocumentCounts()); },
  updateFixedTourDocumentCounts() {
    const acceptance = 1 + this.data.fixedTourSegments.filter((item) => !item.same_passenger).length;
    this.setData({ fixedTourAcceptanceCount: acceptance, fixedTourInstructionCount: 1 });
  },
  createFixedTourRun() {
    const { fixedTourRouteId, fixedTourDriverId, fixedTourVehicleId, fixedTourDate } = this.data;
    if (!fixedTourRouteId || !fixedTourDriverId || !fixedTourVehicleId) { wx.showToast({ title: '请选择司机、车辆和路线', icon: 'none' }); return; }
    if (this.data.fixedTourSubmitting) return; this.setData({ fixedTourSubmitting:true });
    api.materializeFixedTour({ route_id: fixedTourRouteId, driver_id: fixedTourDriverId, vehicle_id: fixedTourVehicleId, date: fixedTourDate, segments: this.data.fixedTourSegments, effective_price_jpy: this.data.fixedTourEffectivePrice })
      .then((result) => {
        wx.showToast({ title: '已生成，进入PDF审核', icon: 'success' });
        this.setData({ workbenchMode: 'daily', dailyDate: fixedTourDate }, () => {
          const run = result && result.run;
          this.loadAll().then(() => {
            if (run && run.assignment_id) this.openDailyPdfByKey(`${fixedTourDate}:${fixedTourDriverId}:${fixedTourVehicleId}`, true);
          });
        });
      })
      .catch((error) => { const raw = api.errorMessage(error); const message = ({ fixed_tour_price_not_configured: '请填写实际金额后重试。', missing_route_vehicle_price: '该车型没有建议价，请填写实际金额后重试。', fixed_tour_effective_price_invalid: '实际金额必须是大于或等于 0 的整数日元。', fixed_tour_segment_locations_required: '前后置行程需要填写乘车地点和降车地点。', fixed_tour_segment_time_invalid: '前后置行程的结束时间不能早于开始时间。', segment_time_order: '前后置行程时间顺序不正确。', operations_business_area_confirmation: '营业区域需要确认后才能生成。', operations_business_area_validation: '营业区域校验未通过，请确认路线端点后重试。', fixed_tour_assignment_conflict: '司机或车辆已有任务，请更换后重试。', fixed_tour_segment_assignment_conflict: '司机或车辆已有任务，前后置行程无法加入。' })[raw] || raw || '校验失败，请检查必填字段。'; this.setData({ fixedTourMessage: message }); }).finally(() => this.setData({ fixedTourSubmitting:false }));
  },

  openDailyImport() {
    const tabBar = typeof this.getTabBar === 'function' ? this.getTabBar() : null;
    if (tabBar) tabBar.setData({ visible: false });
    this.setData({
      dailyImportOpen: true,
      dailyImportDefaultDate: this.data.dailyImportDefaultDate || this.data.dailyDate,
      importMode: 'daily',
      dailyMessage: '',
      conflictText: ''
    });
  },

  closeDailyImport() {
    if (this.data.dailyImportSubmitting) return;
    this.setData({ dailyImportOpen: false }, () => this.refreshTabBar());
  },

  onDailyDateChange(e) {
    this.setData({ dailyDate: e.detail.value, dailySelectedGroupKeys: [] }, () => this.loadAll());
  },

  previousDailyDate() {
    this.setData({ dailyDate: shiftIsoDate(this.data.dailyDate, -1), dailySelectedGroupKeys: [] }, () => this.loadAll());
  },

  nextDailyDate() {
    this.setData({ dailyDate: shiftIsoDate(this.data.dailyDate, 1), dailySelectedGroupKeys: [] }, () => this.loadAll());
  },

  selectDailyStatus(e) {
    this.setData({ dailyStatusFilter: (e.currentTarget.dataset || {}).status || 'all' }, () => this.refreshDailyRunGroups());
  },

  refreshDailyRunGroups() {
    const result = this.decorateServerRunGroups(this.data.serverRunGroups || []);
    this.setData({ dailyRunGroups: result.groups, dailyRunSummary: result.summary });
  },

  decorateServerRunGroups(groups) {
    const selected = this.data.dailySelectedGroupKeys || [];
    const all = (groups || []).map((group) => {
      const orders = (group.orders || []).map((order) => ({
        ...order,
        orderId: order.order_id,
        assignmentId: order.assignment_id,
        time: order.start_time || '--:--',
        route: `${order.pickup_location || '待确认'} → ${order.dropoff_location || '待确认'}`,
        businessArea: order.operations_business_area || group.driver_office || '未设定',
        areaWarning: Boolean(order.area_warning),
        areaRoute: order.area_route || '',
        reviewed: order.run_confirmation_status === 'confirmed'
      }));
      const workflowStatus = group.workflow_status || 'draft_ready';
      const status = workflowStatus === 'ready' ? 'ready' : (workflowStatus === 'published' ? 'published' : 'pending');
      return {
        ...group,
        driver: group.driver_name || '未定司机',
        vehicle: plateTail(group.plate_number),
        vehicleFull: group.plate_number || '未定车辆',
        orders,
        visibleOrders: orders.slice(0, 3),
        hiddenCount: Math.max(0, orders.length - 3),
        areaWarningCount: orders.filter((order) => order.areaWarning).length,
        reviewedCount: group.confirmed_count || 0,
        status,
        workflowStatus,
        statusText: group.workflow_status_text || (group.confirmation_status === 'confirmed' ? '订单已确认' : `${group.confirmed_count || 0}/${group.order_count || orders.length} 已确认`),
        selected: selected.indexOf(group.key) >= 0,
        pdfReady: group.confirmation_status === 'confirmed',
        canReviewOrders: false,
        canGeneratePdf: ['draft_ready', 'needs_data', 'stale'].indexOf(workflowStatus) >= 0,
        canReviewPdf: ['draft_ready', 'needs_data', 'stale', 'pdf_pending', 'ready'].indexOf(workflowStatus) >= 0,
        canPublish: false,
        canOpenPdf: true,
        documentStatusText: group.document_status === 'published' ? `已发布 V${group.latest_document && group.latest_document.version}` : (group.document_status === 'reviewed' ? `已确认 V${group.latest_document && group.latest_document.version}` : (group.document_status === 'generated' ? `待确认 V${group.latest_document && group.latest_document.version}` : (group.document_status === 'stale' ? 'PDF 已作废' : '')))
      };
    });
    const filter = this.data.dailyStatusFilter || 'all';
    const visible = filter === 'all' ? all : all.filter((group) => group.status === filter);
    return {
      groups: visible,
      allGroups: all,
      summary: {
        vehicles: all.length,
        orders: all.reduce((sum, group) => sum + group.orders.length, 0),
        published: all.filter((group) => group.workflowStatus === 'published').length,
        pending: all.filter((group) => group.workflowStatus !== 'published').length
      }
    };
  },

  toggleDailyGroupSelection(e) {
    const key = String((e.currentTarget.dataset || {}).key || '');
    if (!key) return;
    const selected = (this.data.dailySelectedGroupKeys || []).slice();
    const index = selected.indexOf(key);
    if (index >= 0) selected.splice(index, 1);
    else selected.push(key);
    this.setData({ dailySelectedGroupKeys: selected }, () => this.refreshDailyRunGroups());
  },

  openDailyReview(e) {
    const key = String((e.currentTarget.dataset || {}).key || '');
    const group = (this.data.dailyRunGroups || []).find((item) => item.key === key);
    if (!group || !group.orders.length) return;
    this.showDailyReviewOrder(group, 0);
  },

  showDailyReviewOrder(group, orderIndex) {
    const safeIndex = Math.max(0, Math.min(Number(orderIndex || 0), group.orders.length - 1));
    const order = group.orders[safeIndex];
    this.setData({
      dailyReviewOpen: true,
      dailyReviewGroupKey: group.key,
      dailyReviewOrderIndex: safeIndex,
      dailyReviewEdit: false,
      dailyReviewGroup: group,
      dailyReviewOrder: order,
      dailyReviewConfirmedCount: group.orders.filter((item) => item.reviewed).length,
      dailyReviewForm: {
        order_date: order.order_date || this.data.dailyDate,
        start_time: order.start_time || '',
        business_area: order.businessArea || '未设定',
        order_type: order.order_type || '',
        pickup_location: order.pickup_location || '',
        dropoff_location: order.dropoff_location || '',
        price: Number(order.price || 0) > 0 ? String(order.price) : (order.recommended_price ? String(order.recommended_price) : '')
      }
    });
  },

  closeDailyReview() {
    this.setData({
      dailyReviewOpen: false,
      dailyReviewEdit: false,
      dailyReviewGroup: null,
      dailyReviewOrder: null,
      dailyReviewForm: blankDailyReviewForm()
    });
  },

  toggleDailyReviewEdit() {
    this.setData({ dailyReviewEdit: !this.data.dailyReviewEdit });
  },

  onDailyReviewField(e) {
    const field = (e.currentTarget.dataset || {}).field;
    if (!field) return;
    this.setData({ [`dailyReviewForm.${field}`]: e.detail.value });
  },

  onDailyReviewDate(e) {
    this.setData({ 'dailyReviewForm.order_date': e.detail.value });
  },

  onDailyReviewTime(e) {
    this.setData({ 'dailyReviewForm.start_time': e.detail.value });
  },

  onDailyReviewArea(e) {
    this.setData({ 'dailyReviewForm.business_area': DAILY_BUSINESS_AREAS[Number(e.detail.value)] || DAILY_BUSINESS_AREAS[0] });
  },

  onDailyReviewType(e) {
    this.setData({ 'dailyReviewForm.order_type': DAILY_ORDER_TYPES[Number(e.detail.value)] || DAILY_ORDER_TYPES[0] });
  },

  selectDailyReviewOrder(e) {
    const index = Number((e.currentTarget.dataset || {}).index || 0);
    const group = this.data.dailyReviewGroup;
    if (group) this.showDailyReviewOrder(group, index);
  },

  previousDailyReviewOrder() {
    const group = this.data.dailyReviewGroup;
    if (!group) return;
    this.showDailyReviewOrder(group, this.data.dailyReviewOrderIndex - 1);
  },

  nextDailyReviewOrder() {
    const group = this.data.dailyReviewGroup;
    if (!group) return;
    this.showDailyReviewOrder(group, this.data.dailyReviewOrderIndex + 1);
  },

  confirmDailyReview() {
    const order = this.data.dailyReviewOrder;
    if (!order || !order.orderId) return;
    const form = this.data.dailyReviewForm || {};
    const payload = {
      order_id: order.orderId,
      order_date: form.order_date,
      start_time: form.start_time,
      operations_business_area: form.business_area,
      order_type: form.order_type,
      pickup_location: form.pickup_location,
      dropoff_location: form.dropoff_location,
      price: form.price,
      pdf_edit: true
    };
    let regeneratedGroupKey = this.data.dailyReviewGroupKey;
    this.setData({ loading: true, conflictText: '' });
    api.confirmRunOrder(payload)
      .then((result) => {
        const savedOrder = result && result.order;
        const activeGroup = this.data.dailyReviewGroup || {};
        const savedDate = (savedOrder && savedOrder.order_date) || payload.order_date;
        regeneratedGroupKey = `${savedDate}:${activeGroup.driver_id}:${activeGroup.vehicle_id}`;
        return api.generateRunDocument(regeneratedGroupKey);
      })
      .then((res) => {
        const group = this.data.dailyReviewGroup;
        const currentIndex = this.data.dailyReviewOrderIndex;
        const updatedOrders = (group.orders || []).map((item, index) => index === currentIndex ? {
          ...item,
          order_date: payload.order_date,
          start_time: payload.start_time,
          time: payload.start_time,
          operations_business_area: payload.operations_business_area,
          businessArea: payload.operations_business_area,
          order_type: payload.order_type,
          pickup_location: payload.pickup_location,
          dropoff_location: payload.dropoff_location,
          route: `${payload.pickup_location || '待确认'} → ${payload.dropoff_location || '待确认'}`,
          price: payload.price,
          reviewed: false
        } : item);
        const updatedGroup = { ...group, key: regeneratedGroupKey, business_date: payload.order_date, orders: updatedOrders };
        const document = res && res.document;
        this.setData({
          loading: false,
          dailyReviewOpen: false,
          dailyReviewEdit: false,
          dailyReviewGroup: null,
          dailyReviewOrder: null,
          dailyPdfReviewOpen: true,
          dailyPdfDraftOnly: false,
          dailyPdfSourceMode: 'daily',
          dailyPdfCurrentDraftId: '',
          dailyPdfDocumentTab: 'acceptance',
          dailyReviewGroupKey: regeneratedGroupKey,
          dailyPdfReviewGroup: updatedGroup,
          dailyPdfReviewDocument: document,
          dailyPdfReviewCanConfirm: true,
          dailyPdfPreviewUnavailable: false,
          dailyPdfValidationIssues: [],
          dailyPdfValidationRaw: [],
          dailyPdfIssueSummary: [],
          dailyPdfIssuesExpanded: false,
          dailyPdfNodesExpanded: false
        });
        wx.showToast({ title: '已保存并重生成', icon: 'success' });
        this.loadAll();
      })
      .catch((err) => {
        console.warn('[daily review update failed]', err);
        this.setData({ loading: false, conflictText: (err && err.error) || '保存失败，请检查后端连接。' });
      });
  },

  openDailyPdf(e) {
    const eventKey = String(e && e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.key || '');
    const key = eventKey || (this.data.dailySelectedGroupKeys || [])[0];
    this.openDailyPdfByKey(key, false);
  },

  openDailyPdfByKey(key, autoOpen) {
    const decorated = this.decorateServerRunGroups(this.data.serverRunGroups || []);
    const groups = decorated.allGroups || [];
    const group = groups.find((item) => item.key === key);
    if (!group) {
      wx.showToast({ title: '请先选择车辆', icon: 'none' });
      return;
    }
    const groupIndex = groups.findIndex((item) => item.key === key);
    this.setData({ loading: true, dailyPdfLoadingKey: key });
    api.generateRunDocument(key)
      .then((res) => api.runDocumentPreview(key)
        .then((previewRes) => [res, previewRes])
        .catch((error) => {
          if (Number(error && error.statusCode || 0) === 404) {
            console.warn('[run document preview unavailable]', error);
            return [res, { preview: null, preview_unavailable: true }];
          }
          throw error;
        }))
      .then(([res, previewRes]) => {
        const document = res && res.document;
        if (!document || !document.file_url) throw new Error('PDF 生成结果无效');
        const preview = previewRes && previewRes.preview || {};
        const previewUnavailable = !!(previewRes && previewRes.preview_unavailable);
        const validation = buildValidationPresentation([...(group.validation_issues || []), ...(preview.validation_issues || [])]);
        const nodes = (preview.nodes || []).map((node) => ({
          ...node,
          type_label: nodeTypeLabel(node.node_type),
          time_text: `${String(node.planned_arrival_at || '').slice(0, 16).replace('T', ' ')}${node.planned_departure_at ? ` → ${String(node.planned_departure_at).slice(0, 16).replace('T', ' ')}` : ''}`
        }));
        this.setData({
          dailyPdfReviewOpen: true,
          dailyPdfDraftOnly: false,
          dailyPdfReviewGroup: group,
          dailyPdfReviewDocument: document,
          dailyPdfReviewCanConfirm: !previewUnavailable && document.status !== 'published' && !validation.raw.length,
          dailyPdfPreviewUnavailable: previewUnavailable,
          dailyPdfReviewIndex: groupIndex,
          dailyPdfReviewTotal: groups.length,
          dailyPdfValidationIssues: validation.issues,
          dailyPdfValidationRaw: validation.raw,
          dailyPdfIssueSummary: validation.summary,
          dailyPdfSourceHash: preview.source_sha256 || '',
          dailyPdfDocumentRevision: preview.document_revision || '',
          dailyPdfIssuesExpanded: false,
          dailyPdfNodes: nodes,
          dailyPdfFields: preview.document_fields || [],
          dailyPdfNodesExpanded: false,
          dailyNodeEditOpen: false,
          dailyNodeEditIndex: -1,
          dailyNodeEditForm: null
        });
        return autoOpen ? api.downloadAndOpenDocument(document.file_url) : null;
      })
      .then(() => this.setData({ loading: false, dailyPdfLoadingKey: '' }))
      .catch((err) => {
        console.warn('[run document open failed]', err);
        this.setData({ loading: false, dailyPdfLoadingKey: '' });
        wx.showToast({ title: api.errorMessage(err) || 'PDF 打开失败', icon: 'none' });
      });
  },

  closeDailyPdfReview() {
    this.setData({
      dailyPdfReviewOpen: false,
      dailyPdfDraftOnly: false,
      dailyPdfSourceMode: '',
      dailyPdfCurrentDraftId: '',
      dailyPdfDocumentTab: 'acceptance',
      dailyPdfReviewGroup: null,
      dailyPdfReviewDocument: null,
      dailyPdfReviewCanConfirm: false,
      dailyPdfPreviewUnavailable: false,
      dailyPdfValidationIssues: [],
      dailyPdfValidationRaw: [],
      dailyPdfIssueSummary: [],
      dailyPdfIssuesExpanded: false,
      dailyPdfNodes: [],
      dailyPdfFields: [],
      dailyPdfSourceHash: '',
      dailyPdfDocumentRevision: '',
      dailyPdfNodesExpanded: false,
      dailyNodeEditOpen: false,
      dailyNodeEditIndex: -1,
      dailyNodeEditForm: null,
      dailyFieldEditOpen: false,
      dailyFieldEditIndex: -1,
      dailyFieldEditForm: null
    });
  },

  toggleDailyPdfIssues() {
    this.setData({ dailyPdfIssuesExpanded: !this.data.dailyPdfIssuesExpanded });
  },

  toggleDailyPdfNodes() {
    this.setData({ dailyPdfNodesExpanded: !this.data.dailyPdfNodesExpanded });
  },

  switchDailyPdfDocumentTab(e) {
    const tab = String(e.currentTarget.dataset.tab || 'acceptance');
    if (tab === 'acceptance' || tab === 'dispatch') this.setData({ dailyPdfDocumentTab: tab });
  },

  openDailyFieldEdit(e) {
    const index = Number(e && e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.index);
    const field = (this.data.dailyPdfFields || [])[index];
    if (!field || !field.editable) return;
    this.setData({
      dailyFieldEditOpen: true,
      dailyFieldEditIndex: index,
      dailyFieldEditForm: { ...field, value: field.value == null ? '' : String(field.value) }
    });
  },

  closeDailyFieldEdit() {
    this.setData({ dailyFieldEditOpen: false, dailyFieldEditIndex: -1, dailyFieldEditForm: null });
  },

  onDailyFieldInput(e) {
    this.setData({ 'dailyFieldEditForm.value': e.detail.value });
  },

  saveDailyFieldEdit() {
    const group = this.data.dailyPdfReviewGroup || {};
    const form = this.data.dailyFieldEditForm || {};
    if (!group.key || !form.field_id) return;
    this.setData({ loading: true });
    api.updateRunDocumentField({
      group_key: group.key,
      field_id: form.field_id,
      value: form.value,
      expected_source_hash: this.data.dailyPdfSourceHash || ''
    })
      .then((result) => {
        const preview = result && result.preview || {};
        return Promise.all([api.generateRunDocument(group.key), Promise.resolve(preview)]);
      })
      .then(([documentResult, preview]) => {
        const document = documentResult && documentResult.document;
        const validation = buildValidationPresentation(preview.validation_issues || []);
        const nodes = (preview.nodes || []).map((node) => ({
          ...node,
          type_label: nodeTypeLabel(node.node_type),
          time_text: `${String(node.planned_arrival_at || '').slice(0, 16).replace('T', ' ')}${node.planned_departure_at ? ` → ${String(node.planned_departure_at).slice(0, 16).replace('T', ' ')}` : ''}`
        }));
        this.setData({
          loading: false,
          dailyPdfReviewDocument: document,
          fixedTourGeneratedDocument: this.data.dailyPdfDraftOnly ? document : this.data.fixedTourGeneratedDocument,
          dailyPdfReviewCanConfirm: !!document && document.status !== 'published' && !validation.raw.length,
          dailyPdfValidationIssues: validation.issues,
          dailyPdfValidationRaw: validation.raw,
          dailyPdfIssueSummary: validation.summary,
          dailyPdfSourceHash: preview.source_sha256 || '',
          dailyPdfDocumentRevision: preview.document_revision || '',
          dailyPdfNodes: nodes,
          dailyPdfFields: preview.document_fields || [],
          dailyFieldEditOpen: false,
          dailyFieldEditIndex: -1,
          dailyFieldEditForm: null
        });
        wx.showToast({ title: '字段已保存并生成新版', icon: 'success' });
        this.loadAll();
      })
      .catch((err) => {
        console.warn('[run document field update failed]', err);
        const conflict = String(err && (err.backendError || err.error) || '') === 'document_revision_conflict';
        this.setData({ loading: false });
        wx.showToast({ title: conflict ? '文书已被更新，请重新打开核对' : (api.errorMessage(err) || '字段保存失败，输入已保留'), icon: 'none' });
      });
  },

  openDailyNodeEdit(e) {
    const index = Number(e && e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.index);
    const node = (this.data.dailyPdfNodes || [])[index];
    if (!node) return;
    const fallbackDate = (this.data.dailyPdfReviewGroup || {}).business_date || this.data.dailyDate;
    const arrival = splitNodeDateTime(node.planned_arrival_at, fallbackDate);
    const departure = splitNodeDateTime(node.planned_departure_at, fallbackDate);
    this.setData({
      dailyNodeEditOpen: true,
      dailyNodeEditIndex: index,
      dailyNodeEditForm: {
        route_node_id: node.route_node_id,
        type_label: node.type_label,
        planned_location: node.planned_location || '',
        arrival_date: arrival.date,
        arrival_time: arrival.time,
        departure_date: departure.date,
        departure_time: departure.time,
        editable_arrival: !!node.editable_arrival,
        editable_departure: !!node.editable_departure
      }
    });
  },

  closeDailyNodeEdit() {
    this.setData({ dailyNodeEditOpen: false, dailyNodeEditIndex: -1, dailyNodeEditForm: null });
  },

  onDailyNodeLocation(e) {
    this.setData({ 'dailyNodeEditForm.planned_location': e.detail.value });
  },

  onDailyNodeDate(e) {
    const field = String(e.currentTarget.dataset.field || '');
    if (field) this.setData({ [`dailyNodeEditForm.${field}`]: e.detail.value });
  },

  onDailyNodeTime(e) {
    const field = String(e.currentTarget.dataset.field || '');
    if (field) this.setData({ [`dailyNodeEditForm.${field}`]: e.detail.value });
  },

  saveDailyNodeEdit() {
    const group = this.data.dailyPdfReviewGroup || {};
    const form = this.data.dailyNodeEditForm || {};
    if (!group.key || !form.route_node_id || !String(form.planned_location || '').trim()) {
      wx.showToast({ title: '请填写行程地点', icon: 'none' });
      return;
    }
    const payload = {
      group_key: group.key,
      route_node_id: form.route_node_id,
      planned_location: String(form.planned_location || '').trim(),
      expected_source_hash: this.data.dailyPdfSourceHash || ''
    };
    if (form.editable_arrival) payload.planned_arrival_at = composeNodeDateTime(form.arrival_date, form.arrival_time);
    if (form.editable_departure) payload.planned_departure_at = composeNodeDateTime(form.departure_date, form.departure_time);
    this.setData({ loading: true });
    api.updateRunDocumentNode(payload)
      .then((result) => {
        const preview = result && result.preview || {};
        return Promise.all([api.generateRunDocument(group.key), Promise.resolve(preview)]);
      })
      .then(([documentResult, preview]) => {
        const document = documentResult && documentResult.document;
        const validation = buildValidationPresentation(preview.validation_issues || []);
        const nodes = (preview.nodes || []).map((node) => ({
          ...node,
          type_label: nodeTypeLabel(node.node_type),
          time_text: `${String(node.planned_arrival_at || '').slice(0, 16).replace('T', ' ')}${node.planned_departure_at ? ` → ${String(node.planned_departure_at).slice(0, 16).replace('T', ' ')}` : ''}`
        }));
        this.setData({
          loading: false,
          dailyPdfReviewDocument: document,
          fixedTourGeneratedDocument: this.data.dailyPdfDraftOnly ? document : this.data.fixedTourGeneratedDocument,
          fixedTourMessage: this.data.dailyPdfDraftOnly && document ? `PDF草稿已生成 · ${Number(document.page_count || 0)}页` : this.data.fixedTourMessage,
          dailyPdfReviewCanConfirm: !!document && document.status !== 'published' && !validation.raw.length,
          dailyPdfPreviewUnavailable: false,
          dailyPdfValidationIssues: validation.issues,
          dailyPdfValidationRaw: validation.raw,
          dailyPdfIssueSummary: validation.summary,
          dailyPdfSourceHash: preview.source_sha256 || '',
          dailyPdfDocumentRevision: preview.document_revision || '',
          dailyPdfNodes: nodes,
          dailyPdfFields: preview.document_fields || [],
          dailyNodeEditOpen: false,
          dailyNodeEditIndex: -1,
          dailyNodeEditForm: null
        });
        wx.showToast({ title: '已保存并生成新版', icon: 'success' });
        this.loadAll();
      })
      .catch((err) => {
        console.warn('[run document node update failed]', err);
        this.setData({ loading: false });
        wx.showToast({ title: api.errorMessage(err) || '节点保存失败', icon: 'none' });
      });
  },

  editDailyPdf() {
    const group = this.data.dailyPdfReviewGroup;
    if (!group || !(group.orders || []).length) return;
    this.showDailyReviewOrder(group, 0);
    this.setData({ dailyReviewEdit: true });
  },

  previousDailyPdfDriver() {
    const groups = this.decorateServerRunGroups(this.data.serverRunGroups || []).allGroups || [];
    const index = Math.max(0, Number(this.data.dailyPdfReviewIndex || 0) - 1);
    if (groups[index]) this.openDailyPdfByKey(groups[index].key, false);
  },

  nextDailyPdfDriver() {
    const groups = this.decorateServerRunGroups(this.data.serverRunGroups || []).allGroups || [];
    const index = Math.min(groups.length - 1, Number(this.data.dailyPdfReviewIndex || 0) + 1);
    if (groups[index]) this.openDailyPdfByKey(groups[index].key, false);
  },

  openGeneratedDailyPdf() {
    const document = this.data.dailyPdfReviewDocument;
    if (!document || !document.file_url) return;
    api.downloadAndOpenDocument(document.file_url).catch((err) => {
      wx.showToast({ title: (err && err.error) || 'PDF 打开失败', icon: 'none' });
    });
  },

  confirmDailyPdfReview() {
    const group = this.data.dailyPdfReviewGroup;
    if (!group || !group.key) return;
    this.setData({ loading: true });
    api.reviewRunDocument(group.key)
      .then((res) => {
        this.setData({
          loading: false,
          dailyPdfReviewDocument: res.document || null,
          dailyPdfReviewCanConfirm: false
        });
        wx.showToast({ title: '草稿已确认，未发布', icon: 'success' });
        this.loadAll();
      })
      .catch((err) => {
        this.setData({ loading: false });
        if (this.showRunDocumentAccountError(err)) return;
        wx.showToast({ title: api.errorMessage(err) || '草稿确认失败', icon: 'none' });
      });
  },

  showRunDocumentAccountError(err) {
    const code = String(err && (err.backendError || err.error) || '');
    if (code !== 'driver_account_preflight_failed') return false;
    const blocked = Array.isArray(err && err.blocked_drivers) ? err.blocked_drivers : [];
    const reasonLabels = {
      driver_not_found: '司机资料不存在',
      driver_account_missing: '未创建或未关联司机账号',
      driver_account_inactive: '司机账号已停用',
      driver_account_role_mismatch: '账号角色不是司机',
      driver_account_profile_mismatch: '账号关联的司机资料不一致',
      driver_supabase_identity_missing: '登录身份尚未建立'
    };
    const lines = blocked.slice(0, 5).map((item) => {
      const name = item.driver_name || `司机 #${item.driver_id || '-'}`;
      return `${name}：${reasonLabels[item.reason] || '账号资料不完整'}`;
    });
    if (blocked.length > 5) lines.push(`另有 ${blocked.length - 5} 名司机未就绪`);
    wx.showModal({
      title: '司机账号未就绪',
      content: [
        lines.join('\n') || '所选司机没有可接收文件的登录账号。',
        '请先在后台账号管理中创建或正确关联司机账号，再重新发布。开发阶段无需先绑定微信。'
      ].join('\n\n'),
      showCancel: false,
      confirmText: '知道了'
    });
    return true;
  },

  publishDailyGroup(e) {
    const key = String((e.currentTarget.dataset || {}).key || '');
    if (!key) return;
    this.setData({ dailySelectedGroupKeys: [key] }, () => this.publishSelectedDailyGroups());
  },

  publishSelectedDailyGroups() {
    if (!(this.data.dailySelectedGroupKeys || []).length) {
      wx.showToast({ title: '请先勾选车辆', icon: 'none' });
      return;
    }
    const keys = (this.data.dailySelectedGroupKeys || []).slice();
    const groups = (this.data.serverRunGroups || []).filter((item) => keys.indexOf(item.key) >= 0);
    const pending = groups.reduce((sum, item) => sum + Number(item.pending_count || 0), 0);
    if (pending) {
      wx.showToast({ title: `还有 ${pending} 单未确认`, icon: 'none' });
      return;
    }
    const notReviewed = groups.filter((item) => item.document_status !== 'reviewed');
    if (notReviewed.length) {
      wx.showToast({ title: `还有 ${notReviewed.length} 车 PDF 未确认`, icon: 'none' });
      return;
    }
    wx.showModal({
      title: keys.length > 1 ? '批量发布' : '确认发布',
      content: `将发布 ${keys.length} 辆车的最新运行文件给对应司机。`,
      confirmText: '发布',
      success: (res) => {
        if (!res.confirm) return;
        this.setData({ loading: true });
        api.publishRunDocuments(keys)
          .then((result) => {
            this.setData({ loading: false, dailySelectedGroupKeys: [] });
            wx.showToast({ title: `已发布 ${result.count || keys.length} 份`, icon: 'success' });
            this.loadAll();
          })
          .catch((err) => {
            console.warn('[run document publish failed]', err);
            this.setData({ loading: false });
            if (this.showRunDocumentAccountError(err)) return;
            wx.showToast({ title: api.errorMessage(err) || '发布失败', icon: 'none' });
          });
      }
    });
  },

  openImport(e) {
    const mode = (e && e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.mode) || 'batch';
    this.setData({
      importOpen: true,
      importMode: mode
    });
  },

  openFlowDemo() {
    this.setData({ workbenchMode: 'daily' });
  },

  openDailyFlowDemo() {
    this.setData({ workbenchMode: 'daily' });
  },

  toggleCharter() {
    this.setData({ charterCollapsed: !this.data.charterCollapsed });
  },

  onImportText(e) {
    this.setData({ importText: e.detail.value });
  },
  openBatchFullscreen() { this.setData({ batchFullscreen: true, batchFullscreenText: this.data.importText || '' }); },
  onBatchFullscreenText(e) { this.setData({ batchFullscreenText: e.detail.value }); },
  closeBatchFullscreen() { this.setData({ batchFullscreen: false }); },
  finishBatchFullscreen() { this.setData({ importText: this.data.batchFullscreenText, batchFullscreen: false }); },

  updateDailyGroups(groups, dailyMessage) {
    const next = normalizeDailyGroups(groups);
    const patch = {
      dailyGroups: next,
      dailyStats: calcDailyStats(next),
      dailyOverview: this.buildDailyOverview(next),
      dailySwipeGroupIndex: -1,
      dailySwipeOrderIndex: -1
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
    const currentAssignments = resources.assignments || this.data.assignments || [];
    const missingDriverGroups = [];
    const missingVehicleGroups = [];
    const driverNav = [];
    normalized.forEach((group, index) => {
      const driverName = String(group.driverName || '').trim();
      const vehicleCode = String(group.vehicleCode || '').trim();
      const orderCount = (group.orders || []).filter((order) => order.status !== '作废').length;
      if (!driverName || driverName === '未命名司机' || driverName === '未分组司机') {
        missingDriverGroups.push({ index, label: `第 ${index + 1} 组`, orderCount });
      } else if (currentDrivers.length && !matchDailyDriver(currentDrivers, driverName)) {
        missingDriverGroups.push({ index, label: `${driverName}（资料库无匹配）`, orderCount });
        driverNav.push({ index, name: driverName, orderCount, vehicleCode: vehicleCode || '未填车辆' });
      } else {
        driverNav.push({ index, name: driverName, orderCount, vehicleCode: vehicleCode || '未填车辆' });
      }
      if (!vehicleCode) {
        missingVehicleGroups.push({ index, label: driverName || `第 ${index + 1} 组`, orderCount });
      } else if (currentVehicles.length && !matchDailyVehicle(currentVehicles, vehicleCode)) {
        missingVehicleGroups.push({ index, label: `${driverName || `第 ${index + 1} 组`}（车辆 ${vehicleCode} 不可派）`, orderCount });
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
    const now = new Date();
    const today = `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`;
    const todayAssignments = currentAssignments.filter((item) => String(item.order_date || '').slice(0, 10) === today);
    const assignedDriverIds = new Set(todayAssignments.map((item) => String(item.driver_id || '')).filter(Boolean));
    const assignedVehicleIds = new Set(todayAssignments.map((item) => String(item.vehicle_id || '')).filter(Boolean));
    const availableDrivers = currentDrivers.filter((driver) => isDriverUsable(driver));
    const availableVehicles = currentVehicles.filter((vehicle) => isVehicleUsable(vehicle));
    const idleDriverCount = availableDrivers.filter((driver) => !assignedDriverIds.has(String(driver.id || ''))).length;
    const idleVehicles = availableVehicles.filter((vehicle) => !assignedVehicleIds.has(String(vehicle.id || '')));
    const idleVehicleCount = idleVehicles.length;
    const tenSeatTotal = availableVehicles.filter((vehicle) => vehicleTypeBucket(vehicle) === '10座').length;
    const alphardTotal = availableVehicles.filter((vehicle) => vehicleTypeBucket(vehicle) === 'Alphard').length;
    const idleTenSeat = idleVehicles.filter((vehicle) => vehicleTypeBucket(vehicle) === '10座').length;
    const idleAlphard = idleVehicles.filter((vehicle) => vehicleTypeBucket(vehicle) === 'Alphard').length;
    return {
      assignedDrivers: driverNav.length,
      assignedOrders,
      idleDrivers: idleDriverCount,
      driverTotal: availableDrivers.length,
      idleVehicles: currentVehicles.length ? idleVehicleCount : filledVehicleCodes.size,
      vehicleTotal: availableVehicles.length,
      idleTenSeat,
      tenSeatTotal,
      idleAlphard,
      alphardTotal,
      missingDriverGroups,
      missingVehicleGroups,
      driverNav
    };
  },

  restoreDailyDraft() {
    const draft = wx.getStorageSync(DAILY_STORAGE_KEY);
    if (!draft || (!draft.sourceText && !draft.groups)) return;
    this.setData({
      dailySourceText: draft.sourceText || '',
      dailyImportDefaultDate: draft.defaultDate || this.data.dailyDate,
      dailyImportBatchId: draft.clientBatchId || ''
    });
    this.updateDailyGroups(draft.groups || [], '已恢复上次保存的日配草稿。');
  },

  onDailySourceInput(e) {
    this.setData({ dailySourceText: e.detail.value, dailyImportBatchId: '', dailyImportLastResult: null });
  },

  onDailyImportDefaultDateChange(e) {
    this.setData({ dailyImportDefaultDate: e.detail.value, dailyImportBatchId: '', dailyImportLastResult: null });
  },

  onDailyGroupDateChange(e) {
    const index = Number(e.currentTarget.dataset.groupIndex);
    const nextDate = String(e.detail.value || '');
    const groups = normalizeDailyGroups(this.data.dailyGroups);
    if (!groups[index] || !isIsoDate(nextDate)) return;
    groups[index].serviceDate = nextDate;
    groups[index].orders = (groups[index].orders || []).map((order) => ({
      ...order,
      date: nextDate,
      parsed: order.parsed ? { ...order.parsed, order_date: nextDate, end_date: nextDate } : order.parsed
    }));
    this.setData({ dailyImportBatchId: '', dailyImportLastResult: null });
    this.updateDailyGroups(groups, '业务日期已修改，请确认后再导入。');
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
      dailyMessage: '已清空。',
      dailyImportBatchId: '',
      dailyImportLastResult: null,
      dailySwipeGroupIndex: -1,
      dailySwipeOrderIndex: -1
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
    this.setData({ loading: true, dailyMessage: '正在解析日配文本...' });
    const defaultDate = this.data.dailyImportDefaultDate || this.data.dailyDate;
    api.parseDailyText(text, {
      default_date: defaultDate,
      default_year: Number(String(defaultDate || '').slice(0, 4)) || new Date().getFullYear()
    })
      .then((res) => {
        const groups = normalizeDailyGroups((res && res.groups) || []);
        const ignored = (res && res.ignored_lines) || [];
        if (ignored.length) console.info('[daily parser ignored lines]', ignored);
        this.updateDailyGroups(groups, `已解析 ${groups.length} 名司机、${calcDailyStats(groups).orders} 单。请核对每组业务日期。`);
        this.setData({ loading: false, dailyImportBatchId: dailyImportRequestId(), dailyImportLastResult: null });
      })
      .catch((err) => {
        this.setData({ loading: false, dailyMessage: this.formatDailyPublishError(err) });
        wx.showToast({ title: '解析失败', icon: 'none' });
      });
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
    this.setData({
      dailySwipeGroupIndex: -1,
      dailySwipeOrderIndex: -1
    });
    this.updateDailyGroups(groups, '已删除订单。');
  },

  onDailyOrderTouchStart(e) {
    const touch = e.touches && e.touches[0];
    if (!touch) return;
    this._dailySwipeStart = {
      x: Number(touch.clientX || 0),
      y: Number(touch.clientY || 0)
    };
  },

  onDailyOrderTouchEnd(e) {
    const start = this._dailySwipeStart;
    const touch = e.changedTouches && e.changedTouches[0];
    this._dailySwipeStart = null;
    if (!start || !touch) return;
    const deltaX = Number(touch.clientX || 0) - start.x;
    const deltaY = Number(touch.clientY || 0) - start.y;
    if (Math.abs(deltaX) < 28 || Math.abs(deltaX) <= Math.abs(deltaY)) return;
    if (deltaX < 0) {
      this.setData({
        dailySwipeGroupIndex: Number(e.currentTarget.dataset.groupIndex),
        dailySwipeOrderIndex: Number(e.currentTarget.dataset.orderIndex)
      });
      return;
    }
    this.setData({
      dailySwipeGroupIndex: -1,
      dailySwipeOrderIndex: -1
    });
  },

  saveDailyDraft() {
    const draft = {
      sourceText: this.data.dailySourceText,
      groups: normalizeDailyGroups(this.data.dailyGroups),
      defaultDate: this.data.dailyImportDefaultDate,
      clientBatchId: this.data.dailyImportBatchId,
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
      api.assignments()
    ]).then(([driversRes, vehiclesRes, assignmentsRes]) => {
      const drivers = (driversRes && driversRes.drivers) || [];
      const vehicles = (vehiclesRes && vehiclesRes.vehicles) || [];
      return {
        drivers: drivers.length ? drivers : (this.data.drivers || []),
        vehicles: vehicles.length ? vehicles : (this.data.vehicles || []),
        assignments: (assignmentsRes && assignmentsRes.assignments) || this.data.assignments || []
      };
    });
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

  publishDailyBatchToBackend(plan, clientBatchId) {
    const payload = {
      client_batch_id: clientBatchId,
      groups: plan.map((item) => ({
        client_group_index: item.groupIndex,
        service_date: item.group.serviceDate,
        driver_id: Number(item.driver.id),
        vehicle_id: Number(item.vehicle.id),
        driver_name: item.group.driverName,
        vehicle_code: item.group.vehicleCode,
        orders: item.orders.map((order) => buildDailyOrderPayload(order))
      }))
    };
    return api.importDailyAssignments(payload).then((res) => {
      if (res && res.success === false) {
        const failed = (res.groups || [])[0] || {};
        const conflict = (res.conflicts || [])[0] || {};
        const target = conflict.oid || conflict.order_id || '-';
        const at = conflict.start_time || '';
        const driverName = failed.driver_name || '日配订单';
        const vehicleCode = failed.vehicle_code || '';
        throw new Error(`${driverName} · ${vehicleCode}\n${at} 与现有订单 ${target} 时间冲突`);
      }
      const records = (res.groups || []).map((record, planIndex) => ({
        groupIndex: Number(record.client_group_index != null ? record.client_group_index : plan[planIndex].groupIndex),
        orderIds: (record.order_ids || record.updated_order_ids || []).map(Number),
        driverId: Number(record.driver_id || plan[planIndex].driver.id),
        vehicleId: Number(record.vehicle_id || plan[planIndex].vehicle.id),
        reused: Boolean(record.reused),
        updatedExisting: Boolean(record.updated_existing)
      }));
      return { response: res || {}, records };
    });
  },

  formatDailyPublishError(err) {
    if (!err) return '导入失败，请检查后端连接。';
    if (err.error === 'daily_import_oid_conflict') return `订单编号冲突，事务已回滚，未写入。请求号：${err.request_id || this.data.dailyImportBatchId || '-'}`;
    if (err.rolled_back) return `导入失败，事务已回滚，未写入，可安全重试。请求号：${err.request_id || this.data.dailyImportBatchId || '-'}`;
    if (err.error === 'network_timeout') return '后端请求超时，正在按批次号核对实际提交结果。';
    if (err.error === 'network_failed') return '连接后端失败，请确认 API 已启动。';
    if (err.userMessage) return err.userMessage;
    if (err.message) return err.message;
    if (typeof err === 'string') return err;
    return '导入失败，请检查后端连接。';
  },

  finishDailyImportSuccess(groups, orderCount, importResult) {
    const response = importResult.response || importResult;
    const publishedRecords = importResult.records || (response.groups || []).map((record) => ({
      groupIndex: Number(record.client_group_index != null ? record.client_group_index : record.group_index || 0),
      orderIds: (record.order_ids || record.updated_order_ids || []).map(Number),
      driverId: Number(record.driver_id || 0),
      vehicleId: Number(record.vehicle_id || 0),
      reused: Boolean(record.reused),
      updatedExisting: Boolean(record.updated_existing)
    }));
    const publishedByGroup = {};
    publishedRecords.forEach((item) => { publishedByGroup[item.groupIndex] = (item.orderIds || []).slice(); });
    const publishedGroups = groups.map((group, index) => ({
      ...group,
      orders: group.orders.map((order) => {
        if (order.status === '作废' || order.backendOrderId) return order;
        const backendOrderId = (publishedByGroup[index] || []).shift();
        return backendOrderId ? { ...order, status: '待确认', backendOrderId } : order;
      })
    }));
    const businessDates = (response.business_dates || publishedGroups.map((group) => group.serviceDate)).filter(Boolean);
    const uniqueDates = businessDates.filter((value, index, list) => list.indexOf(value) === index).sort();
    const targetDate = uniqueDates[0] || this.data.dailyDate;
    const firstRecord = publishedRecords[0] || {};
    const highlightKey = firstRecord.driverId && firstRecord.vehicleId ? `${targetDate}:${firstRecord.driverId}:${firstRecord.vehicleId}` : '';
    const payload = {
      sourceText: this.data.dailySourceText,
      groups: normalizeDailyGroups(publishedGroups),
      backendPublished: publishedRecords,
      backendResult: response,
      clientBatchId: response.client_batch_id || this.data.dailyImportBatchId,
      defaultDate: this.data.dailyImportDefaultDate,
      publishedAt: new Date().toISOString(),
      overview: this.buildDailyOverview(publishedGroups)
    };
    wx.setStorageSync(DAILY_PUBLISHED_KEY, payload);
    wx.setStorageSync(DAILY_STORAGE_KEY, payload);
    wx.setStorageSync(DAILY_CONFIRM_QUEUE_KEY, payload);
    const extraDates = uniqueDates.slice(1);
    const message = `已导入 ${publishedRecords.length} 名司机、${orderCount} 单；订单待核对，文书待生成。${extraDates.length ? ` 另有日期：${extraDates.join('、')}` : ''}`;
    this.updateDailyGroups(payload.groups, message);
    this.setData({
      loading: false,
      dailyImportSubmitting: false,
      dailyImportOpen: false,
      dailyDate: targetDate,
      dailyImportLastResult: response,
      dailyImportedHighlightKey: highlightKey,
      dailySelectedGroupKeys: highlightKey ? [highlightKey] : []
    }, () => this.refreshTabBar());
    const reused = Boolean(response.idempotent_replay) || publishedRecords.some((item) => item.reused || item.updatedExisting);
    wx.showToast({ title: reused ? '已定位原日配草稿' : '导入成功', icon: 'success' });
    return this.loadAll().then(() => {
      const found = !highlightKey || (this.data.dailyRunGroups || []).some((item) => item.key === highlightKey);
      if (!found) this.setData({ dailyMessage: '导入成功，列表刷新失败。请点击重新加载；不要重复导入。' });
    });
  },

  resolveDailyImportUncertain(err, groups, orderCount) {
    const batchId = this.data.dailyImportBatchId;
    const uncertain = !!err && (
      ['network_timeout', 'network_failed', 'internal_server_error', 'daily_import_oid_conflict', 'daily_import_transaction_failed'].includes(err.error) ||
      Number(err.statusCode || 0) >= 500
    );
    if (!batchId || !uncertain) return Promise.reject(err);
    return api.dailyImportStatus(batchId).then((statusResult) => {
      const batch = statusResult && statusResult.batch;
      if (batch && batch.status === 'succeeded' && batch.result) {
        return this.finishDailyImportSuccess(groups, orderCount, batch.result);
      }
      if (batch && batch.status === 'failed') {
        return Promise.reject({
          error: batch.error_code || err.error || 'daily_import_transaction_failed',
          request_id: batchId,
          rolled_back: true,
          message: `请求 ${batchId} 已确认回滚，原文、解析结果和选择均已保留。`
        });
      }
      return Promise.reject({
        error: batch && batch.error_code || 'daily_import_result_unknown',
        request_id: batchId,
        rolled_back: Boolean(batch && batch.status === 'failed'),
        message: batch && batch.status === 'pending'
          ? `请求 ${batchId} 仍在处理中，请稍后重新加载状态，不要重复创建新批次。`
          : `请求 ${batchId} 的提交结果尚未确认，已保留原批次号和全部输入。`
      });
    }, (statusError) => Promise.reject({
      error: 'daily_import_result_unknown',
      request_id: batchId,
      message: Number(statusError && statusError.statusCode || 0) === 404
        ? `当前 Trial 后端缺少批次状态接口。请求 ${batchId} 可能已经写入；已保留全部输入，请先返回日配日期刷新检查，不要重复确认。`
        : `请求 ${batchId} 的提交结果尚未确认，已保留原批次号和全部输入。请先重新加载状态，不要创建新批次。`
    }));
  },

  reloadDailyAfterImport() {
    this.loadAll().then(() => this.setData({ dailyMessage: this.data.dailyImportLastResult ? '日配列表已重新加载。' : this.data.dailyMessage }));
  },

  showDailyImportFailure(err) {
    const message = this.formatDailyPublishError(err);
    this.setData({
      loading: false,
      dailyImportSubmitting: false,
      dailyMessage: message,
      conflictText: message
    });
    wx.showModal({ title: '导入未完成', content: message, showCancel: false });
  },

  publishDailyAssignments() {
    if (this.data.dailyImportSubmitting) return;
    if (!this.ensureYuzuDevTenant()) return;
    const groups = normalizeDailyGroups(this.data.dailyGroups);
    const orderCount = groups.reduce((sum, group) => {
      return sum + (group.orders || []).filter((order) => shouldPublishDailyOrder(order)).length;
    }, 0);
    if (!orderCount) {
      wx.showToast({ title: '没有待导入订单', icon: 'none' });
      return;
    }
    const missingDate = groups.find((group) => !isIsoDate(group.serviceDate) || (group.orders || []).some((order) => !isIsoDate(order.date)));
    if (missingDate) {
      wx.showToast({ title: '请补全业务日期', icon: 'none' });
      return;
    }
    const clientBatchId = this.data.dailyImportBatchId || dailyImportRequestId();
    this.setData({
      loading: true,
      dailyImportSubmitting: true,
      dailyMessage: '正在导入订单，导入后进入待运行确认...',
      conflictText: '',
      dailyImportBatchId: clientBatchId
    });
    this.loadDailyPublishResources()
      .then((resources) => {
        const result = this.validateDailyPublishPlan(groups, resources);
        if (result.errors.length) {
          const mainErrors = result.errors.slice(0, 4);
          const diagnostic = result.errors[result.errors.length - 1];
          throw new Error(mainErrors.concat(diagnostic).join('；'));
        }
        return this.publishDailyBatchToBackend(result.plan, clientBatchId);
      })
      .then((result) => this.finishDailyImportSuccess(groups, orderCount, result))
      .catch((err) => {
        if (err && (
          ['network_timeout', 'network_failed', 'internal_server_error', 'daily_import_oid_conflict', 'daily_import_transaction_failed'].includes(err.error) ||
          Number(err.statusCode || 0) >= 500
        )) {
          this.resolveDailyImportUncertain(err, groups, orderCount).catch((resolvedError) => this.showDailyImportFailure(resolvedError));
          return;
        }
        this.showDailyImportFailure(err);
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
    let loadError = '';
    const fallback = (label, value) => (err) => {
      console.warn(`[dispatch load ${label} failed]`, err);
      loadError = loadError || api.errorMessage(err);
      return value;
    };
    return Promise.all([
      api.drafts().catch(fallback('drafts', { drafts: [] })),
      api.unassignedOrders().catch(fallback('unassigned orders', { orders: [] })),
      api.drivers().catch(fallback('drivers', { drivers: this.data.drivers || [] })),
      api.vehicles().catch(fallback('vehicles', { vehicles: this.data.vehicles || [] })),
      api.assignments().catch(fallback('assignments', { assignments: this.data.assignments || [] })),
      api.runGroups(this.data.dailyDate).catch(fallback('run groups', { groups: this.data.serverRunGroups || [] }))
    ])
      .then((rawResults) => {
        const results = Array.isArray(rawResults) ? rawResults : [];
        const draftsRes = results[0] || { drafts: [] };
        const ordersRes = results[1] || { orders: [] };
        const driversRes = results[2] || { drivers: [] };
        const vehiclesRes = results[3] || { vehicles: [] };
        const assignmentsRes = results[4] || { assignments: [] };
        const runGroupsRes = results[5] || { groups: [] };
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
        const serverRunGroups = runGroupsRes.groups || [];
        const dailyRun = this.decorateServerRunGroups(serverRunGroups);
        const activePdfKey = this.data.dailyPdfReviewGroup && this.data.dailyPdfReviewGroup.key;
        const activePdfGroup = activePdfKey && (dailyRun.allGroups || []).find((item) => item.key === activePdfKey);
        const activePdfIndex = activePdfGroup ? (dailyRun.allGroups || []).findIndex((item) => item.key === activePdfKey) : this.data.dailyPdfReviewIndex;
        const activePdfValidation = buildValidationPresentation(activePdfGroup && activePdfGroup.validation_issues || []);
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
          serverRunGroups,
          publishedRows,
          dailyRunGroups: dailyRun.groups,
          dailyRunSummary: dailyRun.summary,
          ...(activePdfGroup ? {
            dailyPdfReviewGroup: activePdfGroup,
            dailyPdfReviewIndex: activePdfIndex,
            dailyPdfReviewTotal: (dailyRun.allGroups || []).length,
            dailyPdfValidationIssues: activePdfValidation.issues,
            dailyPdfValidationRaw: activePdfValidation.raw,
            dailyPdfIssueSummary: activePdfValidation.summary,
            dailyPdfReviewCanConfirm: !this.data.dailyPdfPreviewUnavailable && !!this.data.dailyPdfReviewDocument && this.data.dailyPdfReviewDocument.status !== 'published' && !activePdfValidation.raw.length
          } : {}),
          dailyOverview: this.buildDailyOverview(this.data.dailyGroups, {
            drivers: decoratedDrivers,
            vehicles: decoratedVehicles,
            assignments
          }),
          conflictText: loadError,
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
    });
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
    });
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

