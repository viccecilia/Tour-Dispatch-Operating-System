const api = require('../../utils/api');

Page({
  data: {
    session: { dispatcher: {} },
    shared: { tables: {} },
    baseUrl: api.getBaseUrl()
  },
  onShow() {
    this.setData({ session: api.getSession() || { dispatcher: {} }, baseUrl: api.getBaseUrl() });
    this.loadShared();
  },
  loadShared() {
    api.sharedState()
      .then((shared) => this.setData({ shared }))
      .catch(() => this.setData({ shared: { tables: {} } }));
  },
  logout() {
    api.clearSession();
    this.setData({ session: { dispatcher: {} } });
    wx.switchTab({ url: '/pages/index/index' });
  }
});
