const api = require('../../utils/api');

Page({
  data: {
    summary: {},
    orders: [],
    message: ''
  },

  onShow() {
    this.loadFinance();
  },

  loadFinance() {
    Promise.all([
      api.financeSummary().catch(() => ({})),
      api.financeLedger().catch(() => ({ orders: [] }))
    ])
      .then(([summary, ledger]) => {
        const expenseSummary = summary.driver_expense_summary || {};
        this.setData({
          summary: {
            ...summary,
            driver_advance_total: expenseSummary.advance_total || expenseSummary.driver_advance_total || 0,
            driver_collect_total: expenseSummary.collect_total || expenseSummary.driver_collect_total || 0
          },
          orders: (ledger.orders || summary.orders || []).slice(0, 30),
          message: ''
        });
      })
      .catch(() => this.setData({ message: '无法加载财务数据。' }));
  }
});
