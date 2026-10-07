const api = require('../../utils/api');
const session = require('../../utils/session');
const router = require('../../utils/role-router');

const PORT_META = {
  agency: {
    accountLabel: '登录账号',
    placeholder: 'AGA2026 / 080-7101-0000',
    button: '登录旅行社端'
  },
  dispatch: {
    accountLabel: '登录账号',
    placeholder: '08070010000',
    button: '登录车公司端'
  }
};

function bridgeLegacySession(port, payload, baseUrl) {
  if (port === 'agency') {
    wx.setStorageSync('tourflow_agency_api_base_url', baseUrl);
    wx.setStorageSync('tourflow_agency_session', payload);
    wx.removeStorageSync('agency_manual_logout');
    return;
  }
  const dispatchSession = Object.assign({}, payload, { port: 'dispatch' });
  wx.setStorageSync('wx_dispatch_api_base_url', baseUrl);
  wx.setStorageSync('dispatcher_session', dispatchSession);
  wx.setStorageSync(`dispatcher_session:${baseUrl}`, dispatchSession);
  wx.setStorageSync('dispatcher_session:http://127.0.0.1:18765', dispatchSession);
  wx.setStorageSync('yuzu_session', dispatchSession);
  wx.setStorageSync('yuzu_selected_port', 'dispatch');
  wx.setStorageSync('dispatch_active_tab_path', '/package_dispatch/pages/home/index');
  wx.removeStorageSync('dispatch_manual_logout');
}

function forceRoute(url, page, reason = 'login') {
  console.info('[yozi force route]', { url, reason });
  wx.reLaunch({
    url,
    success: () => console.info('[yozi relaunch success]', { url, reason }),
    fail: (error) => {
      console.error('[yozi relaunch failed]', error);
      wx.redirectTo({
        url,
        success: () => console.info('[yozi redirect success]', { url, reason }),
        fail: (redirectError) => {
          console.error('[yozi redirect failed]', redirectError);
          if (page) {
            page.setData({
              message: `登录成功，但跳转失败：${redirectError && redirectError.errMsg ? redirectError.errMsg : url}`
            });
          }
        }
      });
    },
    complete: (res) => console.info('[yozi relaunch complete]', { url, reason, errMsg: res && res.errMsg })
  });
}

Page({
  data: {
    port: 'agency',
    meta: PORT_META.agency,
    loginCode: '',
    password: '',
    loading: false,
    message: '',
    showHelp: false
  },

  onLoad(query = {}) {
    api.syncEnvironmentBaseUrl();
    const port = PORT_META[query.port] ? query.port : (session.getSelectedPort() || 'agency');
    session.setSelectedPort(port);
    this.setData({
      port,
      meta: PORT_META[port] || PORT_META.agency
    });
    this.autoLoginTried = false;
  },

  onShow() {
    api.syncEnvironmentBaseUrl();
    const currentSession = session.getSession();
    if (currentSession && currentSession.token && currentSession.port) {
      const homeUrl = router.homeForSession(currentSession);
      if (homeUrl && homeUrl !== '/pages/entry/index') {
        forceRoute(homeUrl, this, 'login-onshow');
      }
    }
    if (!this.autoLoginTried && !wx.getStorageSync(this.data.port === 'agency' ? 'agency_manual_logout' : 'dispatch_manual_logout')) {
      this.tryWechatAutoLogin();
    }
  },

  getWechatLoginCode() {
    return new Promise((resolve, reject) => {
      wx.login({
        success: (res) => res.code ? resolve(res.code) : reject({ error: 'wechat_login_failed' }),
        fail: () => reject({ error: 'wechat_login_failed' })
      });
    });
  },

  normalizeWechatSession(payload) {
    if (this.data.port !== 'agency') return Object.assign({}, payload, { port: 'dispatch' });
    const user = payload.user || {};
    return Object.assign({}, payload, {
      port: 'agency',
      account: {
        id: user.agency_account_id,
        role: user.role,
        display_name: user.display_name,
        phone: user.phone,
        company_id: user.organization_id,
        company_code: user.company_code,
        company_name: user.company_name
      },
      agency: {
        id: user.organization_id,
        name: user.company_name,
        company_code: user.company_code
      }
    });
  },

  tryWechatAutoLogin() {
    this.autoLoginTried = true;
    this.setData({ loading: true, message: '' });
    this.getWechatLoginCode()
      .then((code) => api.loginWechat(code, this.data.port))
      .then((payload) => {
        const nextSession = this.normalizeWechatSession(payload);
        session.setSelectedPort(this.data.port);
        session.setSession(nextSession);
        bridgeLegacySession(this.data.port, nextSession, api.getBaseUrl());
        getApp().globalData.session = nextSession;
        forceRoute(router.homeForSession(nextSession), this, 'wechat-auto-login');
      })
      .catch((err) => {
        const code = err && err.error;
        this.setData({ message: code && code !== 'wechat_not_bound' ? `微信自动登录失败：${code}` : '' });
      })
      .finally(() => this.setData({ loading: false }));
  },

  switchPort(event) {
    const port = event.currentTarget.dataset.port || 'agency';
    if (!PORT_META[port]) return;
    session.setSelectedPort(port);
    this.setData({
      port,
      meta: PORT_META[port],
      message: ''
    });
  },

  toggleHelp() {
    this.setData({ showHelp: !this.data.showHelp });
  },

  onLoginCodeInput(event) {
    this.setData({ loginCode: event.detail.value });
  },

  onPasswordInput(event) {
    this.setData({ password: event.detail.value });
  },

  async submit() {
    api.syncEnvironmentBaseUrl();
    const loginCode = String(this.data.loginCode || '').trim();
    const password = String(this.data.password || '').trim();
    if (!loginCode || !password) {
      this.setData({ message: '请输入账号和密码。' });
      return;
    }
    if (loginCode.toLowerCase() === 'admin') {
      this.setData({ message: 'admin / admin123 是平台总后台账号，请在 Web 总后台登录。' });
      return;
    }
    this.setData({ loading: true, message: '' });
    try {
      console.info('[yozi login submit]', { port: this.data.port, baseUrl: api.getBaseUrl(), loginCode });
      const wxCode = await this.getWechatLoginCode();
      const payload = this.data.port === 'agency'
        ? await api.loginAgency(loginCode, password, wxCode)
        : await api.loginDispatch(loginCode, password, wxCode);
      console.info('[yozi login success]', {
        port: this.data.port,
        role: payload && payload.user ? payload.user.role : payload.role,
        hasToken: !!(payload && payload.token)
      });
      const nextSession = Object.assign({}, payload, {
        port: this.data.port,
        login_code: loginCode,
        display_name: payload.agency_name
          || payload.company_name
          || (payload.dispatcher && payload.dispatcher.dispatcher_name)
          || loginCode
      });
      session.setSelectedPort(this.data.port);
      session.setSession(nextSession);
      bridgeLegacySession(this.data.port, nextSession, api.getBaseUrl());
      getApp().globalData.session = nextSession;
      const homeUrl = router.homeForSession(nextSession);
      console.info('[yozi login route]', { homeUrl, selectedPort: this.data.port });
      forceRoute(homeUrl, this, 'login-submit');
      return;
    } catch (err) {
      console.error('[yozi login failed]', err);
      this.setData({
        message: err && err.error ? `登录失败：${err.error}` : '登录失败，请检查账号密码或 API。'
      });
    } finally {
      if (this.data.loading) this.setData({ loading: false });
    }
  }
});
