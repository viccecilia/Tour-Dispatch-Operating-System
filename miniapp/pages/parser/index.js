const api = require('../../utils/api');

const emptyDraft = {
  order_date: '',
  start_time: '',
  end_time: '',
  pickup_location: '',
  dropoff_location: '',
  order_type: '',
  vehicle_type: '',
  passenger_count: '',
  luggage_count: '',
  guest_name: '',
  guest_contact: '',
  agency_name: '',
  price: '',
  remark: ''
};

Page({
  data: {
    text: '',
    drafts: [],
    selected: null,
    saving: false
  },

  onShow() {
    this.loadDrafts();
  },

  onTextInput(event) {
    this.setData({ text: event.detail.value });
  },

  loadDrafts() {
    api.listDrafts().then((res) => {
      this.setData({ drafts: res.drafts || [] });
    });
  },

  onParseText() {
    if (!this.data.text.trim()) {
      wx.showToast({ title: '请粘贴订单文本', icon: 'none' });
      return;
    }
    api.parseText(this.data.text).then((res) => {
      if (res.draft) {
        wx.showToast({ title: '已生成草稿' });
        this.setData({ text: '', selected: res.draft });
        this.loadDrafts();
      }
    });
  },

  onVoiceEntry() {
    api.parseVoice({ voice_text: this.data.text || '语音入口草稿，等待补充识别文本' }).then((res) => {
      if (res.draft) {
        wx.showToast({ title: '已生成语音草稿' });
        this.setData({ selected: res.draft });
        this.loadDrafts();
      }
    });
  },

  onSelectDraft(event) {
    api.getDraft(event.currentTarget.dataset.id).then((res) => {
      this.setData({ selected: { ...emptyDraft, ...(res.draft || {}) } });
    });
  },

  onFieldInput(event) {
    const key = event.currentTarget.dataset.key;
    this.setData({ [`selected.${key}`]: event.detail.value });
  },

  onSaveDraft() {
    if (!this.data.selected) {
      return;
    }
    this.setData({ saving: true });
    api.updateDraft(this.data.selected.id, this.data.selected).then((res) => {
      this.setData({ saving: false, selected: res.draft || this.data.selected });
      wx.showToast({ title: '草稿已保存' });
      this.loadDrafts();
    });
  },

  onConfirmDraft() {
    if (!this.data.selected) {
      return;
    }
    api.confirmDraft(this.data.selected.id).then((res) => {
      if (res.order_id) {
        wx.showToast({ title: '已生成订单' });
        this.setData({ selected: res.draft });
        this.loadDrafts();
      } else {
        wx.showToast({ title: '确认失败', icon: 'none' });
      }
    });
  },

  onDiscardDraft() {
    if (!this.data.selected) {
      return;
    }
    api.discardDraft(this.data.selected.id).then((res) => {
      if (res.deleted) {
        wx.showToast({ title: '草稿已作废' });
        this.setData({ selected: res.draft });
        this.loadDrafts();
      }
    });
  },

  clearSelected() {
    this.setData({ selected: null });
  }
});
