const api = require('../../utils/api');

const FILTERS = [
  { label: '进行中', value: 'active' },
  { label: '全部订单', value: 'all' },
  { label: '发布中', value: 'listed' },
  { label: '已接单', value: 'claimed' },
  { label: '流拍', value: 'expired' },
  { label: '待结算', value: 'settlement' },
  { label: '已完成', value: 'completed' }
];

const LISTING_TYPES = [
  { label: '全部类型', value: '' },
  { label: '接机', value: '接机' },
  { label: '送机', value: '送机' },
  { label: '包车', value: '包车' }
];

Page({
  data: {
    hallTab: 'market',
    filterNames: FILTERS.map((item) => item.label),
    filterIndex: 0,
    orders: [],
    filteredOrders: [],
    listings: [],
    filteredListings: [],
    listingTypeNames: LISTING_TYPES.map((item) => item.label),
    listingTypeIndex: 0,
    listingDate: '',
    listingKeyword: '',
    selectedOrderId: '',
    reason: '',
    timeChangeForm: {
      order_date: '',
      start_time: ''
    },
    forceCancel: false,
    loading: false,
    actionLoading: false,
    message: ''
  },

  onShow() {
    const session = api.getSession();
    if (!session) {
      wx.redirectTo({ url: '/package_agency/pages/home/index' });
      return;
    }
    const role = session.account ? String(session.account.role || '').toLowerCase() : '';
    if (role.indexOf('guide') >= 0 || role.indexOf('导游') >= 0 || role.indexOf('service') >= 0 || role.indexOf('support') >= 0 || role.indexOf('customer') >= 0 || role.indexOf('客服') >= 0) {
      wx.showToast({ title: '当前角色不开放订单大厅', icon: 'none' });
      wx.redirectTo({ url: '/package_agency/pages/home/index' });
      return;
    }
    const tabBar = typeof this.getTabBar === 'function' && this.getTabBar();
    if (tabBar) tabBar.setData({ selected: 2 });
    wx.setNavigationBarTitle({
      title: session.agency && session.agency.name ? session.agency.name : '订单大厅'
    });
    this.loadAll();
  },

  loadAll() {
    this.setData({ loading: true, message: '' });
    Promise.all([
      api.orders(),
      api.auctionListings('listed')
    ]).then(([orders, listings]) => {
      const decoratedOrders = this.sortOrders((orders || []).map((item) => this.decorateOrder(item)));
      const decoratedListings = (listings || []).map((item) => this.decorateListing(item));
      this.setData({
        orders: decoratedOrders,
        filteredOrders: this.applyFilter(decoratedOrders, FILTERS[this.data.filterIndex].value),
        listings: decoratedListings,
        filteredListings: this.applyListingFilter(decoratedListings),
        loading: false
      });
    }).catch((err) => {
      this.setData({ loading: false, message: `数据加载失败：${err.error || err.message || '请确认接口'}` });
    });
  },

  switchHallTab(e) {
    this.setData({ hallTab: e.currentTarget.dataset.tab || 'market' });
  },

  onFilterChange(e) {
    const filterIndex = Number(e.detail.value);
    this.setData({
      filterIndex,
      filteredOrders: this.applyFilter(this.data.orders, FILTERS[filterIndex].value)
    });
  },

  onListingTypeChange(e) {
    this.setData({ listingTypeIndex: Number(e.detail.value) }, () => {
      this.setData({ filteredListings: this.applyListingFilter(this.data.listings) });
    });
  },

  onListingDateChange(e) {
    this.setData({ listingDate: e.detail.value || '' }, () => {
      this.setData({ filteredListings: this.applyListingFilter(this.data.listings) });
    });
  },

  onListingKeywordInput(e) {
    this.setData({ listingKeyword: e.detail.value || '' }, () => {
      this.setData({ filteredListings: this.applyListingFilter(this.data.listings) });
    });
  },

  selectOrderCard(e) {
    const orderId = e.currentTarget.dataset.id;
    const isClosing = String(this.data.selectedOrderId) === String(orderId);
    const order = isClosing ? null : this.findOrder(orderId);
    this.setData({
      selectedOrderId: isClosing ? '' : orderId,
      reason: '',
      timeChangeForm: {
        order_date: order ? (order.order_date || '') : '',
        start_time: order ? (order.start_time || '') : ''
      },
      forceCancel: false
    });
  },

  onReasonInput(e) {
    this.setData({ reason: e.detail.value });
  },

  onForceChange(e) {
    this.setData({ forceCancel: e.detail.value });
  },

  onTimeChangeInput(e) {
    this.setData({ [`timeChangeForm.${e.currentTarget.dataset.key}`]: e.detail.value });
  },

  withdrawOrder(e) {
    const order = this.findOrder(e.currentTarget.dataset.id);
    if (!order || !order.canDirectWithdraw) {
      wx.showToast({ title: '当前订单不能直接撤回', icon: 'none' });
      return;
    }
    wx.showModal({
      title: '撤回订单',
      content: '未被车公司接单的订单可以直接从订单大厅撤回。',
      confirmText: '撤回',
      success: (res) => {
        if (!res.confirm) return;
        this.setData({ actionLoading: true, message: '' });
        api.withdrawOrderFromHall(order.id)
          .then(() => {
            wx.showToast({ title: '已撤回' });
            this.setData({ actionLoading: false, message: '订单已从订单大厅撤回。' });
            this.loadAll();
          })
          .catch((err) => {
            this.setData({ actionLoading: false, message: `撤回失败：${err.error || err.message || '需要车公司确认'}` });
          });
      }
    });
  },

  submitTimeChange(e) {
    const order = this.findOrder(e.currentTarget.dataset.id);
    const reason = String(this.data.reason || '').trim();
    const nextDate = String(this.data.timeChangeForm.order_date || '').trim();
    const nextTime = String(this.data.timeChangeForm.start_time || '').trim();
    if (!order || !order.canRequestChange) {
      wx.showToast({ title: '当前订单不能申请改时间', icon: 'none' });
      return;
    }
    if (!nextTime) {
      wx.showToast({ title: '请填写新出发时间', icon: 'none' });
      return;
    }
    if (!reason) {
      wx.showToast({ title: '请填写一句原因', icon: 'none' });
      return;
    }
    const originalDate = this.normalizeDate(order.order_date);
    const requestedDate = this.normalizeDate(nextDate || order.order_date);
    const hoursUntilStart = this.hoursUntilOrderStart(order);
    if (requestedDate !== originalDate && hoursUntilStart < 24) {
      wx.showToast({ title: '不足24小时不能改日期', icon: 'none' });
      return;
    }
    const changes = { start_time: nextTime };
    if (requestedDate !== originalDate) {
      changes.order_date = requestedDate;
    }
    this.setData({ actionLoading: true, message: '' });
    api.createChangeRequest(order.id, {
      request_type: 'modify',
      reason,
      changes
    }).then(() => {
      wx.showToast({ title: '已提交' });
      this.setData({
        actionLoading: false,
        reason: '',
        message: '时间变更申请已提交给车公司确认。'
      });
      this.loadAll();
    }).catch((err) => {
      this.setData({ actionLoading: false, message: `提交失败：${err.error || err.message || '请稍后重试'}` });
    });
  },

  submitCancelRequest(e) {
    const order = this.findOrder(e.currentTarget.dataset.id);
    const reason = String(this.data.reason || '').trim();
    if (!order || !order.canRequestChange) {
      wx.showToast({ title: '当前订单不能申请撤销', icon: 'none' });
      return;
    }
    if (!reason) {
      wx.showToast({ title: '请填写一句原因', icon: 'none' });
      return;
    }
    wx.showModal({
      title: '申请撤销',
      content: this.data.forceCancel ? '强行撤销可能产生费用，确认提交？' : '撤销申请将提交给车公司确认。',
      confirmText: '提交',
      success: (res) => {
        if (!res.confirm) return;
        this.setData({ actionLoading: true, message: '' });
        api.createChangeRequest(order.id, {
          request_type: 'cancel',
          reason,
          force: this.data.forceCancel
        }).then(() => {
          wx.showToast({ title: '已提交' });
          this.setData({ actionLoading: false, reason: '', forceCancel: false, message: '撤销申请已提交给车公司确认。' });
          this.loadAll();
        }).catch((err) => {
          this.setData({ actionLoading: false, message: `提交失败：${err.error || err.message || '请稍后重试'}` });
        });
      }
    });
  },

  uploadReceipt(e) {
    const order = this.findOrder(e.currentTarget.dataset.id);
    if (!order || !order.canUploadReceipt) {
      wx.showToast({ title: '当前订单不能上传回执', icon: 'none' });
      return;
    }
    wx.chooseMessageFile({
      count: 1,
      type: 'file',
      success: (res) => {
        const file = res.tempFiles && res.tempFiles[0];
        if (!file) return;
        this.setData({ actionLoading: true, message: '' });
        api.fileToDataUrl(file.path, file.type || 'application/octet-stream')
          .then((fileBase64) => api.uploadPaymentReceipt(order.id, {
            file_name: file.name || 'payment-receipt',
            file_base64: fileBase64
          }))
          .then(() => {
            wx.showToast({ title: '已上传' });
            this.setData({ actionLoading: false, message: '付款回执已上传，等待车公司确认收款。' });
            this.loadAll();
          })
          .catch((err) => {
            this.setData({ actionLoading: false, message: `上传失败：${err.error || err.message || '请稍后重试'}` });
          });
      }
    });
  },

  findOrder(orderId) {
    return this.data.orders.find((item) => String(item.id) === String(orderId));
  },

  normalizeDate(value) {
    return String(value || '').replace(/\//g, '-').slice(0, 10);
  },

  hoursUntilOrderStart(order) {
    const date = this.normalizeDate(order && order.order_date);
    const time = String((order && order.start_time) || '00:00').slice(0, 5);
    const target = new Date(`${date}T${time}:00`);
    if (Number.isNaN(target.getTime())) return 0;
    return (target.getTime() - Date.now()) / (1000 * 60 * 60);
  },

  decorateOrder(order) {
    const dispatchStatus = order.dispatch_status || '';
    const auctionStatus = order.auction_status || '';
    const executionStatus = order.execution_status || '';
    const settlementStatus = order.settlement_status || order.agency_settlement_status || 'pending';
    const accepted = ['auction_claimed', 'claimed', 'assigned'].indexOf(dispatchStatus) >= 0 || Boolean(order.assignment_id);
    const listed = ['auction_listed', 'bidding'].indexOf(dispatchStatus) >= 0 || ['listed', 'bidding'].indexOf(auctionStatus) >= 0;
    const completed = ['completed', 'returned'].indexOf(executionStatus) >= 0 || ['paid', 'settled'].indexOf(settlementStatus) >= 0;
    const expired = auctionStatus === 'expired' || dispatchStatus === 'auction_expired';
    const cancelled = ['auction_cancelled', 'agency_cancelled', 'cancelled'].indexOf(dispatchStatus) >= 0 || executionStatus === 'cancelled';
    return {
      ...order,
      routeText: `${order.pickup_location || '-'} -> ${order.dropoff_location || '-'}`,
      timeText: `${order.order_date || '-'} ${order.start_time || ''}`,
      statusText: this.statusLabel(auctionStatus || dispatchStatus || executionStatus || 'unassigned'),
      settlementText: this.settlementLabel(settlementStatus),
      amountText: this.formatMoney(order.payment_amount_jpy || order.price_jpy || order.price),
      accepted,
      listed,
      completed,
      expired,
      active: !completed && !cancelled,
      canDirectWithdraw: !accepted && !completed && !cancelled,
      canRequestChange: accepted && !completed && !cancelled,
      canUploadReceipt: ['payment_requested', 'receipt_uploaded'].indexOf(settlementStatus) >= 0
    };
  },

  decorateListing(item) {
    const typeText = this.publicOrderType(item.order_type);
    return {
      ...item,
      typeText,
      publicTitle: `${typeText} · ${item.order_date || '-'} ${item.start_time || ''}`,
      routeText: `${item.pickup_location || '-'} -> ${item.dropoff_location || '-'}`,
      timeText: `${item.order_date || '-'} ${item.start_time || ''}`,
      priceText: `${this.formatMoney(item.start_price_jpy)} / ${this.formatMoney(item.buyout_price_jpy)}`,
      durationText: item.auction_duration_hours ? `${item.auction_duration_hours}小时` : '-'
    };
  },

  applyFilter(rows, filterValue) {
    return this.sortOrders(rows.filter((item) => {
      if (filterValue === 'all') return true;
      if (filterValue === 'active') return item.active;
      if (filterValue === 'listed') return item.listed;
      if (filterValue === 'claimed') return item.accepted;
      if (filterValue === 'expired') return item.expired;
      if (filterValue === 'settlement') return ['pending', 'payment_requested', 'receipt_uploaded', 'unsettled'].indexOf(item.settlement_status || item.agency_settlement_status || 'pending') >= 0;
      if (filterValue === 'completed') return item.completed;
      return true;
    }));
  },

  applyListingFilter(rows) {
    const typeValue = LISTING_TYPES[this.data.listingTypeIndex].value;
    const dateValue = this.data.listingDate;
    const keyword = String(this.data.listingKeyword || '').trim().toLowerCase();
    return rows.filter((item) => {
      if (typeValue && item.typeText !== typeValue) return false;
      if (dateValue && String(item.order_date || '').slice(0, 10) !== dateValue) return false;
      if (keyword) {
        const text = [item.pickup_location, item.dropoff_location, item.start_time, item.vehicle_type, item.typeText].filter(Boolean).join(' ').toLowerCase();
        if (text.indexOf(keyword) < 0) return false;
      }
      return true;
    });
  },

  sortOrders(rows) {
    return rows.slice().sort((a, b) => {
      if (a.active !== b.active) return a.active ? -1 : 1;
      const left = `${a.order_date || ''} ${a.start_time || ''}`;
      const right = `${b.order_date || ''} ${b.start_time || ''}`;
      return left.localeCompare(right);
    });
  },

  formatMoney(value) {
    const number = Number(value || 0);
    return number ? `¥${number.toLocaleString()}` : '-';
  },

  statusLabel(status) {
    const labels = {
      unassigned: '未发布',
      auction_listed: '发布中',
      listed: '发布中',
      bidding: '竞拍中',
      auction_claimed: '已接单',
      claimed: '已接单',
      assigned: '已派车',
      expired: '流拍',
      auction_expired: '流拍',
      cancelled: '已取消',
      agency_cancelled: '已撤回',
      completed: '已完成',
      paid: '已付款',
      pending: '待确认',
      approved: '已同意',
      rejected: '已驳回'
    };
    return labels[status] || status || '-';
  },

  settlementLabel(status) {
    const labels = {
      pending: '待处理',
      payment_requested: '待付款',
      receipt_uploaded: '已传回执',
      paid: '已收款',
      settled: '已结算',
      unsettled: '未结算'
    };
    return labels[status] || status || '-';
  },

  publicOrderType(value) {
    const text = String(value || '').toLowerCase();
    if (text.indexOf('接机') >= 0 || text.indexOf('pickup') >= 0) return '接机';
    if (text.indexOf('送机') >= 0 || text.indexOf('dropoff') >= 0) return '送机';
    if (text.indexOf('airport') >= 0) return '接送机';
    return '包车';
  }
});

