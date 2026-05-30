const api = require('../../utils/api');

Page({
  data: {
    driverId: 0,
    expenses: [],
    income: {},
    form: {
      expense_kind: 'advance',
      amount: '',
      note: ''
    },
    message: '',
    loading: false
  },

  onShow() {
    api.setActiveTab('/pages/expense/index');
    const session = api.getSession();
    const role = api.getRole(session);
    if (!session || role !== 'driver') {
      wx.switchTab({ url: '/pages/index/index' });
      return;
    }
    this.refreshTabBar();
    const driverId = Number(session.user && session.user.profile_id || 0);
    this.setData({ driverId });
    this.loadExpenses();
  },

  refreshTabBar() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().refresh();
    }
  },

  loadExpenses() {
    if (!this.data.driverId) return;
    this.setData({ loading: true, message: '' });
    Promise.all([
      api.driverExpenses(this.data.driverId).catch(() => ({ expenses: [] })),
      api.driverIncome(this.data.driverId).catch(() => ({}))
    ]).then(([expenseRes, income]) => {
      this.setData({
        expenses: expenseRes.expenses || [],
        income,
        loading: false
      });
    }).catch(() => this.setData({ loading: false, message: '无法加载费用。' }));
  },

  onInput(e) {
    this.setData({ [`form.${e.currentTarget.dataset.key}`]: e.detail.value });
  },

  onKindChange(e) {
    this.setData({ 'form.expense_kind': Number(e.detail.value) === 1 ? 'collect' : 'advance' });
  },

  submitExpense() {
    const amount = Number(this.data.form.amount || 0);
    if (!amount) {
      wx.showToast({ title: '请输入金额', icon: 'none' });
      return;
    }
    api.submitDriverExpense({
      driver_id: this.data.driverId,
      expense_kind: this.data.form.expense_kind,
      amount,
      note: this.data.form.note
    }).then(() => {
      this.setData({ form: { expense_kind: 'advance', amount: '', note: '' } });
      wx.showToast({ title: '已提交', icon: 'success' });
      this.loadExpenses();
    }).catch(() => wx.showToast({ title: '提交失败', icon: 'none' }));
  }
});
