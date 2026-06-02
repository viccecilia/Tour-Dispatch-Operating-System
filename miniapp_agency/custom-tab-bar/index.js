Component({
  data: {
    selected: 0,
    list: [
      { pagePath: '/pages/index/index', text: '首页' },
      { pagePath: '/pages/orders/index', text: '入单' },
      { pagePath: '/pages/hall/index', text: '大厅' },
      { pagePath: '/pages/tracking/index', text: '跟踪' },
      { pagePath: '/pages/calendar/index', text: '日历' }
    ]
  },

  methods: {
    switchTab(e) {
      const index = Number(e.currentTarget.dataset.index || 0);
      const item = this.data.list[index];
      if (!item || index === this.data.selected) return;
      wx.switchTab({ url: item.pagePath });
    }
  }
});
