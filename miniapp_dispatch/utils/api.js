const API_STORAGE_KEY = 'wx_dispatch_api_base_url';
const DEFAULT_BASE_URL = 'http://localhost:18765';
const CLOUD_BASE_URL = 'https://api.example.com';

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

function getSession() {
  return wx.getStorageSync('dispatcher_session') || null;
}

function setSession(session) {
  wx.setStorageSync('dispatcher_session', session);
}

function clearSession() {
  wx.removeStorageSync('dispatcher_session');
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
  setBaseUrl,
  getBaseUrl,
  useCloudBaseUrl,
  resetBaseUrl,
  getSession,
  setSession,
  clearSession,
  withDispatcher,
  request,
  login: (username, password, wxOpenid = '') => request('/api/dispatch-mobile/login', { method: 'POST', data: { username, password, wx_openid: wxOpenid, client_type: wxOpenid ? 'dispatch_miniapp' : 'web' } }),
  loginPhone: (phone, password, wxOpenid) => request('/api/dispatch-mobile/login', { method: 'POST', data: { phone, password, wx_openid: wxOpenid, client_type: 'dispatch_miniapp' } }),
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
