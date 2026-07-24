const SESSION_KEY = 'yuzu_session';
const SELECTED_PORT_KEY = 'yuzu_selected_port';

function getSelectedPort() {
  return wx.getStorageSync(SELECTED_PORT_KEY) || '';
}

function setSelectedPort(port) {
  wx.setStorageSync(SELECTED_PORT_KEY, port || '');
}

function getSession() {
  const current = wx.getStorageSync(SESSION_KEY);
  const selectedPort = getSelectedPort() || (current && current.port) || '';
  const agency = wx.getStorageSync('tourflow_agency_session');
  if ((selectedPort === 'agency' || !current) && agency && agency.token) {
    return { ...agency, port: 'agency' };
  }
  const baseUrl = wx.getStorageSync('wx_dispatch_api_base_url') || 'https://api-trial.taxi-airport.jp';
  const dispatch = wx.getStorageSync(`dispatcher_session:${baseUrl}`) || wx.getStorageSync('dispatcher_session');
  if ((selectedPort === 'dispatch' || !current) && dispatch && dispatch.token) {
    return { ...dispatch, port: 'dispatch' };
  }
  if (selectedPort && current && current.port && current.port !== selectedPort) {
    return null;
  }
  if (current) return current;
  return null;
}

function setSession(session) {
  wx.setStorageSync(SESSION_KEY, session || null);
}

function clearSession() {
  wx.removeStorageSync(SESSION_KEY);
}

function getRole(session = getSession()) {
  if (!session) return '';
  if (session.port === 'agency') {
    return session.role || session.agency_role || 'agency_admin';
  }
  const dispatcher = session.dispatcher || {};
  const user = session.user || {};
  return user.role || dispatcher.dispatcher_role || session.role || '';
}

module.exports = {
  getSelectedPort,
  setSelectedPort,
  getSession,
  setSession,
  clearSession,
  getRole
};
