const api = require('../../utils/api');

const CONTACT_FIELDS = [
  { key: 'phone', label: '手机号', placeholder: '手机号' },
  { key: 'wechat', label: 'WeChat', placeholder: '微信号' },
  { key: 'line', label: 'Line', placeholder: 'Line ID' },
  { key: 'whatsapp', label: 'WhatsApp', placeholder: 'WhatsApp' },
  { key: 'kakao', label: 'Kakao', placeholder: 'KakaoTalk' },
  { key: 'email', label: '邮箱', placeholder: 'email' }
];

const ROLE_LABELS = {
  admin: '管理员',
  dispatcher: '调度',
  operations_manager: '运行管理',
  driver: '司机'
};

Page({
  data: {
    session: { dispatcher: {}, user: {} },
    role: '',
    roleLabel: '-',
    isDriverTheme: false,
    isTealTheme: false,
    driverId: 0,
    driver: {},
    contactFields: CONTACT_FIELDS,
    contactForm: {},
    saving: false,
    message: ''
  },

  onShow() {
    api.setActiveTab('/pages/profile/index');
    this.refreshTabBar();
    const session = api.getSession() || { dispatcher: {}, user: {} };
    const role = api.getRole(session);
    const isDriverTheme = role === 'driver';
    const isTealTheme = role === 'driver' || role === 'operations_manager';
    const driverId = Number(session.user && session.user.profile_id || 0);
    this.setData({
      session,
      role,
      roleLabel: ROLE_LABELS[role] || role || '-',
      isDriverTheme,
      isTealTheme,
      driverId
    });
    if (isDriverTheme && driverId) this.loadDriverProfile();
  },

  refreshTabBar() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().refresh();
    }
  },

  loadDriverProfile() {
    api.driverProfile(this.data.driverId)
      .then((res) => {
        const driver = res.driver || {};
        this.setData({
          driver,
          contactForm: {
            phone: driver.phone || '',
            wechat: driver.wechat || '',
            line: driver.line || '',
            whatsapp: driver.whatsapp || '',
            kakao: driver.kakao || '',
            email: driver.email || '',
            license_due_date: driver.license_due_date || '',
            health_check_due_date: driver.health_check_due_date || ''
          }
        });
      })
      .catch(() => this.setData({ message: '无法读取司机资料。' }));
  },

  onInput(e) {
    this.setData({ [`contactForm.${e.currentTarget.dataset.key}`]: e.detail.value });
  },

  saveDriverProfile() {
    if (!this.data.driverId || this.data.saving) return;
    this.setData({ saving: true, message: '' });
    api.updateDriverProfile({
      driver_id: this.data.driverId,
      ...this.data.contactForm
    }).then((res) => {
      this.setData({ saving: false, driver: res.driver || this.data.driver, message: '资料已保存。' });
    }).catch(() => this.setData({ saving: false, message: '保存失败。' }));
  },

  uploadLicense() {
    this.uploadDocument('license');
  },

  uploadHealthCheck() {
    this.uploadDocument('health_check');
  },

  uploadDocument(documentType) {
    if (!this.data.driverId || this.data.saving) return;
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const file = res.tempFiles && res.tempFiles[0];
        if (!file || !file.tempFilePath) return;
        this.readFileBase64(file.tempFilePath)
          .then((imageBase64) => {
            const dateKey = documentType === 'license' ? 'license_due_date' : 'health_check_due_date';
            this.setData({ saving: true, message: '' });
            return api.uploadDriverProfileDocument({
              driver_id: this.data.driverId,
              document_type: documentType,
              image_base64: imageBase64,
              [dateKey]: this.data.contactForm[dateKey] || ''
            });
          })
          .then((res) => {
            this.setData({
              saving: false,
              driver: res.driver || this.data.driver,
              message: documentType === 'license' ? '驾照文件已上传。' : '健康体检文件已上传。'
            });
          })
          .catch(() => this.setData({ saving: false, message: '上传失败。' }));
      }
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
  },

  logout() {
    api.clearSession();
    wx.reLaunch({ url: '/pages/index/index' });
  }
});
