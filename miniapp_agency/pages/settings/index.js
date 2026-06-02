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
    message: ''
  },

  onShow() {
    const session = api.getSession();
    if (!session || !session.token) {
      wx.switchTab({ url: '/pages/index/index' });
      return;
    }
    this.setData({ session });
    wx.setNavigationBarTitle({
      title: session.agency && session.agency.name ? session.agency.name : '旅行社设置'
    });
    this.loadProfile();
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
