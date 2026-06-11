const api = require('../../utils/api');
const session = require('../../utils/session');
const router = require('../../utils/role-router');

const PORT_META = {
  agency: {
    title: '旅行社登录',
    eyebrow: 'AGENCY',
    accountLabel: '登录代码',
    placeholder: 'AGA2026 / 080-7101-0000',
    button: '进入旅行社'
  },
  dispatch: {
    title: '车公司登录',
    eyebrow: 'DISPATCH',
    accountLabel: '公司账号',
    placeholder: 'SKR-08070010000',
    button: '进入车公司'
  }
};

function bridgeLegacySession(port, payload, baseUrl) {
  if (port === 'agency') {
    wx.setStorageSync('tourflow_agency_api_base_url', baseUrl);
    wx.setStorageSync('tourflow_agency_session', payload);
    return;
  }
  wx.setStorageSync('wx_dispatch_api_base_url', baseUrl);
  wx.setStorageSync(`dispatcher_session:${baseUrl}`, payload);
  wx.setStorageSync('dispatch_active_tab_path', '/package_dispatch/pages/home/index');
  wx.removeStorageSync('dispatcher_session');
  wx.removeStorageSync('dispatch_manual_logout');
}

Page({
  data: {
    port: 'agency',
    meta: PORT_META.agency,
    loginCode: '',
    password: '',
    loading: false,
    message: ''
  },

  onLoad(query = {}) {
    const port = query.port || session.getSelectedPort() || 'agency';
    this.setData({
      port,
      meta: PORT_META[port] || PORT_META.agency
    });
  },

  onLoginCodeInput(event) {
    this.setData({ loginCode: event.detail.value });
  },

  onPasswordInput(event) {
    this.setData({ password: event.detail.value });
  },

  async submit() {
    const loginCode = String(this.data.loginCode || '').trim();
    const password = String(this.data.password || '').trim();
    if (!loginCode || !password) {
      this.setData({ message: '请输入账号和密码。' });
      return;
    }
    this.setData({ loading: true, message: '' });
    try {
      const payload = this.data.port === 'agency'
        ? await api.loginAgency(loginCode, password)
        : await api.loginDispatch(loginCode, password);
      const nextSession = {
        ...payload,
        port: this.data.port,
        login_code: loginCode,
        display_name: payload.agency_name
          || payload.company_name
          || (payload.dispatcher && payload.dispatcher.dispatcher_name)
          || loginCode
      };
      session.setSession(nextSession);
      bridgeLegacySession(this.data.port, nextSession, api.getBaseUrl());
      getApp().globalData.session = nextSession;
      wx.redirectTo({ url: router.homeForSession(nextSession) });
    } catch (err) {
      this.setData({
        message: err && err.error ? `登录失败：${err.error}` : '登录失败，请检查账号密码或 API。'
      });
    } finally {
      this.setData({ loading: false });
    }
  }
});
