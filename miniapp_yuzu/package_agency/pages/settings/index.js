const api = require('../../utils/api');

function emptyForm() {
  return {
    contact_name: '',
    contact_phone: '',
    company_address: '',
    bank_name: '',
    bank_branch: '',
    bank_account_type: '普通',
    bank_account_number: '',
    bank_account_holder: '',
    registry_pdf_name: '',
    registry_pdf_url: ''
  };
}

Page({
  data: {
    session: null,
    form: emptyForm(),
    loading: false,
    saving: false,
    uploading: false,
    message: '',
    canManageAccounts: false,
    accounts: [],
    accountRoleLabels: ['客服', '导游', '财务'],
    accountRole: 'agency_customer_service',
    accountName: '',
    accountPhone: '',
    accountSaving: false
  },

  onShow() {
    const session = api.getSession();
    if (!session || !session.token) {
      wx.redirectTo({ url: '/package_agency/pages/home/index' });
      return;
    }
    const role = (session.user && session.user.role) || (session.account && session.account.role) || '';
    this.setData({ session, canManageAccounts: role === 'agency_owner' });
    wx.setNavigationBarTitle({
      title: session.agency && session.agency.name ? session.agency.name : '旅行社设置'
    });
    this.loadProfile();
    if (role === 'agency_owner') this.loadAccounts();
  },

  loadAccounts() {
    api.accounts().then((accounts) => this.setData({ accounts })).catch((err) => {
      this.setData({ message: err.error || err.message || '账号读取失败' });
    });
  },

  onAccountFieldInput(e) {
    const field = e.currentTarget.dataset.field;
    if (field) this.setData({ [field]: e.detail.value });
  },

  onAccountRoleChange(e) {
    const roles = ['agency_customer_service', 'agency_guide', 'agency_finance'];
    this.setData({ accountRole: roles[Number(e.detail.value) || 0] });
  },

  createAccount() {
    if (!this.data.accountName.trim() || !this.data.accountPhone.trim()) {
      wx.showToast({ title: '请填写姓名和手机号', icon: 'none' });
      return;
    }
    this.setData({ accountSaving: true });
    api.createAccount({
      role: this.data.accountRole,
      display_name: this.data.accountName.trim(),
      phone: this.data.accountPhone.trim()
    }).then(() => {
      this.setData({ accountSaving: false, accountName: '', accountPhone: '', message: '账号已创建，初始密码为手机号后 6 位' });
      this.loadAccounts();
    }).catch((err) => this.setData({ accountSaving: false, message: err.error || err.message || '账号创建失败' }));
  },

  onAccountAction(e) {
    const id = e.currentTarget.dataset.id;
    const action = e.currentTarget.dataset.action;
    const calls = {
      disable: api.disableAccount,
      enable: api.enableAccount,
      reset: api.resetAccountPassword,
      unbind: api.unbindAccountWechat
    };
    const call = calls[action];
    if (!call) return;
    call(id).then(() => {
      this.setData({ message: action === 'reset' ? '密码已重置为手机号后 6 位' : '账号状态已更新' });
      this.loadAccounts();
    }).catch((err) => this.setData({ message: err.error || err.message || '操作失败' }));
  },

  loadProfile() {
    this.setData({ loading: true, message: '' });
    api.profile()
      .then((res) => {
        const profile = res.profile || {};
        this.setData({
          loading: false,
          form: {
            ...emptyForm(),
            ...profile
          }
        });
      })
      .catch((err) => {
        this.setData({ loading: false, message: err.error || err.message || '资料读取失败' });
      });
  },

  onFieldInput(e) {
    const field = e.currentTarget.dataset.field;
    if (!field) return;
    this.setData({ [`form.${field}`]: e.detail.value });
  },

  saveProfile() {
    this.setData({ saving: true, message: '' });
    const payload = { ...this.data.form };
    delete payload.registry_pdf_name;
    delete payload.registry_pdf_url;
    api.updateProfile(payload)
      .then((res) => {
        this.setData({
          saving: false,
          form: { ...emptyForm(), ...(res.profile || {}) },
          message: '旅行社资料已保存'
        });
      })
      .catch((err) => {
        this.setData({ saving: false, message: err.error || err.message || '保存失败' });
      });
  },

  uploadRegistryPdf() {
    wx.chooseMessageFile({
      count: 1,
      type: 'file',
      success: (res) => {
        const file = (res.tempFiles || [])[0];
        if (!file) return;
        if (!/\.pdf$/i.test(file.name || '')) {
          wx.showToast({ title: '请选择 PDF 文件', icon: 'none' });
          return;
        }
        this.setData({ uploading: true, message: '' });
        api.fileToDataUrl(file.path, 'application/pdf')
          .then((fileBase64) => api.uploadProfileRegistryPdf({
            file_name: file.name,
            file_base64: fileBase64
          }))
          .then((res2) => {
            this.setData({
              uploading: false,
              form: { ...emptyForm(), ...(res2.profile || this.data.form) },
              message: '藤本 PDF 已上传'
            });
          })
          .catch((err) => {
            this.setData({ uploading: false, message: err.error || err.message || '上传失败' });
          });
      }
    });
  }
});

