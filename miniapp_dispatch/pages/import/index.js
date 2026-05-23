const api = require('../../utils/api');

const SAMPLE_TEXT = '5.29 08:00 KIX接机大阪 3代 绿450\n5.29 10:20 大阪市内-京都市内 包车 3代 1500\n5.29 13:30 心斋桥微笑酒店-关西机场 3代 儿童座椅 绿600';

Page({
  data: {
    text: SAMPLE_TEXT,
    drafts: [],
    visibleDrafts: [],
    expandedId: '',
    editingId: '',
    editing: {},
    loading: false,
    message: '',
    riskSummary: {
      high: 0,
      medium: 0,
      ok: 0
    },
    foldedDraftCount: 0
  },

  onShow() {
    this.loadDrafts();
  },

  onText(e) {
    this.setData({ text: e.detail.value });
  },

  parse() {
    if (!api.getSession()) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      wx.switchTab({ url: '/pages/index/index' });
      return;
    }
    if (!String(this.data.text || '').trim()) {
      wx.showToast({ title: '请先粘贴订单', icon: 'none' });
      return;
    }
    this.setData({ loading: true, message: '' });
    api.parseText(this.data.text)
      .then((res) => this.setData({ message: `已生成 ${res.count || 0} 条草稿`, loading: false }))
      .then(() => this.loadDrafts())
      .catch(() => this.setData({ loading: false, message: '解析失败，原文不会丢失。' }));
  },

  loadDrafts() {
    api.drafts()
      .then((res) => {
        const drafts = this.decorateDrafts((res.drafts || []).filter((item) => item.parse_status !== 'confirmed').slice(0, 80));
        const problemDrafts = drafts.filter((item) => item.riskLevel !== 'ok');
        const okPreview = drafts.filter((item) => item.riskLevel === 'ok').slice(0, 3);
        const visibleDrafts = problemDrafts.concat(okPreview);
        this.setData({
          drafts,
          visibleDrafts,
          foldedDraftCount: Math.max(0, drafts.length - visibleDrafts.length),
          riskSummary: this.buildRiskSummary(drafts)
        });
      })
      .catch(() => this.setData({ drafts: [], visibleDrafts: [], foldedDraftCount: 0, riskSummary: { high: 0, medium: 0, ok: 0 } }));
  },

  decorateDrafts(drafts) {
    const seen = {};
    drafts.forEach((draft) => {
      const key = [draft.order_date, draft.start_time, draft.pickup_location, draft.dropoff_location].join('|');
      if (key.replace(/\|/g, '')) seen[key] = (seen[key] || 0) + 1;
    });
    return drafts.map((draft) => {
      const risks = this.getDraftRisks(draft, seen);
      return {
        ...draft,
        risks,
        riskLevel: risks.length >= 2 ? 'high' : risks.length ? 'medium' : 'ok',
        routeText: `${draft.pickup_location || '待确认起点'} -> ${draft.dropoff_location || '待确认终点'}`,
        timeText: `${draft.order_date || '待确认日期'} ${draft.start_time || '待确认时间'}`
      };
    });
  },

  getDraftRisks(draft, seen) {
    const risks = [];
    if (!draft.start_time) risks.push('缺少时间');
    if (!draft.vehicle_type) risks.push('缺少车型');
    if (!draft.pickup_location || !draft.dropoff_location) risks.push('地点异常');
    if (draft.price === null || draft.price === undefined || draft.price === '' || Number(draft.price) <= 0) risks.push('价格可疑');
    const key = [draft.order_date, draft.start_time, draft.pickup_location, draft.dropoff_location].join('|');
    if (key.replace(/\|/g, '') && seen[key] > 1) risks.push('疑似重复');
    return risks;
  },

  buildRiskSummary(drafts) {
    return drafts.reduce((acc, draft) => {
      acc[draft.riskLevel] += 1;
      return acc;
    }, { high: 0, medium: 0, ok: 0 });
  },

  confirmOkDrafts() {
    const okDrafts = this.data.drafts.filter((item) => item.riskLevel === 'ok');
    if (!okDrafts.length) {
      wx.showToast({ title: '没有可直接入库草稿', icon: 'none' });
      return;
    }
    this.setData({ loading: true });
    okDrafts.reduce((chain, draft) => chain.then(() => api.confirmDraft(draft.id)), Promise.resolve())
      .then(() => {
        wx.showToast({ title: `已入库 ${okDrafts.length} 单` });
        this.setData({ loading: false });
        this.loadDrafts();
      })
      .catch(() => this.setData({ loading: false, message: '批量入库失败，请检查草稿。' }));
  },

  toggleExpand(e) {
    const id = String(e.currentTarget.dataset.id);
    this.setData({ expandedId: this.data.expandedId === id ? '' : id });
  },

  startEdit(e) {
    const id = String(e.currentTarget.dataset.id);
    const draft = this.data.drafts.find((item) => String(item.id) === id);
    if (!draft) return;
    this.setData({
      editingId: id,
      expandedId: id,
      editing: {
        order_date: draft.order_date || '',
        start_time: draft.start_time || '',
        end_time: draft.end_time || '',
        pickup_location: draft.pickup_location || '',
        dropoff_location: draft.dropoff_location || '',
        order_type: draft.order_type || '',
        vehicle_type: draft.vehicle_type || '',
        price: draft.price || '',
        agency_name: draft.agency_name || '',
        remark: draft.remark || ''
      }
    });
  },

  onEditField(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [`editing.${field}`]: e.detail.value });
  },

  saveEdit() {
    if (!this.data.editingId) return;
    this.setData({ loading: true });
    api.updateDraft(this.data.editingId, this.data.editing)
      .then(() => {
        wx.showToast({ title: '草稿已保存' });
        this.setData({ editingId: '', editing: {}, loading: false });
        this.loadDrafts();
      })
      .catch(() => this.setData({ loading: false, message: '保存失败，请稍后重试。' }));
  },

  cancelEdit() {
    this.setData({ editingId: '', editing: {} });
  },

  confirmDraft(e) {
    const id = e.currentTarget.dataset.id;
    api.confirmDraft(id)
      .then(() => {
        wx.showToast({ title: '已入库' });
        this.loadDrafts();
      })
      .catch(() => wx.showToast({ title: '入库失败', icon: 'none' }));
  }
});
