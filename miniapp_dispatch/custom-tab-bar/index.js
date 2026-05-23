Component({
  data: {
    selected: 0,
    list: [
      { pagePath: "/pages/index/index", text: "首页", icon: "首" },
      { pagePath: "/pages/dispatch/index", text: "派车", icon: "派" },
      { pagePath: "/pages/map/index", text: "地图", icon: "图" },
      { pagePath: "/pages/finance/index", text: "财务", icon: "财" },
      { pagePath: "/pages/profile/index", text: "我的", icon: "我" }
    ]
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
    syncSelected() {
      const pages = getCurrentPages();
      const current = pages[pages.length - 1];
      const route = `/${current?.route || ""}`;
      const selected = this.data.list.findIndex((item) => item.pagePath === route);
      if (selected >= 0 && selected !== this.data.selected) {
        this.setData({ selected });
      }
    },

    switchTab(event) {
      const index = Number(event.currentTarget.dataset.index || 0);
      const target = this.data.list[index];
      if (!target) return;
      wx.switchTab({ url: target.pagePath });
    }
  }
});
