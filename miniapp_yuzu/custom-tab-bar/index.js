const sessionStore = require('../utils/session');
const portNav = require('../utils/port-nav');

Component({
  data: {
    visible: false,
    selected: 0,
    roleClass: '',
    list: []
  },

  lifetimes: {
    attached() {
      this.syncSelected();
    }
  },

  pageLifetimes: {
    show() {
      this.syncSelected();
    }
  },

  methods: {
    currentRoute() {
      const pages = typeof getCurrentPages === 'function' ? getCurrentPages() : [];
      if (!Array.isArray(pages) || !pages.length) return '';
      const current = pages[pages.length - 1] || {};
      return current.route ? `/${current.route}` : '';
    },

    syncSelected() {
      try {
        const session = sessionStore.getSession();
        const role = sessionStore.getRole(session);
        const route = this.currentRoute();
        const tabSource = session ? portNav.tabsForCurrent(null, route) : [];
        const list = Array.isArray(tabSource) ? tabSource.map((item) => ({
          pagePath: item.url,
          text: item.label
        })) : [];
        const activePath = list.some((item) => item.pagePath === route)
          ? route
          : wx.getStorageSync('yuzu_active_tab_path') || wx.getStorageSync('dispatch_active_tab_path');
        const selected = list.findIndex((item) => item.pagePath === activePath);
        this.setData({
          visible: Boolean(session && list.length),
          list,
          selected: selected >= 0 ? selected : 0,
          roleClass: (session && session.port === 'agency') || ['driver', 'operations_manager', 'ops'].indexOf(role) >= 0 ? 'driver-theme' : ''
        });
      } catch (err) {
        console.warn('[custom-tab sync failed]', err);
        this.setData({ visible: false, list: [], selected: 0, roleClass: '' });
      }
    },

    refresh() {
      this.syncSelected();
    },

    switchTab(event) {
      const index = Number(event.currentTarget.dataset.index || 0);
      const target = this.data.list[index];
      if (!target) return;
      wx.setStorageSync('yuzu_active_tab_path', target.pagePath);
      this.setData({ selected: index });
      if (target.pagePath === this.currentRoute()) {
        this.syncSelected();
        return;
      }
      wx.reLaunch({
        url: target.pagePath,
        success: () => this.syncSelected(),
        fail: () => wx.redirectTo({
          url: target.pagePath,
          success: () => this.syncSelected()
        })
      });
    }
  }
});
