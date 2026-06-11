const API_STORAGE_KEY = 'yuzu_api_base_url';
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
  try {
    const runtime = getRuntimeInfo();
    if (runtime.platform === 'devtools') {
      setBaseUrl(LOCAL_BASE_URL);
      return;
    }
  } catch (err) {
    // Keep cloud endpoint when runtime detection is not available.
  }
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
    wx.request({
      url: `${API_CONFIG.baseUrl}${path}`,
      method: options.method || 'GET',
      data: options.data || {},
      header: headers,
      success: (res) => {
        const payload = res.data || {};
        if (res.statusCode >= 400 || payload.error) {
          console.error('[yuzu api failed]', {
            path,
            method: options.method || 'GET',
            statusCode: res.statusCode,
            requestPayload: options.data || {},
            responseBody: payload
          });
          reject(payload.error ? payload : { error: `request_failed_${res.statusCode}` });
          return;
        }
        resolve(payload);
      },
      fail: (error) => {
        console.error('[yuzu api network failed]', {
          path,
          method: options.method || 'GET',
          requestPayload: options.data || {},
          error
        });
        reject(error);
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
