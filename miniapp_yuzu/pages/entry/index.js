const session = require('../../utils/session');
const router = require('../../utils/role-router');

Page({
  data: {
    currentSession: null
  },

  onShow() {
    const currentSession = session.getSession();
    this.setData({ currentSession });
  },

  choosePort(event) {
    const port = event.currentTarget.dataset.port;
    session.setSelectedPort(port);
    wx.navigateTo({ url: `/pages/login/index?port=${port}` });
  },

  continueSession() {
    const currentSession = session.getSession();
    wx.redirectTo({ url: router.homeForSession(currentSession) });
  },

  clearSession() {
    session.clearSession();
    this.setData({ currentSession: null });
  }
});
