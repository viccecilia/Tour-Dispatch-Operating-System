const api = require('../../utils/api');

Page({
  data: {
    loading: false,
    loadError: '',
    orders: [],
    filters: {
      order_date: '',
      agency_name: '',
      dispatch_status: '',
      settlement_status: '',
      keyword: ''
    },
    dispatchOptions: [
      { label: '全部派车状态', value: '' },
      { label: '未分配', value: 'unassigned' },
      { label: '已派车', value: 'assigned' },
      { label: '已完成', value: 'completed' }
    ],
    settlementOptions: [
      { label: '全部结算状态', value: '' },
      { label: '待结算', value: 'pending' },
      { label: '已结算', value: 'settled' }
    ],
    dispatchIndex: 0,
    settlementIndex: 0
  },

  onShow() {
    this.loadOrders();
  },

  loadOrders() {
    this.setData({ loading: true, loadError: '' });
    api.listOrders(this.data.filters)
      .then((res) => {
        if (res.error) {
          throw new Error(res.error);
        }
        this.setData({ orders: res.orders || [], loading: false });
      })
      .catch(() => {
        this.setData({ loading: false, loadError: '订单加载失败' });
      });
  },

  onFilterInput(event) {
    const key = event.currentTarget.dataset.key;
    this.setData({ [`filters.${key}`]: event.detail.value });
  },

  onDateChange(event) {
    this.setData({ 'filters.order_date': event.detail.value });
    this.loadOrders();
  },

  onDispatchChange(event) {
    const index = Number(event.detail.value);
    this.setData({
      dispatchIndex: index,
      'filters.dispatch_status': this.data.dispatchOptions[index].value
    });
    this.loadOrders();
  },

  onSettlementChange(event) {
    const index = Number(event.detail.value);
    this.setData({
      settlementIndex: index,
      'filters.settlement_status': this.data.settlementOptions[index].value
    });
    this.loadOrders();
  },

  onSearch() {
    this.loadOrders();
  },

  onAdd() {
    wx.navigateTo({ url: '/pages/orders/form' });
  },

  onEdit(event) {
    wx.navigateTo({ url: `/pages/orders/form?id=${event.currentTarget.dataset.id}` });
  },

  onDelete(event) {
    const id = event.currentTarget.dataset.id;
    wx.showModal({
      title: '删除订单',
      content: '确认删除该订单？',
      success: (res) => {
        if (!res.confirm) {
          return;
        }
        api.deleteOrder(id).then((result) => {
          if (result.error) {
            wx.showToast({ title: '删除失败', icon: 'none' });
            return;
          }
          wx.showToast({ title: '已删除' });
          this.loadOrders();
        });
      }
    });
  }
});
