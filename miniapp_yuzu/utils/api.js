const API_STORAGE_KEY = 'yuzu_api_base_url';
const FORCE_LOCAL_KEY = 'yuzu_force_local_api';
const TRIAL_BASE_URL = 'https://api-trial.taxi-airport.jp';
const LOCAL_BASE_URL = 'http://127.0.0.1:18765';
const DEFAULT_BASE_URL = TRIAL_BASE_URL;
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

function getRuntimeInfo() {
  const device = typeof wx.getDeviceInfo === 'function' ? wx.getDeviceInfo() : {};
  const app = typeof wx.getAppBaseInfo === 'function' ? wx.getAppBaseInfo() : {};
  const win = typeof wx.getWindowInfo === 'function' ? wx.getWindowInfo() : {};
  return {
    device,
    app,
    window: win,
    platform: device.platform || app.platform || ''
  };
}

function syncEnvironmentBaseUrl() {
  wx.removeStorageSync(FORCE_LOCAL_KEY);
  setBaseUrl(TRIAL_BASE_URL);
}

function request(path, options = {}) {
  const session = options.session || null;
  const token = options.token || (session && session.token);
  const headers = {
    'Content-Type': 'application/json',
    ...(options.header || {})
  };
  if (token && options.authType === 'agency') {
    headers['X-Agency-Token'] = token;
  }
  if (token && options.authType === 'dispatch') {
    headers.Authorization = `Bearer ${token}`;
  }
  return new Promise((resolve, reject) => {
    const requestPayload = options.data || {};
    wx.request({
      url: `${API_CONFIG.baseUrl}${path}`,
      method: options.method || 'GET',
      data: requestPayload,
      timeout: options.timeout || REQUEST_TIMEOUT_MS,
      header: headers,
      success: (res) => {
        const payload = res.data || {};
        if (res.statusCode >= 400 || payload.error) {
          console.error('[yuzu api failed]', {
            path,
            method: options.method || 'GET',
            statusCode: res.statusCode,
            requestPayload,
            responseBody: payload
          });
          reject(payload.error ? payload : { error: `request_failed_${res.statusCode}` });
          return;
        }
        if (path.indexOf('/login') >= 0) {
          console.info('[yuzu api success]', { path, statusCode: res.statusCode, hasToken: !!payload.token });
        }
        resolve(payload);
      },
      fail: (error) => {
        console.error('[yuzu api network failed]', {
          path,
          method: options.method || 'GET',
          baseUrl: API_CONFIG.baseUrl,
          requestPayload,
          error
        });
        const errMsg = error && error.errMsg ? String(error.errMsg) : '';
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

function loginAgency(loginCode, password) {
  return request('/api/agency-portal/login', {
    method: 'POST',
    data: { portal_code: loginCode, password }
  });
}

function loginDispatch(username, password, wxCode = '') {
  return request('/api/dispatch-mobile/login', {
    method: 'POST',
    data: {
      username,
      password,
      wx_code: wxCode,
      client_type: wxCode ? 'dispatch_miniapp' : 'web'
    }
  });
}

module.exports = {
  API_CONFIG,
  TRIAL_BASE_URL,
  LOCAL_BASE_URL,
  setBaseUrl,
  getBaseUrl,
  getRuntimeInfo,
  syncEnvironmentBaseUrl,
  request,
  loginAgency,
  loginDispatch
};
