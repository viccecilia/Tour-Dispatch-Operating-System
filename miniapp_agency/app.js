const api = require('./utils/api');

App({
  onLaunch() {
    api.syncEnvironmentBaseUrl();
  },
  globalData: {
    appName: 'TourFlow'
  }
});
