const api = require('../../utils/api');

const AUCTION_DRAFT_KEY = 'auction_publish_draft';
const ACTIVE_LISTING_STATUSES = ['listed', 'bidding'];

Page({
  data: {
    draft: null,
    listings: [],
    startPrice: '',
    buyoutPrice: '',
    durationHours: 1,
    durationOptions: [1, 2, 4],
    note: '',
    loading: false,
    message: '',
    helpTip: null
  },

  onShow() {
    api.syncEnvironmentBaseUrl();
    api.setActiveTab('/pages/auction/index');
    this.refreshTabBar();
    if (!api.canAccess('auction')) {
      wx.showToast({ title: '当前账号无订单大厅权限', icon: 'none' });
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

  showHelp(e) {
    const type = e.currentTarget.dataset.type;
    const contentMap = {
      hero: '订单大厅用于把本公司暂时无法执行的订单开放给其他车公司。其他公司可以竞拍降价，也可以一口价直接接单。',
      publish: '从派车页选择订单后会来到这里。起拍价是订单放出的起始价格，一口价是最低成交价。选择拍卖时间后即可发布。',
      list: '这里只显示可竞拍或可一口价接单的大厅订单。每次竞拍会把当前价降低 20，达到一口价后不再继续降低。'
    };
    this.setData({
      helpTip: {
        title: type === 'publish' ? '发布到大厅' : (type === 'list' ? '大厅订单' : '订单大厅'),
        content: contentMap[type] || '暂无说明'
      }
    });
  },

  hideHelp() {
    this.setData({ helpTip: null });
  },

  noop() {},

  loadDraft() {
    const draft = wx.getStorageSync(AUCTION_DRAFT_KEY);
    if (!draft || !draft.order_ids || !draft.order_ids.length) {
      this.setData({ draft: null });
      return;
    }
    const total = (draft.orders || []).reduce((sum, item) => sum + Number(item.price || item.price_jpy || 0), 0);
    this.setData({
      draft,
      startPrice: total ? String(Math.round(total)) : '',
      buyoutPrice: total ? String(Math.round(total * 0.8)) : '',
      durationHours: 1
    });
  },

  loadListings() {
    this.setData({ loading: true });
    const session = api.getSession() || {};
    const currentTenantId = Number(
      (session.user && session.user.tenant_id)
      || (session.dispatcher && session.dispatcher.tenant_id)
      || 0
    );
    api.auctionListings()
      .then((res) => {
        const listings = (res.listings || [])
          .filter((item) => ACTIVE_LISTING_STATUSES.indexOf(item.status) >= 0)
          .map((item) => this.decorateListing(item, currentTenantId));
        this.setData({ listings, loading: false });
      })
      .catch(() => {
        this.setData({ loading: false, message: '订单大厅加载失败，请确认后端服务在线。' });
      });
  },

  onInput(e) {
    this.setData({ [e.currentTarget.dataset.key]: e.detail.value });
  },

  chooseDuration(e) {
    this.setData({ durationHours: Number(e.currentTarget.dataset.hours || 1) });
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
    if (buyout > start) {
      wx.showToast({ title: '一口价不能高于起拍价', icon: 'none' });
      return;
    }
    this.setData({ loading: true, message: '' });
    api.createAuctionListing({
      order_ids: draft.order_ids,
      order_oids: draft.order_oids || [],
      start_price_jpy: start,
      buyout_price_jpy: buyout,
      auction_duration_hours: this.data.durationHours,
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
        message: `已发布 ${res.count || 0} 单到大厅。`
      });
      this.loadListings();
    }).catch((err) => {
      const code = err && (err.error || err.message);
      if (['order_not_found', 'order_not_unassigned', 'order_already_in_auction'].includes(code)) {
        wx.removeStorageSync(AUCTION_DRAFT_KEY);
        this.setData({
          draft: null,
          startPrice: '',
          buyoutPrice: '',
          note: '',
          loading: false,
          message: `发布失败：${this.humanAuctionError(err)}已清空待发布订单，请回到派车页重新选择。`
        });
        return;
      }
      this.setData({ loading: false, message: `发布失败：${this.humanAuctionError(err)}` });
    });
  },

  clearDraft() {
    wx.removeStorageSync(AUCTION_DRAFT_KEY);
    this.setData({ draft: null, startPrice: '', buyoutPrice: '', note: '', message: '' });
  },

  placeBid(e) {
    const id = e.currentTarget.dataset.id;
    const current = Number(e.currentTarget.dataset.current || 0);
    const buyout = Number(e.currentTarget.dataset.buyout || 0);
    if (!id) return;
    if (current <= buyout) {
      wx.showToast({ title: '已到一口价', icon: 'none' });
      return;
    }
    const next = Math.max(buyout, current - 20);
    wx.showModal({
      title: '确认竞拍',
      content: `当前价 ${this.formatMoney(current)}，竞拍价 ${this.formatMoney(next)}。确认出价？`,
      confirmText: '确认',
      cancelText: '取消',
      success: (res) => {
        if (!res.confirm) return;
        this.setData({ loading: true, message: '' });
        api.bidAuctionListing(id, { step_jpy: 20 })
          .then(() => {
            wx.showToast({ title: '竞拍成功' });
            this.loadListings();
          })
          .catch((err) => {
            this.setData({ message: `竞拍失败：${this.humanAuctionError(err)}` });
          })
          .finally(() => this.setData({ loading: false }));
      }
    });
  },

  claimListing(e) {
    const id = e.currentTarget.dataset.id;
    const price = Number(e.currentTarget.dataset.price || 0);
    if (!id) return;
    wx.showModal({
      title: '一口价接单',
      content: `确认按 ${this.formatMoney(price)} 接下这张订单？`,
      confirmText: '确认接单',
      success: (res) => {
        if (!res.confirm) return;
        this.setData({ loading: true, message: '' });
        api.claimAuctionListing(id, { claim_price_jpy: price })
          .then(() => {
            wx.showToast({ title: '已一口价接单' });
            this.loadListings();
          })
          .catch((err) => {
            this.setData({ message: `接单失败：${this.humanAuctionError(err)}` });
            this.loadListings();
          })
          .finally(() => this.setData({ loading: false }));
      }
    });
  },

  humanAuctionError(err) {
    const code = err && (err.error || err.message);
    const map = {
      listing_not_claimable: '订单已过期或已被接单，请刷新大厅。',
      listing_not_biddable: '订单已过期或已被接单，请刷新大厅。',
      cannot_claim_own_listing: '不能接本公司发布的订单。',
      cannot_bid_own_listing: '不能竞拍本公司发布的订单。',
      already_leading_bid: '本公司当前领先，不需要重复竞拍。',
      already_at_buyout_price: '当前价已经到一口价，不能继续竞拍。',
      claim_price_less_than_buyout_price: '接单价不能低于一口价。',
      claim_price_greater_than_start_price: '接单价不能高于起拍价。',
      missing_order_ids: '没有选中订单，请回到派车页重新选择。',
      order_not_found: '订单不存在或不属于当前公司，请刷新派车页后重试。',
      order_not_unassigned: '订单当前状态不能发布到大厅，请确认未派车或已撤回。',
      order_already_in_auction: '订单已经在大厅中，请刷新大厅查看。',
      invalid_order_route: '订单起点或终点无效，请回到派车页修改后再发布。',
      missing_start_price: '请填写起拍价。',
      missing_buyout_price: '请填写一口价。',
      buyout_price_greater_than_start_price: '一口价不能高于起拍价。',
      invalid_auction_duration_hours: '拍卖时间只能选择 1、2 或 4 小时。'
    };
    return map[code] || code || '请稍后重试';
  },

  goDispatch() {
    wx.reLaunch({ url: '/pages/dispatch/index' });
  },

  formatMoney(value) {
    const number = Number(value || 0);
    return `￥${number.toLocaleString()}`;
  },

  cleanLocation(value) {
    const text = String(value || '').trim();
    if (!text || /^[-?？\s]+$/.test(text) || text.includes('????')) return '地点待确认';
    return text;
  },

  decorateListing(item, currentTenantId) {
    const current = Number(item.current_bid_jpy || item.start_price_jpy || 0);
    const buyout = Number(item.buyout_price_jpy || 0);
    const isOwnListing = Boolean(currentTenantId && Number(item.seller_tenant_id || item.owner_tenant_id || 0) === currentTenantId);
    const isLeadingBid = Boolean(currentTenantId && Number(item.current_bidder_tenant_id || 0) === currentTenantId);
    const isAtBuyout = Boolean(buyout && current <= buyout);
    const canBid = !isOwnListing && !isLeadingBid && !isAtBuyout;
    return {
      ...item,
      isOwnListing,
      isLeadingBid,
      isAtBuyout,
      canBid,
      bidActionText: isLeadingBid ? `领先 ${this.formatMoney(current)}` : (isAtBuyout ? '已到一口价' : '竞拍'),
      routeText: `${this.cleanLocation(item.pickup_location)} -> ${this.cleanLocation(item.dropoff_location)}`,
      timeText: `${item.order_date || '-'} ${item.start_time || ''}`,
      startPriceText: this.formatMoney(item.start_price_jpy),
      buyoutPriceText: this.formatMoney(item.buyout_price_jpy),
      currentPriceText: this.formatMoney(current),
      durationText: `${item.auction_duration_hours || 1}小时`
    };
  }
});
