const api = require('../../utils/api');

Page({
  data: {
    driverId: 0,
    expenses: [],
    income: {},
    form: {
      expense_kind: 'advance',
      amount: '',
      note: '',
      receipt_image_base64: '',
      receipt_file_name: ''
    },
    message: '',
    loading: false,
    saving: false
  },

  onShow() {
    api.setActiveTab('/package_dispatch/pages/expense/index');
    const session = api.getSession();
    const role = api.getRole(session);
    if (!session || role !== 'driver') {
      wx.redirectTo({ url: '/package_dispatch/pages/home/index' });
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
        expenses: (expenseRes.expenses || []).map((item) => ({
          ...item,
          kind_label: item.expense_kind === 'collect' ? '代收上交' : '垫付报销',
          status_label: this.statusLabel(item.submit_status),
          receipt_label: item.receipt_photo_url ? '已上传领収书' : '无领収书'
        })),
        income,
        loading: false
      });
    }).catch(() => this.setData({ loading: false, message: '费用记录加载失败。' }));
  },

  statusLabel(status) {
    return {
      submitted: '待财务确认',
      in_hand: '待财务确认',
      confirmed: '已确认',
      rejected: '已驳回'
    }[status] || status || '-';
  },

  onInput(e) {
    this.setData({ [`form.${e.currentTarget.dataset.key}`]: e.detail.value });
  },

  onKindChange(e) {
    const nextKind = Number(e.detail.value) === 1 ? 'collect' : 'advance';
    const nextForm = { ...this.data.form, expense_kind: nextKind };
    if (nextKind === 'collect') {
      nextForm.receipt_image_base64 = '';
      nextForm.receipt_file_name = '';
    }
    this.setData({ form: nextForm });
  },

  chooseReceipt() {
    if (this.data.saving) return;
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const file = res.tempFiles && res.tempFiles[0];
        if (!file || !file.tempFilePath) return;
        this.readFileBase64(file.tempFilePath)
          .then((base64) => {
            const parts = file.tempFilePath.split(/[\\/]/);
            this.setData({
              'form.receipt_image_base64': base64,
              'form.receipt_file_name': parts[parts.length - 1] || 'receipt.jpg'
            });
          })
          .catch(() => wx.showToast({ title: '照片读取失败', icon: 'none' }));
      }
    });
  },

  clearReceipt() {
    this.setData({ 'form.receipt_image_base64': '', 'form.receipt_file_name': '' });
  },

  submitExpense() {
    const amount = Number(this.data.form.amount || 0);
    if (!amount) {
      wx.showToast({ title: '请输入金额', icon: 'none' });
      return;
    }
    const payload = {
      driver_id: this.data.driverId,
      expense_kind: this.data.form.expense_kind,
      category: this.data.form.expense_kind === 'collect' ? '司机代收' : '司机垫付',
      amount,
      note: this.data.form.note
    };
    if (this.data.form.receipt_image_base64) {
      payload.receipt_image_base64 = this.data.form.receipt_image_base64;
    }
    this.setData({ saving: true, message: '' });
    api.submitDriverExpense(payload).then((res) => {
      if (res && res.success === false) throw new Error(res.error || 'submit_failed');
      this.setData({
        saving: false,
        form: { expense_kind: 'advance', amount: '', note: '', receipt_image_base64: '', receipt_file_name: '' },
        message: '已提交，财务端可以查看。'
      });
      wx.showToast({ title: '已提交', icon: 'success' });
      this.loadExpenses();
    }).catch((error) => {
      this.setData({ saving: false, message: `提交失败：${error.message || '请稍后重试'}` });
      wx.showToast({ title: '提交失败', icon: 'none' });
    });
  },

  readFileBase64(path) {
    return new Promise((resolve, reject) => {
      wx.getFileSystemManager().readFile({
        filePath: path,
        encoding: 'base64',
        success: (res) => resolve(res.data),
        fail: reject
      });
    });
  }
});

