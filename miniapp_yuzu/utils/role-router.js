function homeForSession(session) {
  if (!session) {
    return '/pages/entry/index';
  }
  if (session.port === 'agency') {
    return '/package_agency/pages/home/index';
  }
  if (session.port === 'dispatch') {
    return '/package_dispatch/pages/home/index';
  }
  return '/pages/entry/index';
}

module.exports = {
  homeForSession
};
