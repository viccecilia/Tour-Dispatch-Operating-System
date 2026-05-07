const api = require('../../utils/api');

Page({
  data: {
    loading: false,
    loadError: '',
    summary: {
      order_count: 0,
      total_amount: 0,
      pending_amount: 0,
      settled_amount: 0,
      today_amount: 0,
      missing_price_orders: 0,
      by_agency: [],
      pending_orders: []
    }
  },

  onShow() {
    this.loadSummary();
  },

  loadSummary() {
    this.setData({ loading: true, loadError: '' });
    api.financeSummary()
      .then((summary) => {
        this.setData({ summary, loading: false });
      })
      .catch(() => {
        this.setData({ loading: false, loadError: '财务概览加载失败' });
      });
  }
});
