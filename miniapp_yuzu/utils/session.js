const SESSION_KEY = 'yuzu_session';
const SELECTED_PORT_KEY = 'yuzu_selected_port';

function getSelectedPort() {
  return wx.getStorageSync(SELECTED_PORT_KEY) || '';
}

function setSelectedPort(port) {
  wx.setStorageSync(SELECTED_PORT_KEY, port || '');
}

function getSession() {
  return wx.getStorageSync(SESSION_KEY) || null;
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
  return session.role || user.role || dispatcher.dispatcher_role || '';
}

module.exports = {
  getSelectedPort,
  setSelectedPort,
  getSession,
  setSession,
  clearSession,
  getRole
};
