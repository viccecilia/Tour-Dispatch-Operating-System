const api = require('../../utils/api');

const AUCTION_DRAFT_KEY = 'auction_publish_draft';

Page({
  data: {
    draft: null,
    listings: [],
    startPrice: '',
    buyoutPrice: '',
    note: '',
    loading: false,
    message: ''
  },

  onShow() {
    api.setActiveTab('/pages/auction/index');
    this.refreshTabBar();
    if (!api.canAccess('auction')) {
      wx.showToast({ title: '当前账号没有订单大厅权限', icon: 'none' });
      wx.reLaunch({ url: '/pages/index/index' });
      return;
    }
    this.loadDraft();
    this.loadListings();
  },

  refreshTabBar() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().refresh();
    }
  },

  loadDraft() {
    const draft = wx.getStorageSync(AUCTION_DRAFT_KEY);
    if (!draft || !draft.order_ids || !draft.order_ids.length) {
      this.setData({ draft: null });
      return;
    }
    const total = (draft.orders || []).reduce((sum, item) => sum + Number(item.price || 0), 0);
    this.setData({
      draft,
      startPrice: total ? String(Math.round(total * 0.8)) : '',
      buyoutPrice: total ? String(Math.round(total)) : ''
    });
  },

  loadListings() {
    this.setData({ loading: true });
    api.auctionListings()
      .then((res) => {
        const listings = (res.listings || []).map((item) => ({
          ...item,
          routeText: `${item.pickup_location || '-'} → ${item.dropoff_location || '-'}`,
          timeText: `${item.order_date || '-'} ${item.start_time || ''}`,
          startPriceText: this.formatMoney(item.start_price_jpy),
          buyoutPriceText: this.formatMoney(item.buyout_price_jpy)
        }));
        this.setData({ listings, loading: false });
      })
      .catch(() => this.setData({ loading: false, message: '订单大厅加载失败，请确认后端在线。' }));
  },

  onInput(e) {
    this.setData({ [e.currentTarget.dataset.key]: e.detail.value });
  },

  publishDraft() {
    const draft = this.data.draft;
    const start = Number(this.data.startPrice || 0);
    const buyout = Number(this.data.buyoutPrice || 0);
    if (!draft || !draft.order_ids || !draft.order_ids.length) {
      wx.showToast({ title: '请先从派车页选择订单', icon: 'none' });
      return;
    }
    if (!start || !buyout) {
      wx.showToast({ title: '请填写起拍价和一口价', icon: 'none' });
      return;
    }
    if (buyout < start) {
      wx.showToast({ title: '一口价不能低于起拍价', icon: 'none' });
      return;
    }
    this.setData({ loading: true, message: '' });
    api.createAuctionListing({
      order_ids: draft.order_ids,
      start_price_jpy: start,
      buyout_price_jpy: buyout,
      note: this.data.note
    }).then((res) => {
      wx.removeStorageSync(AUCTION_DRAFT_KEY);
      wx.showToast({ title: '已发布到大厅' });
      this.setData({
        draft: null,
        startPrice: '',
        buyoutPrice: '',
        note: '',
        loading: false,
        message: `已发布 ${res.count || 0} 单`
      });
      this.loadListings();
    }).catch((err) => {
      this.setData({ loading: false, message: `发布失败：${err.error || err.message || '请稍后重试'}` });
    });
  },

  clearDraft() {
    wx.removeStorageSync(AUCTION_DRAFT_KEY);
    this.setData({ draft: null, startPrice: '', buyoutPrice: '', note: '' });
  },

  goDispatch() {
    wx.reLaunch({ url: '/pages/dispatch/index' });
  },

  formatMoney(value) {
    const number = Number(value || 0);
    return `¥${number.toLocaleString()}`;
  }
});
