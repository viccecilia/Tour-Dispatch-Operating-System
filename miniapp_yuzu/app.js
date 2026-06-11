const api = require('./utils/api');
const session = require('./utils/session');

App({
  globalData: {
    appName: '柚子调度',
    session: null
  },

  onLaunch() {
    api.syncEnvironmentBaseUrl();
    this.globalData.session = session.getSession();
  }
});
