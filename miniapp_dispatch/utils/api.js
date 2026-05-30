const API_STORAGE_KEY = 'wx_dispatch_api_base_url';
const ACTIVE_TAB_KEY = 'dispatch_active_tab_path';
const TRIAL_BASE_URL = 'https://api-trial.taxi-airport.jp';
const LOCAL_BASE_URL = 'http://127.0.0.1:18765';
const DEFAULT_BASE_URL = TRIAL_BASE_URL;
const CLOUD_BASE_URL = TRIAL_BASE_URL;

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

function useCloudBaseUrl(baseUrl = CLOUD_BASE_URL) {
  setBaseUrl(baseUrl);
}

function resetBaseUrl() {
  wx.removeStorageSync(API_STORAGE_KEY);
  API_CONFIG.baseUrl = DEFAULT_BASE_URL;
}

function setActiveTab(path) {
  wx.setStorageSync(ACTIVE_TAB_KEY, path);
}

function getSession() {
  return wx.getStorageSync('dispatcher_session') || null;
}

function setSession(session) {
  wx.setStorageSync('dispatcher_session', session);
}

function clearSession() {
  wx.removeStorageSync('dispatcher_session');
}

function getRole(session = getSession()) {
  const dispatcher = session && session.dispatcher ? session.dispatcher : {};
  const user = session && session.user ? session.user : {};
  return user.role || dispatcher.dispatcher_role || '';
}

function canAccess(feature, session = getSession()) {
  const role = getRole(session);
  const rules = {
    dispatch: ['admin', 'dispatcher'],
    map: ['admin', 'dispatcher', 'operations_manager', 'driver'],
    finance: ['admin'],
    profile: ['admin', 'dispatcher', 'operations_manager', 'driver']
  };
  return (rules[feature] || []).indexOf(role) >= 0;
}

function request(path, options = {}) {
  const session = getSession();
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${API_CONFIG.baseUrl}${path}`,
      method: options.method || 'GET',
      data: options.data || {},
      header: {
        'Content-Type': 'application/json',
        ...(session && session.token ? { Authorization: `Bearer ${session.token}` } : {})
      },
      success: (res) => {
        if (res.statusCode >= 400) {
          reject(res.data || { error: 'request_failed' });
          return;
        }
        resolve(res.data);
      },
      fail: reject
    });
  });
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
  setActiveTab,
  getSession,
  setSession,
  clearSession,
  getRole,
  canAccess,
  withDispatcher,
  request,
  login: (username, password, wxCode = '') => request('/api/dispatch-mobile/login', { method: 'POST', data: { username, password, wx_code: wxCode, client_type: wxCode ? 'dispatch_miniapp' : 'web' } }),
  loginPhone: (phone, password, wxCode = '') => request('/api/dispatch-mobile/login', { method: 'POST', data: { phone, password, wx_code: wxCode, client_type: wxCode ? 'dispatch_miniapp' : 'web' } }),
  loginWechat: (wxCode) => request('/api/dispatch-mobile/wechat-login', { method: 'POST', data: { wx_code: wxCode, client_type: 'dispatch_miniapp' } }),
  registerPhone: (data) => request('/api/auth/register', { method: 'POST', data: { ...data, client_type: data.client_type || 'dispatch_miniapp' } }),
  context: () => request('/api/dispatch-mobile/context'),
  dashboard: () => {
    const session = getSession();
    const dispatcher = session && session.dispatcher ? session.dispatcher : {};
    const query = dispatcher.dispatcher_id ? `?dispatcher_id=${dispatcher.dispatcher_id}` : '';
    return request(`/api/dispatch-mobile/dashboard${query}`);
  },
  sharedState: () => request('/api/dispatch-mobile/shared-state'),
  parseText: (text) => request('/api/dispatch-mobile/parser/text', { method: 'POST', data: withDispatcher({ text, batch: true }) }),
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
  notifications: () => request('/api/dispatch-mobile/notifications'),
  driverNotifications: (driverId) => request(`/api/driver/notifications?driver_id=${driverId}`),
  driverAssignments: (driverId) => request(`/api/driver/assignments?driver_id=${driverId}`),
  driverWorkbench: (driverId) => request(`/api/driver/workbench?driver_id=${driverId}`),
  driverProfile: (driverId) => request(`/api/driver/profile?driver_id=${driverId}`),
  updateDriverProfile: (data) => request('/api/driver/profile', { method: 'POST', data }),
  uploadDriverProfileDocument: (data) => request('/api/driver/profile-document', { method: 'POST', data }),
  driverExpenses: (driverId) => request(`/api/driver/expenses?driver_id=${driverId}`),
  driverIncome: (driverId) => request(`/api/driver/income?driver_id=${driverId}`),
  submitDriverReport: (data) => request('/api/driver/report', { method: 'POST', data }),
  submitDriverWorkflowEvent: (data) => request('/api/driver/workflow-event', { method: 'POST', data }),
  submitDriverExpense: (data) => request('/api/driver/expense', { method: 'POST', data }),
  auditLogs: () => {
    const session = getSession();
    const dispatcher = session && session.dispatcher ? session.dispatcher : {};
    const query = dispatcher.dispatcher_id ? `?dispatcher_id=${dispatcher.dispatcher_id}` : '';
    return request(`/api/dispatch-mobile/audit-logs${query}`);
  },
  drivers: () => request('/api/dispatch-mobile/drivers'),
  vehicles: () => request('/api/dispatch-mobile/vehicles'),
  assignOrders: (payload) => request('/api/dispatch-mobile/dispatch/assign', { method: 'POST', data: withDispatcher(payload) }),
  assignments: () => request('/api/dispatch-mobile/assignments'),
  fleetLocations: () => request('/api/dispatch-mobile/fleet/latest-locations'),
  financeSummary: () => request('/api/dispatch-mobile/finance/summary'),
  financeLedger: () => request('/api/dispatch-mobile/finance/ledger')
};
