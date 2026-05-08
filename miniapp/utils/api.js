const API_CONFIG = {
  // 微信开发者工具本机预览默认使用 127.0.0.1。
  // 真机预览时请改成电脑局域网 IP，例如 http://192.168.1.23:8000。
  // 如果后端端口被占用，可配合 WX_DISPATCH_PORT 切换为 18765。
  baseUrl: 'http://127.0.0.1:8000'
};

function setBaseUrl(baseUrl) {
  API_CONFIG.baseUrl = String(baseUrl || '').replace(/\/$/, '');
}

function getBaseUrl() {
  return API_CONFIG.baseUrl;
}

function request(path, options = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${API_CONFIG.baseUrl}${path}`,
      method: options.method || 'GET',
      data: options.data || {},
      header: {
        'Content-Type': 'application/json',
        ...(options.token ? { Authorization: `Bearer ${options.token}` } : {})
      },
      success: (res) => resolve(res.data),
      fail: reject
    });
  });
}

module.exports = {
  API_CONFIG,
  setBaseUrl,
  getBaseUrl,
  request,
  login: (username, password) => request('/api/auth/login', {
    method: 'POST',
    data: { username, password }
  }),
  dashboardSummary: () => request('/api/dashboard/summary'),
  financeSummary: () => request('/api/finance/summary'),
  listOrders: (filters = {}) => {
    const query = Object.keys(filters)
      .filter((key) => filters[key] !== undefined && filters[key] !== '')
      .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(filters[key])}`)
      .join('&');
    return request(`/api/orders${query ? `?${query}` : ''}`);
  },
  getOrder: (id) => request(`/api/orders/${id}`),
  createOrder: (data) => request('/api/orders', { method: 'POST', data }),
  updateOrder: (id, data) => request(`/api/orders/${id}`, { method: 'PUT', data }),
  deleteOrder: (id) => request(`/api/orders/${id}`, { method: 'DELETE' }),
  unassignedOrders: () => request('/api/dispatch/unassigned-orders'),
  dispatchDrivers: () => request('/api/dispatch/drivers'),
  dispatchVehicles: () => request('/api/dispatch/vehicles'),
  assignOrders: (data) => request('/api/dispatch/assign', { method: 'POST', data }),
  cancelAssignment: (data) => request('/api/dispatch/cancel', { method: 'POST', data }),
  reassignOrders: (data) => request('/api/dispatch/reassign', { method: 'POST', data }),
  dispatchAssignments: () => request('/api/dispatch/assignments'),
  routeSuggestion: (orderIds = []) => request(`/api/dispatch/route-suggestion?order_ids=${orderIds.join(',')}`),
  dispatchCalendar: (filters = {}) => {
    const query = Object.keys(filters)
      .filter((key) => filters[key] !== undefined && filters[key] !== '')
      .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(filters[key])}`)
      .join('&');
    return request(`/api/calendar/dispatch${query ? `?${query}` : ''}`);
  },
  dispatchCalendarDetail: (assignmentId) => request(`/api/calendar/dispatch/detail/${assignmentId}`),
  listDrivers: () => request('/api/resources/drivers'),
  createDriver: (data) => request('/api/resources/drivers', { method: 'POST', data }),
  updateDriver: (id, data) => request(`/api/resources/drivers/${id}`, { method: 'PUT', data }),
  listVehicles: () => request('/api/resources/vehicles'),
  createVehicle: (data) => request('/api/resources/vehicles', { method: 'POST', data }),
  updateVehicle: (id, data) => request(`/api/resources/vehicles/${id}`, { method: 'PUT', data }),
  parseText: (text) => request('/api/parser/text', { method: 'POST', data: { text } }),
  parseExcel: (data) => request('/api/parser/excel', { method: 'POST', data }),
  parseVoice: (data) => request('/api/parser/voice', { method: 'POST', data }),
  listDrafts: () => request('/api/parser/drafts'),
  getDraft: (id) => request(`/api/parser/drafts/${id}`),
  updateDraft: (id, data) => request(`/api/parser/drafts/${id}`, { method: 'PUT', data }),
  confirmDraft: (id) => request(`/api/parser/drafts/${id}/confirm`, { method: 'POST' }),
  discardDraft: (id) => request(`/api/parser/drafts/${id}`, { method: 'DELETE' }),
  driverAssignments: (driverId) => request(`/api/driver/assignments?driver_id=${driverId}`),
  driverAssignmentDetail: (driverId, assignmentId) => request(`/api/driver/assignments/${assignmentId}?driver_id=${driverId}`),
  driverReports: (driverId) => request(`/api/driver/reports?driver_id=${driverId}`),
  driverDashboard: (driverId) => request(`/api/driver/dashboard?driver_id=${driverId}`),
  submitDriverReport: (data) => request('/api/driver/report', { method: 'POST', data })
};
