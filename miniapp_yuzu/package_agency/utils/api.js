const API_STORAGE_KEY = 'tourflow_agency_api_base_url';
const SESSION_STORAGE_KEY = 'tourflow_agency_session';
const TRIAL_BASE_URL = 'https://api-trial.taxi-airport.jp';
const LOCAL_BASE_URL = 'http://127.0.0.1:18765';
const DEFAULT_BASE_URL = TRIAL_BASE_URL;

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

function useLocalBaseUrl() {
  setBaseUrl(LOCAL_BASE_URL);
}

function useTrialBaseUrl() {
  setBaseUrl(TRIAL_BASE_URL);
}

function getRuntimeInfo() {
  const deviceInfo = typeof wx.getDeviceInfo === 'function' ? wx.getDeviceInfo() : {};
  const appBaseInfo = typeof wx.getAppBaseInfo === 'function' ? wx.getAppBaseInfo() : {};
  const windowInfo = typeof wx.getWindowInfo === 'function' ? wx.getWindowInfo() : {};
  return {
    device: deviceInfo,
    app: appBaseInfo,
    window: windowInfo,
    platform: deviceInfo.platform || appBaseInfo.platform || ''
  };
}

function syncEnvironmentBaseUrl() {
  try {
    const runtimeInfo = getRuntimeInfo();
    if (runtimeInfo.platform === 'devtools') {
      setBaseUrl(LOCAL_BASE_URL);
      return;
    }
  } catch (err) {
    // Keep trial endpoint when environment detection is unavailable.
  }
  useTrialBaseUrl();
}

function getSession() {
  return wx.getStorageSync(SESSION_STORAGE_KEY) || null;
}

function setSession(session) {
  wx.setStorageSync(SESSION_STORAGE_KEY, session || null);
}

function clearSession() {
  wx.removeStorageSync(SESSION_STORAGE_KEY);
}

function request(path, options = {}) {
  const session = getSession();
  const token = options.agencyToken || (session && session.token);
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${API_CONFIG.baseUrl}${path}`,
      method: options.method || 'GET',
      data: options.data || {},
      header: {
        'Content-Type': 'application/json',
        ...(path.indexOf('/api/agency-portal') === 0 && token ? { 'X-Agency-Token': token } : {}),
        ...(options.header || {})
      },
      success: (res) => {
        const payload = res.data || {};
        if (res.statusCode >= 400 || payload.error) {
          if (res.statusCode === 401 || payload.error === 'agency_unauthorized' || payload.error === 'invalid_agency_credentials') {
            clearSession();
          }
          reject(payload.error ? payload : { error: `request_failed_${res.statusCode}` });
          return;
        }
        resolve(payload);
      },
      fail: reject
    });
  });
}

function listFrom(payload, keys) {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (payload && typeof payload === 'object') {
    for (let i = 0; i < keys.length; i += 1) {
      const value = payload[keys[i]];
      if (Array.isArray(value)) {
        return value;
      }
    }
  }
  return [];
}

function fileToDataUrl(filePath, mimeType = 'application/octet-stream') {
  return new Promise((resolve, reject) => {
    wx.getFileSystemManager().readFile({
      filePath,
      encoding: 'base64',
      success: (res) => resolve(`data:${mimeType};base64,${res.data}`),
      fail: reject
    });
  });
}

function assetUrl(path) {
  if (!path) {
    return '';
  }
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  return `${API_CONFIG.baseUrl}${path.charAt(0) === '/' ? path : `/${path}`}`;
}

module.exports = {
  API_CONFIG,
  TRIAL_BASE_URL,
  LOCAL_BASE_URL,
  setBaseUrl,
  getBaseUrl,
  useLocalBaseUrl,
  useTrialBaseUrl,
  syncEnvironmentBaseUrl,
  getRuntimeInfo,
  getSession,
  setSession,
  clearSession,
  request,
  fileToDataUrl,
  assetUrl,
  agencies: () => request('/api/agency-portal/agencies').then((res) => listFrom(res, ['agencies', 'items', 'data'])),
  resolveAccount: (loginCode) => request(`/api/agency-portal/resolve?portal_code=${encodeURIComponent(loginCode)}`),
  login: (loginCode, password) => request('/api/agency-portal/login', {
    method: 'POST',
    data: { portal_code: loginCode, password }
  }),
  profile: () => request('/api/agency-portal/profile'),
  updateProfile: (payload) => request('/api/agency-portal/profile', {
    method: 'POST',
    data: payload
  }),
  uploadProfileRegistryPdf: (payload) => request('/api/agency-portal/profile/registry-pdf', {
    method: 'POST',
    data: payload
  }),
  orders: () => request('/api/agency-portal/orders').then((res) => listFrom(res, ['orders', 'items', 'data'])),
  parseOrders: (text, mode, batch) => request('/api/agency-portal/orders/parse', {
    method: 'POST',
    data: { text, mode, batch }
  }),
  createOrder: (payload) => request('/api/agency-portal/orders', {
    method: 'POST',
    data: payload
  }),
  auctionListings: (status = 'listed') => request(`/api/agency-portal/auction-listings?status=${encodeURIComponent(status)}`).then((res) => listFrom(res, ['listings', 'items', 'data'])),
  publishOrderToAuction: (orderId, payload) => request(`/api/agency-portal/orders/${orderId}/publish-auction`, {
    method: 'POST',
    data: payload
  }),
  withdrawOrderFromHall: (orderId) => request(`/api/agency-portal/orders/${orderId}/withdraw`, {
    method: 'POST',
    data: {}
  }),
  changeRequests: () => request('/api/agency-portal/change-requests').then((res) => listFrom(res, ['requests', 'items', 'data'])),
  createChangeRequest: (orderId, payload) => request(`/api/agency-portal/orders/${orderId}/change-requests`, {
    method: 'POST',
    data: payload
  }),
  uploadItineraryPdf: (orderId, payload) => request(`/api/agency-portal/orders/${orderId}/itinerary-pdf`, {
    method: 'POST',
    data: payload
  }),
  uploadPaymentReceipt: (orderId, payload) => request(`/api/agency-portal/orders/${orderId}/payment-receipt`, {
    method: 'POST',
    data: payload
  })
};

