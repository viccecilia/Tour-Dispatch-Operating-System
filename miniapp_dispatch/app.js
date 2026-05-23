App({
  globalData: {
    dispatcherSession: null
  },
  onLaunch() {
    const session = wx.getStorageSync('dispatcher_session');
    if (session) {
      this.globalData.dispatcherSession = session;
    }
  }
});
