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
  driverAssignments: (driverId) => request(`/api/driver/assignments?driver_id=${driverId}`),
  driverAssignmentDetail: (driverId, assignmentId) => request(`/api/driver/assignments/${assignmentId}?driver_id=${driverId}`),
  driverReports: (driverId) => request(`/api/driver/reports?driver_id=${driverId}`),
  driverDashboard: (driverId) => request(`/api/driver/dashboard?driver_id=${driverId}`),
  driverProfile: (driverId) => request(`/api/driver/profile?driver_id=${driverId}`),
  updateDriverProfile: (data) => request('/api/driver/profile', { method: 'POST', data }),
  driverWorkbench: (driverId) => request(`/api/driver/workbench?driver_id=${driverId}`),
  driverWorkflowEvents: (driverId) => request(`/api/driver/workflow-events?driver_id=${driverId}`),
  submitDriverWorkflowEvent: (data) => request('/api/driver/workflow-event', { method: 'POST', data }),
  driverExpenses: (driverId) => request(`/api/driver/expenses?driver_id=${driverId}`),
  submitDriverExpense: (data) => request('/api/driver/expense', { method: 'POST', data }),
  driverHistory: (driverId, filters = {}) => {
    const query = Object.keys(filters)
      .filter((key) => filters[key] !== undefined && filters[key] !== '')
      .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(filters[key])}`)
      .join('&');
    return request(`/api/driver/history?driver_id=${driverId}${query ? `&${query}` : ''}`);
  },
  driverIncome: (driverId) => request(`/api/driver/income?driver_id=${driverId}`),
  driverNotifications: (driverId) => request(`/api/driver/notifications?driver_id=${driverId}`),
  markDriverNotificationRead: (driverId, notificationId) => request(`/api/driver/notifications/${notificationId}/read`, { method: 'POST', data: { driver_id: driverId } }),
  submitDriverReport: (data) => request('/api/driver/report', { method: 'POST', data }),
  submitDriverIncident: (data) => request('/api/driver/incident', { method: 'POST', data }),
  uploadDriverEvidence: (data) => request('/api/driver/evidence', { method: 'POST', data }),
  driverEvidence: (driverId, assignmentId = '') => request(`/api/driver/evidence?driver_id=${driverId}${assignmentId ? `&assignment_id=${assignmentId}` : ''}`),
  submitDriverLocation: (data) => request('/api/driver/location', { method: 'POST', data }),
  driverLocations: (driverId) => request(`/api/driver/locations?driver_id=${driverId}`)
};
