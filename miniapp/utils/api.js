const API_STORAGE_KEY = 'wx_dispatch_api_base_url';
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

function request(path, options = {}) {
  return requestWithRefresh(path, options, false);
}

function requestWithRefresh(path, options = {}, retried = false) {
  const session = wx.getStorageSync('driver_session') || null;
  const token = options.token || (session && (session.access_token || session.token));
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${API_CONFIG.baseUrl}${path}`,
      method: options.method || 'GET',
      data: options.data || {},
      header: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      success: (res) => {
        if (res.statusCode === 401 && !retried && session && session.refresh_token && path !== '/api/auth/refresh') {
          wx.request({
            url: `${API_CONFIG.baseUrl}/api/auth/refresh`,
            method: 'POST',
            data: { refresh_token: session.refresh_token },
            header: { 'Content-Type': 'application/json' },
            success: (refreshRes) => {
              if (refreshRes.statusCode >= 200 && refreshRes.statusCode < 300 && refreshRes.data && refreshRes.data.token) {
                wx.setStorageSync('driver_session', refreshRes.data);
                requestWithRefresh(path, options, true).then(resolve).catch(reject);
              } else {
                wx.removeStorageSync('driver_session');
                reject(refreshRes.data || { error: 'unauthorized' });
              }
            },
            fail: reject
          });
          return;
        }
        if (res.statusCode >= 400) {
          reject(res.data || { error: `request_failed_${res.statusCode}` });
          return;
        }
        resolve(res.data);
      },
      fail: reject
    });
  });
}

module.exports = {
  API_CONFIG,
  TRIAL_BASE_URL,
  LOCAL_BASE_URL,
  setBaseUrl,
  getBaseUrl,
  useCloudBaseUrl,
  resetBaseUrl,
  request,
  login: (username, password) => request('/api/auth/login', {
    method: 'POST',
    data: { username, password }
  }),
  loginPhone: (phone, password, wxCode) => request('/api/auth/login-phone', {
    method: 'POST',
    data: { phone, password, wx_code: wxCode, client_type: 'driver_miniapp' }
  }),
  registerPhone: (data) => request('/api/auth/register', {
    method: 'POST',
    data: { ...data, client_type: data.client_type || 'driver_miniapp' }
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
  resourceReminders: () => request('/api/resources/reminders'),
  reminderSettings: () => request('/api/settings/reminders'),
  updateReminderSettings: (data) => request('/api/settings/reminders', { method: 'PUT', data }),
  parseText: (text) => request('/api/parser/text', { method: 'POST', data: { text } }),
  parseExcel: (data) => request('/api/parser/excel', { method: 'POST', data }),
  parseVoice: (data) => request('/api/parser/voice', { method: 'POST', data }),
  listDrafts: () => request('/api/parser/drafts'),
  getDraft: (id) => request(`/api/parser/drafts/${id}`),
  updateDraft: (id, data) => request(`/api/parser/drafts/${id}`, { method: 'PUT', data }),
  confirmDraft: (id) => request(`/api/parser/drafts/${id}/confirm`, { method: 'POST' }),
  discardDraft: (id) => request(`/api/parser/drafts/${id}`, { method: 'DELETE' }),
  driverAssignments: () => request('/api/driver/assignments'),
  driverAssignmentDetail: (_driverId, assignmentId) => request(`/api/driver/assignments/${assignmentId}`),
  driverReports: () => request('/api/driver/reports'),
  driverDashboard: () => request('/api/driver/dashboard'),
  driverProfile: () => request('/api/driver/profile'),
  updateDriverProfile: (data) => request('/api/driver/profile', { method: 'POST', data }),
  driverWorkbench: () => request('/api/driver/workbench'),
  driverWorkflowEvents: () => request('/api/driver/workflow-events'),
  submitDriverWorkflowEvent: (data) => request('/api/driver/workflow-event', { method: 'POST', data }),
  driverExpenses: () => request('/api/driver/expenses'),
  submitDriverExpense: (data) => request('/api/driver/expense', { method: 'POST', data }),
  driverHistory: (_driverId, filters = {}) => {
    const query = Object.keys(filters)
      .filter((key) => filters[key] !== undefined && filters[key] !== '')
      .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(filters[key])}`)
      .join('&');
    return request(`/api/driver/history${query ? `?${query}` : ''}`);
  },
  driverIncome: () => request('/api/driver/income'),
  driverNotifications: () => request('/api/driver/notifications'),
  markDriverNotificationRead: (_driverId, notificationId) => request(`/api/driver/notifications/${notificationId}/read`, { method: 'POST', data: {} }),
  submitDriverReport: (data) => request('/api/driver/report', { method: 'POST', data }),
  submitDriverIncident: (data) => request('/api/driver/incident', { method: 'POST', data }),
  uploadDriverEvidence: (data) => request('/api/driver/evidence', { method: 'POST', data }),
  driverEvidence: (_driverId, assignmentId = '') => request(`/api/driver/evidence${assignmentId ? `?assignment_id=${assignmentId}` : ''}`),
  submitDriverLocation: (data) => request('/api/driver/location', { method: 'POST', data }),
  driverLocations: () => request('/api/driver/locations')
};
