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

function sessionExpiresAtMs(session) {
  if (!session || typeof session !== 'object') return 0;
  const expiresAt = Number(session.expires_at || session.expiresAt || 0);
  if (Number.isFinite(expiresAt) && expiresAt > 0) {
    return expiresAt > 1000000000000 ? expiresAt : expiresAt * 1000;
  }
  return 0;
}

function isSessionActive(session, nowMs = Date.now()) {
  if (!session || !session.token || !session.port) return false;
  const expiresAtMs = sessionExpiresAtMs(session);
  // Older session payloads did not include an expiry. Preserve compatibility
  // and let their API request perform the authoritative server-side check.
  if (!expiresAtMs) return true;
  return expiresAtMs > Number(nowMs || Date.now()) + 15000;
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
  isSessionActive,
  clearSession,
  getRole
};
