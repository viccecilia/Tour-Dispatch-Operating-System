const API_CONFIG = {
  baseUrl: 'http://127.0.0.1:18765'
};

function setBaseUrl(baseUrl) {
  API_CONFIG.baseUrl = String(baseUrl || '').replace(/\/$/, '');
}

function getBaseUrl() {
  return API_CONFIG.baseUrl;
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
  getSession,
  setSession,
  clearSession,
  withDispatcher,
  request,
  login: (username, password) => request('/api/dispatch-mobile/login', { method: 'POST', data: { username, password } }),
  context: () => request('/api/dispatch-mobile/context'),
  dashboard: () => {
    const session = getSession();
    const dispatcher = session && session.dispatcher ? session.dispatcher : {};
    const query = dispatcher.dispatcher_id ? `?dispatcher_id=${dispatcher.dispatcher_id}` : '';
    return request(`/api/dispatch-mobile/dashboard${query}`);
  },
  sharedState: () => request('/api/dispatch-mobile/shared-state'),
  parseText: (text) => request('/api/dispatch-mobile/parser/text', { method: 'POST', data: withDispatcher({ text, batch: true }) }),
  drafts: () => request('/api/parser/drafts'),
  updateDraft: (id, data) => request(`/api/dispatch-mobile/drafts/${id}`, { method: 'PUT', data: withDispatcher(data) }),
  updateOrder: (id, data) => request(`/api/orders/${id}`, { method: 'PUT', data: withDispatcher(data) }),
  confirmDraft: (id) => request(`/api/parser/drafts/${id}/confirm`, { method: 'POST', data: withDispatcher({}) }),
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
  drivers: () => request('/api/dispatch/drivers'),
  vehicles: () => request('/api/dispatch/vehicles'),
  assignOrders: (payload) => request('/api/dispatch/assign', { method: 'POST', data: withDispatcher(payload) }),
  assignments: () => request('/api/dispatch/assignments'),
  fleetLocations: () => request('/api/fleet/latest-locations'),
  financeSummary: () => request('/api/finance/summary'),
  financeLedger: () => request('/api/finance/ledger')
};
