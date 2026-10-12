const API_STORAGE_KEY = 'wx_dispatch_api_base_url';
const FORCE_LOCAL_KEY = 'wx_dispatch_force_local_api';
const ACTIVE_TAB_KEY = 'dispatch_active_tab_path';
const SESSION_STORAGE_KEY = 'dispatcher_session';
const MANUAL_LOGOUT_KEY = 'dispatch_manual_logout';
const TRIAL_BASE_URL = 'https://api-trial.taxi-airport.jp';
const LOCAL_BASE_URL = 'http://127.0.0.1:18765';
const DEFAULT_BASE_URL = TRIAL_BASE_URL;
const CLOUD_BASE_URL = TRIAL_BASE_URL;
const REQUEST_TIMEOUT_MS = 15000;

const API_CONFIG = {
  baseUrl: wx.getStorageSync(API_STORAGE_KEY) || DEFAULT_BASE_URL
};

function setBaseUrl(baseUrl) {
  API_CONFIG.baseUrl = String(baseUrl || '').replace(/\/$/, '');
  wx.setStorageSync(API_STORAGE_KEY, API_CONFIG.baseUrl);
}

function getBaseUrl() {
  return API_CONFIG.baseUrl;
}

function getSessionStorageKey() {
  return `${SESSION_STORAGE_KEY}:${API_CONFIG.baseUrl}`;
}

function useCloudBaseUrl(baseUrl = CLOUD_BASE_URL) {
  setBaseUrl(baseUrl);
}

function resetBaseUrl() {
  wx.removeStorageSync(API_STORAGE_KEY);
  API_CONFIG.baseUrl = DEFAULT_BASE_URL;
}

function getRuntimeInfo() {
  const deviceInfo = typeof wx.getDeviceInfo === 'function' ? wx.getDeviceInfo() : {};
  const windowInfo = typeof wx.getWindowInfo === 'function' ? wx.getWindowInfo() : {};
  const appBaseInfo = typeof wx.getAppBaseInfo === 'function' ? wx.getAppBaseInfo() : {};
  return {
    device: deviceInfo,
    window: windowInfo,
    app: appBaseInfo,
    platform: deviceInfo.platform || appBaseInfo.platform || ''
  };
}

function isLocalBaseUrl() {
  return /^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?/i.test(API_CONFIG.baseUrl);
}

function syncEnvironmentBaseUrl() {
  const forceLocal = !!wx.getStorageSync(FORCE_LOCAL_KEY);
  if (forceLocal) {
    setBaseUrl(LOCAL_BASE_URL);
    return;
  }
  setBaseUrl(CLOUD_BASE_URL);
}

function setActiveTab(path) {
  wx.setStorageSync(ACTIVE_TAB_KEY, path);
}

function getSession() {
  const scopedSession = wx.getStorageSync(getSessionStorageKey()) || null;
  if (scopedSession && scopedSession.token) return scopedSession;
  const legacySession = wx.getStorageSync(SESSION_STORAGE_KEY) || null;
  if (legacySession && legacySession.token) return legacySession;
  const unifiedSession = wx.getStorageSync('yuzu_session') || null;
  if (unifiedSession && unifiedSession.port === 'dispatch' && unifiedSession.token) return unifiedSession;
  const app = typeof getApp === 'function' ? getApp() : null;
  const appSession = app && app.globalData ? app.globalData.session : null;
  if (appSession && appSession.port === 'dispatch' && appSession.token) return appSession;
  console.warn('[dispatch getSession missing]', {
    baseUrl: API_CONFIG.baseUrl,
    hasScoped: !!scopedSession,
    hasLegacy: !!legacySession,
    hasUnified: !!unifiedSession,
    hasAppSession: !!appSession
  });
  return null;
}

function setSession(session) {
  wx.setStorageSync(getSessionStorageKey(), session);
  wx.setStorageSync(SESSION_STORAGE_KEY, session);
  wx.setStorageSync('yuzu_session', Object.assign({}, session || {}, { port: 'dispatch' }));
  const app = typeof getApp === 'function' ? getApp() : null;
  if (app && app.globalData) {
    app.globalData.session = Object.assign({}, session || {}, { port: 'dispatch' });
  }
  wx.removeStorageSync(MANUAL_LOGOUT_KEY);
}

function clearSession(options = {}) {
  wx.removeStorageSync(getSessionStorageKey());
  wx.removeStorageSync(SESSION_STORAGE_KEY);
  wx.removeStorageSync(`${SESSION_STORAGE_KEY}:${TRIAL_BASE_URL}`);
  wx.removeStorageSync(`${SESSION_STORAGE_KEY}:${LOCAL_BASE_URL}`);
  wx.removeStorageSync('yuzu_session');
  wx.removeStorageSync(ACTIVE_TAB_KEY);
  const app = typeof getApp === 'function' ? getApp() : null;
  if (app && app.globalData && app.globalData.session && app.globalData.session.port === 'dispatch') {
    app.globalData.session = null;
  }
  if (options.manual) {
    wx.setStorageSync(MANUAL_LOGOUT_KEY, true);
  }
}

function isManualLogout() {
  return !!wx.getStorageSync(MANUAL_LOGOUT_KEY);
}

function clearManualLogout() {
  wx.removeStorageSync(MANUAL_LOGOUT_KEY);
}

function getRole(session = getSession()) {
  const dispatcher = session && session.dispatcher ? session.dispatcher : {};
  const user = session && session.user ? session.user : {};
  return user.role || dispatcher.dispatcher_role || '';
}

function canAccess(feature, session = getSession()) {
  const role = getRole(session);
  const rules = {
    dispatch: ['admin', 'dispatcher', 'operations_manager'],
    auction: ['admin'],
    map: ['admin', 'dispatcher', 'operations_manager', 'driver'],
    finance: ['admin'],
    profile: ['admin', 'dispatcher', 'operations_manager', 'driver']
  };
  return (rules[feature] || []).indexOf(role) >= 0;
}

function errorMessage(err) {
  const statusCode = Number(err && err.statusCode || 0);
  const code = String(err && (err.backendError || err.error) || '').trim();
  const pendingCount = Number(err && (err.pending_count || err.pendingCount) || 0);
  if (statusCode === 403 || code === 'forbidden') return '当前账号无此操作权限';
  if (statusCode >= 500 || code === 'internal_server_error') return '服务器处理失败，请稍后重试';
  if (code === 'network_timeout') return '后端请求超时，请稍后重试';
  if (code === 'network_failed') return '连接服务器失败，请检查网络后重试';
  if (code === 'driver_account_preflight_failed') {
    const blocked = Array.isArray(err && err.blocked_drivers) ? err.blocked_drivers : [];
    const names = blocked.map((item) => item.driver_name).filter(Boolean).slice(0, 3).join('、');
    return `${names || '所选司机'}的登录账号尚未就绪，请先创建或正确关联司机账号`;
  }
  const fixedTourMessages = {
    fixed_tour_requires_two_stops: '行程至少需要两个地点',
    fixed_tour_stop_location_required: '请补全所有地点名称',
    fixed_tour_time_invalid: '时间必须使用24小时制 HH:mm，例如 09:30',
    fixed_tour_stop_time_order: '同一地点的出发时间不能早于到达时间',
    fixed_tour_day_order_invalid: '多日行程的天数顺序不正确',
    fixed_tour_day_trip_has_multiple_days: '日归路线不能包含第2天，请切换为多日',
    fixed_tour_business_date_invalid: '请选择有效的本次出发日期',
    fixed_tour_client_request_id_required: '本次保存标识缺失，请返回后重试',
    fixed_tour_service_unavailable: '当前测试后端尚未更新保存行程功能；已保留填写内容，请稍后安全重试',
    fixed_tour_route_not_found: '未找到对应的预设路线，请刷新路线列表后重试',
    fixed_tour_route_not_available: '该预设路线已停用或不属于当前公司，请刷新后重试',
    fixed_tour_charter_draft_not_found: '本次行程草稿不存在或无权访问',
    fixed_tour_charter_draft_locked: '该行程已进入后续流程，不能覆盖原草稿',
    fixed_tour_charter_order_not_found: '本次行程关联订单不存在，请重新创建本次行程',
    fixed_tour_driver_vehicle_required: '请选择司机和车辆后再生成文书草稿',
    fixed_tour_assignment_conflict: '司机或车辆与已有任务冲突，请更换后重试',
    fixed_tour_draft_already_assigned: '本次草稿已分配其他司机或车辆，请返回原草稿继续处理',
    fixed_tour_driver_unavailable: '司机当日已有任务或资格状态不满足，请更换司机',
    fixed_tour_vehicle_unavailable: '车辆当日已有任务或车辆状态不可派，请更换车辆',
    fixed_tour_vehicle_type_mismatch: '车辆车型与该路线配置不匹配，请更换车辆',
    run_group_not_found: '没有找到对应的派车组合，请刷新后重试'
  };
  const dailyImportMessages = {
    daily_import_batch_payload_mismatch: '本批次的内容已发生变化，请重新解析后再导入',
    daily_import_batch_id_required: '日配批次号缺失，请保留输入并重新解析',
    daily_import_batch_not_found: '尚未查到该日配批次的提交结果，请勿新建重复批次',
    daily_import_year_invalid: '导入年份无效，请重新选择年份',
    daily_import_default_date_invalid: '默认业务日期无效，请重新选择日期',
    daily_import_requires_one_service_date: '同一司机车辆分组只能使用一个业务日期'
  };
  if (dailyImportMessages[code]) return dailyImportMessages[code];
  if (fixedTourMessages[code]) return fixedTourMessages[code];
  if (/confirm/i.test(code) && /order/i.test(code)) {
    return pendingCount > 0 ? `还有 ${pendingCount} 单未确认` : '还有订单未确认，请先完成审核';
  }
  if (/review/i.test(code) && /document|pdf/i.test(code)) return '请先确认 PDF';
  return String(err && (err.userMessage || err.message || err.detail) || code || '请求失败，请稍后重试');
}

function normalizeApiError(body, statusCode, path = '') {
  const payload = body && typeof body === 'object' ? { ...body } : { error: 'request_failed' };
  payload.statusCode = Number(statusCode || 0);
  payload.backendError = String(payload.error || 'request_failed');
  payload.path = path;
  if (payload.statusCode === 404 && payload.backendError === 'not_found' && path.indexOf('/fixed-tour/') >= 0) {
    payload.backendError = 'fixed_tour_service_unavailable';
    payload.error = payload.backendError;
  }
  payload.userMessage = errorMessage(payload);
  return payload;
}

function request(path, options = {}) {
  const session = getSession();
  return new Promise((resolve, reject) => {
    const requestPayload = options.data || {};
    wx.request({
      url: `${API_CONFIG.baseUrl}${path}`,
      method: options.method || 'GET',
      data: requestPayload,
      timeout: options.timeout || REQUEST_TIMEOUT_MS,
      header: {
        'Content-Type': 'application/json',
        ...(session && session.token ? { Authorization: `Bearer ${session.token}` } : {})
      },
      success: (res) => {
        if (res.statusCode >= 400) {
          console.error('[dispatch-mobile api failed]', {
            path,
            method: options.method || 'GET',
            statusCode: res.statusCode,
            responseBody: res.data
          });
          if (res.statusCode === 401 && !options._retried && path.indexOf('/login') < 0 && session && session.refresh_token) {
            refreshSession(session.refresh_token).then(() => {
              request(path, { ...options, _retried: true }).then(resolve).catch(reject);
            }).catch(() => {
              clearSession();
              wx.reLaunch({ url: '/package_dispatch/pages/home/index' });
              reject(normalizeApiError(res.data, res.statusCode, path));
            });
            return;
          }
          if (res.statusCode === 401 && path.indexOf('/login') < 0) {
            clearSession();
            wx.reLaunch({ url: '/package_dispatch/pages/home/index' });
          }
          reject(normalizeApiError(res.data, res.statusCode, path));
          return;
        }
        resolve(res.data);
      },
      fail: (err) => {
        console.error('[dispatch-mobile api network failed]', {
          path,
          method: options.method || 'GET',
          baseUrl: API_CONFIG.baseUrl,
          error: err
        });
        const errMsg = err && err.errMsg ? String(err.errMsg) : '';
        reject({
          error: errMsg.indexOf('timeout') >= 0 ? 'network_timeout' : 'network_failed',
          detail: errMsg,
          path,
          base_url: API_CONFIG.baseUrl
        });
      }
    });
  });
}

function downloadAndOpenDocument(path) {
  const session = getSession();
  return new Promise((resolve, reject) => {
    wx.downloadFile({
      url: `${API_CONFIG.baseUrl}${path}`,
      header: session && session.token ? { Authorization: `Bearer ${session.token}` } : {},
      success: (res) => {
        if (res.statusCode !== 200) {
          reject({ error: 'document_download_failed', statusCode: res.statusCode });
          return;
        }
        wx.openDocument({
          filePath: res.tempFilePath,
          fileType: 'pdf',
          showMenu: true,
          success: () => resolve(res),
          fail: reject
        });
      },
      fail: reject
    });
  });
}

function refreshSession(refreshToken) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${API_CONFIG.baseUrl}/api/auth/refresh`,
      method: 'POST',
      data: { refresh_token: refreshToken },
      timeout: REQUEST_TIMEOUT_MS,
      header: { 'Content-Type': 'application/json' },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300 && res.data && res.data.token) {
          setSession(Object.assign({}, res.data, { port: 'dispatch' }));
          resolve(res.data);
          return;
        }
        reject(normalizeApiError(res.data, res.statusCode, '/api/auth/refresh'));
      },
      fail: reject
    });
  });
}

function buildWechatLoginPayload(wxCode = '', overrides = {}) {
  const code = String(wxCode || '').trim();
  return { wx_code: code, client_type: 'dispatch_miniapp' };
}

function toQuery(params = {}) {
  const pairs = Object.keys(params)
    .filter((key) => params[key] !== undefined && params[key] !== null && params[key] !== '')
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`);
  return pairs.length ? `?${pairs.join('&')}` : '';
}

function withDispatcher(payload = {}) {
  const session = getSession();
  const dispatcher = session && session.dispatcher ? session.dispatcher : {};
  return {
    ...payload,
    dispatcher_id: dispatcher.dispatcher_id,
    dispatcher_code: dispatcher.dispatcher_code,
    dispatcher_name: dispatcher.dispatcher_name,
    dispatcher_role: dispatcher.dispatcher_role
  };
}

module.exports = {
  API_CONFIG,
  TRIAL_BASE_URL,
  LOCAL_BASE_URL,
  setBaseUrl,
  getBaseUrl,
  useCloudBaseUrl,
  resetBaseUrl,
  syncEnvironmentBaseUrl,
  getRuntimeInfo,
  isLocalBaseUrl,
  setActiveTab,
  getSession,
  setSession,
  clearSession,
  isManualLogout,
  clearManualLogout,
  getRole,
  canAccess,
  errorMessage,
  withDispatcher,
  request,
  downloadAndOpenDocument,
  appConfig: () => request('/api/dispatch-mobile/app-config'),
  login: (username, password, wxCode = '') => request('/api/dispatch-mobile/login', { method: 'POST', data: { username, password, wx_code: wxCode, client_type: wxCode ? 'dispatch_miniapp' : 'web' } }),
  loginPhone: (phone, password, wxCode = '') => request('/api/dispatch-mobile/login', { method: 'POST', data: { phone, password, wx_code: wxCode, client_type: wxCode ? 'dispatch_miniapp' : 'web' } }),
  loginWechat: (wxCode, overrides = {}) => request('/api/auth/wechat-login', { method: 'POST', data: buildWechatLoginPayload(wxCode, overrides) }),
  registerPhone: (data) => request('/api/auth/register', { method: 'POST', data: { ...data, client_type: data.client_type || 'dispatch_miniapp' } }),
  context: () => {
    const session = getSession();
    const dispatcher = session && session.dispatcher ? session.dispatcher : {};
    const query = dispatcher.dispatcher_id ? `?dispatcher_id=${dispatcher.dispatcher_id}` : '';
    return request(`/api/dispatch-mobile/context${query}`);
  },
  dashboard: () => {
    const session = getSession();
    const dispatcher = session && session.dispatcher ? session.dispatcher : {};
    const query = dispatcher.dispatcher_id ? `?dispatcher_id=${dispatcher.dispatcher_id}` : '';
    return request(`/api/dispatch-mobile/dashboard${query}`);
  },
  sharedState: () => request('/api/dispatch-mobile/shared-state'),
  parseText: (text, batch = true) => request('/api/dispatch-mobile/parser/text', { method: 'POST', data: withDispatcher({ text, batch }) }),
  parseDailyText: (text, options = {}) => request('/api/dispatch-mobile/parser/daily', { method: 'POST', data: withDispatcher({ text, ...options }) }),
  drafts: () => request('/api/dispatch-mobile/drafts'),
  updateDraft: (id, data) => request(`/api/dispatch-mobile/drafts/${id}`, { method: 'PUT', data: withDispatcher(data) }),
  updateOrder: (id, data) => request(`/api/dispatch-mobile/orders/${id}/update`, { method: 'POST', data: withDispatcher(data) }),
  confirmDraft: (id) => request(`/api/dispatch-mobile/drafts/${id}/confirm`, { method: 'POST', data: withDispatcher({}) }),
  unassignedOrders: () => {
    const session = getSession();
    const dispatcher = session && session.dispatcher ? session.dispatcher : {};
    const query = dispatcher.dispatcher_id ? `?dispatcher_id=${dispatcher.dispatcher_id}` : '';
    return request(`/api/dispatch-mobile/unassigned-orders${query}`);
  },
  notifications: () => {
    const session = getSession();
    const dispatcher = session && session.dispatcher ? session.dispatcher : {};
    const query = dispatcher.dispatcher_id ? `?dispatcher_id=${dispatcher.dispatcher_id}` : '';
    return request(`/api/dispatch-mobile/notifications${query}`);
  },
  driverNotifications: () => request('/api/driver/notifications?limit=30'),
  markDriverNotificationRead: (_driverId, notificationId) => request(`/api/driver/notifications/${notificationId}/read`, { method: 'POST', data: {} }),
  driverAssignments: () => request('/api/driver/assignments'),
  driverWorkbench: () => request('/api/driver/workbench'),
  driverDailyReport: (date) => request(`/api/driver/daily-report${date ? `?date=${encodeURIComponent(date)}` : ''}`),
  saveDriverDailyReport: (data) => request('/api/driver/daily-report', { method: 'POST', data }),
  driverProfile: () => request('/api/driver/profile'),
  updateDriverProfile: (data) => request('/api/driver/profile', { method: 'POST', data }),
  uploadDriverProfileDocument: (data) => request('/api/driver/profile-document', { method: 'POST', data }),
  driverExpenses: () => request('/api/driver/expenses'),
  driverIncome: () => request('/api/driver/income'),
  submitDriverReport: (data) => request('/api/driver/report', { method: 'POST', data }),
  uploadDriverEvidence: (data) => request('/api/driver/evidence', { method: 'POST', data }),
  submitDriverLocation: (data) => request('/api/driver/location', { method: 'POST', data }),
  submitDriverWorkflowEvent: (data) => request('/api/driver/workflow-event', { method: 'POST', data }),
  submitDriverExpense: (data) => request('/api/driver/expense', { method: 'POST', data }),
  auditLogs: () => {
    const session = getSession();
    const dispatcher = session && session.dispatcher ? session.dispatcher : {};
    const query = dispatcher.dispatcher_id ? `?dispatcher_id=${dispatcher.dispatcher_id}` : '';
    return request(`/api/dispatch-mobile/audit-logs${query}`);
  },
  orderHistory: (orderId) => request(`/api/audit/history?entity_type=order&entity_id=${orderId}&limit=30`),
  drivers: () => request('/api/dispatch-mobile/drivers'),
  vehicles: () => request('/api/dispatch-mobile/vehicles'),
  resourceSearch: (type, q = '', date = '', routeId = '') => request(`/api/dispatch-mobile/resource-search${toQuery({ type, q, date, route_id: routeId })}`),
  fixedTourRoutes: (q = '') => request(`/api/fixed-tour/routes${toQuery({ q })}`),
  mobileFixedTourRoutes: (q = '') => request(`/api/dispatch-mobile/fixed-tour/routes${toQuery({ q })}`),
  fixedTourDispatchOptions: (date, draftId = '', routeId = '') => request(`/api/dispatch-mobile/fixed-tour/options${toQuery({ date, draft_id: draftId, route_id: routeId })}`),
  createMobileFixedTourRoute: (payload) => request('/api/dispatch-mobile/fixed-tour/routes', { method: 'POST', data: withDispatcher(payload) }),
  updateMobileFixedTourRoute: (routeId, payload) => request(`/api/dispatch-mobile/fixed-tour/routes/${routeId}`, { method: 'PUT', data: withDispatcher(payload) }),
  copyMobileFixedTourRoute: (routeId) => request(`/api/dispatch-mobile/fixed-tour/routes/${routeId}/copy`, { method: 'POST', data: withDispatcher({}) }),
  setMobileFixedTourRouteStatus: (routeId, status) => request(`/api/dispatch-mobile/fixed-tour/routes/${routeId}/status`, { method: 'POST', data: withDispatcher({ status }) }),
  saveAndUseMobileFixedTourRoute: (payload) => request('/api/dispatch-mobile/fixed-tour/routes/save-use', { method: 'POST', data: withDispatcher(payload) }),
  createFixedTourCharterDraft: (payload) => request('/api/dispatch-mobile/fixed-tour/drafts', { method: 'POST', data: withDispatcher(payload) }),
  fixedTourCharterDraft: (draftId) => request(`/api/dispatch-mobile/fixed-tour/drafts/${draftId}`),
  updateFixedTourCharterDraft: (draftId, payload) => request(`/api/dispatch-mobile/fixed-tour/drafts/${draftId}`, { method: 'PUT', data: withDispatcher(payload) }),
  generateFixedTourDraftDocuments: (draftId, payload) => request(`/api/dispatch-mobile/fixed-tour/drafts/${draftId}/generate-documents`, { method: 'POST', data: withDispatcher(payload) }),
  materializeFixedTour: (payload) => request('/api/dispatch-mobile/fixed-tour/materialize', { method: 'POST', data: withDispatcher(payload) }),
  resourceDrivers: (status = '') => request(`/api/resources/drivers${toQuery({ status })}`),
  updateResourceDriver: (id, data) => request(`/api/resources/drivers/${id}`, { method: 'PUT', data }),
  deleteResourceDriver: (id) => request(`/api/resources/drivers/${id}`, { method: 'DELETE' }),
  resourceVehicles: (status = '') => request(`/api/resources/vehicles${toQuery({ status })}`),
  updateResourceVehicle: (id, data) => request(`/api/resources/vehicles/${id}`, { method: 'PUT', data }),
  resourceReminders: () => request('/api/resources/reminders'),
  updateResourceReminderDate: (data) => request('/api/dispatch-mobile/resource-reminders/date', { method: 'POST', data }),
  resourceLibrary: () => request('/api/dispatch-mobile/resource-library'),
  markNotificationRead: (notificationId) => request(`/api/notifications/${notificationId}/read`, { method: 'POST', data: {} }),
  updateResourceDriverStatus: (data) => request('/api/dispatch-mobile/resource-library/driver-status', { method: 'POST', data }),
  updateResourceDriverHealth: (data) => request('/api/dispatch-mobile/resource-library/driver-health', { method: 'POST', data }),
  updateResourceVehicleInspection: (data) => request('/api/dispatch-mobile/resource-library/vehicle-inspection', { method: 'POST', data }),
  updateResourceVehicleStatus: (data) => request('/api/dispatch-mobile/resource-library/vehicle-status', { method: 'POST', data }),
  resourceLibraryFileUrl: (fileKey) => `${API_CONFIG.baseUrl}/api/dispatch-mobile/resource-library/file${toQuery({ file: fileKey })}`,
  assignOrders: (payload) => request('/api/dispatch-mobile/dispatch/assign', { method: 'POST', data: withDispatcher(payload) }),
  importDailyAssignments: (payload) => request('/api/dispatch-mobile/daily-import/assign', { method: 'POST', data: withDispatcher(payload) }),
  dailyImportStatus: (clientBatchId) => request(`/api/dispatch-mobile/daily-import/status${toQuery({ client_batch_id: clientBatchId })}`),
  assignments: () => request('/api/dispatch-mobile/assignments'),
  runGroups: (date) => request(`/api/dispatch-mobile/run-groups${toQuery({ date })}`),
  confirmRunOrder: (data) => request('/api/dispatch-mobile/run-confirm', { method: 'POST', data: withDispatcher(data) }),
  generateRunDocument: (groupKey) => request('/api/dispatch-mobile/run-documents/generate', { method: 'POST', data: withDispatcher({ group_key: groupKey }) }),
  runDocumentPreview: (groupKey) => request('/api/dispatch-mobile/run-documents/preview', { method: 'POST', data: withDispatcher({ group_key: groupKey }) }),
  updateRunDocumentNode: (data) => request('/api/dispatch-mobile/run-documents/node', { method: 'POST', data: withDispatcher(data) }),
  reviewRunDocument: (groupKey) => request('/api/dispatch-mobile/run-documents/review', { method: 'POST', data: withDispatcher({ group_key: groupKey }) }),
  reviewAndPublishRunDocument: (groupKey) => request('/api/dispatch-mobile/run-documents/review-publish', { method: 'POST', data: withDispatcher({ group_key: groupKey }) }),
  publishRunDocuments: (groupKeys) => request('/api/dispatch-mobile/run-documents/publish', { method: 'POST', data: withDispatcher({ group_keys: groupKeys }) }),
  driverRunDocuments: () => request('/api/driver/run-documents'),
  auctionListings: () => request('/api/auction/listings?status=all'),
  createAuctionListing: (payload) => request('/api/auction/listings', { method: 'POST', data: withDispatcher(payload) }),
  bidAuctionListing: (listingId, payload) => request(`/api/auction/listings/${listingId}/bid`, { method: 'POST', data: withDispatcher(payload) }),
  claimAuctionListing: (listingId, payload) => request(`/api/auction/listings/${listingId}/claim`, { method: 'POST', data: withDispatcher(payload) }),
  fleetLocations: () => request('/api/dispatch-mobile/fleet/latest-locations'),
  financeSummary: () => request('/api/dispatch-mobile/finance/summary'),
  financeLedger: () => request('/api/dispatch-mobile/finance/ledger'),
  financeDriverExpenses: (params = {}) => request(`/api/dispatch-mobile/finance/driver-expenses${toQuery(params)}`)
};

