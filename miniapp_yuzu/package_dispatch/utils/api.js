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
  if (/confirm/i.test(code) && /order/i.test(code)) {
    return pendingCount > 0 ? `还有 ${pendingCount} 单未确认` : '还有订单未确认，请先完成审核';
  }
  if (/review/i.test(code) && /document|pdf/i.test(code)) return '请先确认 PDF';
  return String(err && (err.userMessage || err.message || err.detail) || code || '请求失败，请稍后重试');
}

function normalizeApiError(body, statusCode) {
  const payload = body && typeof body === 'object' ? { ...body } : { error: 'request_failed' };
  payload.statusCode = Number(statusCode || 0);
  payload.backendError = String(payload.error || 'request_failed');
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
              reject(normalizeApiError(res.data, res.statusCode));
            });
            return;
          }
          if (res.statusCode === 401 && path.indexOf('/login') < 0) {
            clearSession();
            wx.reLaunch({ url: '/package_dispatch/pages/home/index' });
          }
          reject(normalizeApiError(res.data, res.statusCode));
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
        reject(normalizeApiError(res.data, res.statusCode));
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
  parseDailyText: (text) => request('/api/dispatch-mobile/parser/daily', { method: 'POST', data: withDispatcher({ text }) }),
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
  materializeFixedTour: (payload) => request('/api/dispatch-mobile/fixed-tour/materialize', { method: 'POST', data: withDispatcher(payload) }),
  resourceDrivers: (status = '') => request(`/api/resources/drivers${toQuery({ status })}`),
  updateResourceDriver: (id, data) => request(`/api/resources/drivers/${id}`, { method: 'PUT', data }),
  deleteResourceDriver: (id) => request(`/api/resources/drivers/${id}`, { method: 'DELETE' }),
  resourceVehicles: (status = '') => request(`/api/resources/vehicles${toQuery({ status })}`),
  updateResourceVehicle: (id, data) => request(`/api/resources/vehicles/${id}`, { method: 'PUT', data }),
  resourceLibrary: () => request('/api/dispatch-mobile/resource-library'),
  updateResourceDriverStatus: (data) => request('/api/dispatch-mobile/resource-library/driver-status', { method: 'POST', data }),
  updateResourceDriverHealth: (data) => request('/api/dispatch-mobile/resource-library/driver-health', { method: 'POST', data }),
  updateResourceVehicleInspection: (data) => request('/api/dispatch-mobile/resource-library/vehicle-inspection', { method: 'POST', data }),
  updateResourceVehicleStatus: (data) => request('/api/dispatch-mobile/resource-library/vehicle-status', { method: 'POST', data }),
  resourceLibraryFileUrl: (fileKey) => `${API_CONFIG.baseUrl}/api/dispatch-mobile/resource-library/file${toQuery({ file: fileKey })}`,
  assignOrders: (payload) => request('/api/dispatch-mobile/dispatch/assign', { method: 'POST', data: withDispatcher(payload) }),
  importDailyAssignments: (payload) => request('/api/dispatch-mobile/daily-import/assign', { method: 'POST', data: withDispatcher(payload) }),
  assignments: () => request('/api/dispatch-mobile/assignments'),
  runGroups: (date) => request(`/api/dispatch-mobile/run-groups${toQuery({ date })}`),
  confirmRunOrder: (data) => request('/api/dispatch-mobile/run-confirm', { method: 'POST', data: withDispatcher(data) }),
  generateRunDocument: (groupKey) => request('/api/dispatch-mobile/run-documents/generate', { method: 'POST', data: withDispatcher({ group_key: groupKey }) }),
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

