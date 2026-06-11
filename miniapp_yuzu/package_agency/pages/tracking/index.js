const api = require('../../utils/api');

function isGuide(session) {
  const role = session && session.account ? String(session.account.role || '').toLowerCase() : '';
  return role.indexOf('guide') >= 0 || role.indexOf('导游') >= 0;
}

function ownGuideOrders(session, orders) {
  if (!isGuide(session)) return orders || [];
  const account = session.account || {};
  const phone = String(account.phone || '').replace(/\D/g, '');
  const name = String(account.display_name || '').trim().toLowerCase();
  return (orders || []).filter((order) => {
    const guidePhone = String(order.guide_phone || order.guide_whatsapp || '').replace(/\D/g, '');
    const guideName = String(order.guide_name || '').trim().toLowerCase();
    if (phone && guidePhone && guidePhone.indexOf(phone.slice(-8)) >= 0) return true;
    if (name && guideName && (guideName.indexOf(name) >= 0 || name.indexOf(guideName) >= 0)) return true;
    return false;
  });
}

Page({
  data: {
    loading: false,
    keyword: '',
    isGuide: false,
    orders: [],
    filteredOrders: [],
    selectedOrder: null,
    markers: [],
    mapLatitude: 34.6937,
    mapLongitude: 135.5023,
    message: ''
  },

  onShow() {
    const session = api.getSession();
    if (!session) {
      wx.redirectTo({ url: '/package_agency/pages/home/index' });
      return;
    }
    const guideMode = isGuide(session);
    if (guideMode) wx.hideTabBar(); else wx.showTabBar();
    const tabBar = typeof this.getTabBar === 'function' && this.getTabBar();
    if (tabBar) tabBar.setData({ selected: 3 });
    this.setData({ isGuide: guideMode });
    wx.setNavigationBarTitle({
      title: session.agency && session.agency.name ? session.agency.name : '订单跟踪'
    });
    this.loadOrders();
  },

  loadOrders() {
    const session = api.getSession();
    this.setData({ loading: true, message: '' });
    api.orders()
      .then((orders) => {
        const scoped = ownGuideOrders(session, orders);
        const decorated = (scoped || []).map((item) => this.decorateOrder(item));
        const markers = decorated
          .filter((item) => item.driver_latitude && item.driver_longitude)
          .map((item) => ({
            id: item.id,
            latitude: Number(item.driver_latitude),
            longitude: Number(item.driver_longitude),
            title: item.driver_name || item.oid || String(item.id),
            width: 28,
            height: 28
          }));
        const first = markers[0];
        this.setData({
          orders: decorated,
          filteredOrders: this.applyKeyword(decorated, this.data.keyword),
          selectedOrder: decorated[0] || null,
          markers,
          mapLatitude: first ? first.latitude : this.data.mapLatitude,
          mapLongitude: first ? first.longitude : this.data.mapLongitude,
          loading: false
        });
      })
      .catch((err) => {
        this.setData({ loading: false, message: `订单跟踪加载失败：${err.error || err.message || '请确认接口在线'}` });
      });
  },

  onKeywordInput(e) {
    const keyword = e.detail.value;
    this.setData({
      keyword,
      filteredOrders: this.applyKeyword(this.data.orders, keyword)
    });
  },

  focusOrder(e) {
    const id = e.currentTarget.dataset.id;
    const selectedOrder = this.data.orders.find((item) => String(item.id) === String(id));
    if (!selectedOrder) return;
    this.setData({
      selectedOrder,
      mapLatitude: selectedOrder.driver_latitude ? Number(selectedOrder.driver_latitude) : this.data.mapLatitude,
      mapLongitude: selectedOrder.driver_longitude ? Number(selectedOrder.driver_longitude) : this.data.mapLongitude
    });
  },

  reportNode(e) {
    const label = e.currentTarget.dataset.label;
    wx.showToast({ title: `${label}已记录`, icon: 'none' });
  },

  decorateOrder(order) {
    const dispatchStatus = order.dispatch_status || '';
    const settlementStatus = order.settlement_status || order.agency_settlement_status || 'pending';
    return {
      ...order,
      routeText: `${order.pickup_location || '-'} → ${order.dropoff_location || '-'}`,
      timeText: `${order.order_date || '-'} ${order.start_time || ''}${order.end_time ? `-${order.end_time}` : ''}`,
      guestText: `${order.guest_name || '-'} / ${order.guest_contact || '-'}`,
      statusText: this.statusLabel(order.auction_status || dispatchStatus || order.execution_status || 'unassigned'),
      settlementText: this.settlementLabel(settlementStatus),
      driverText: order.driver_name || order.assigned_driver_code || '未显示司机',
      vehicleText: order.plate_number || order.plate_no || order.assigned_vehicle_type || '未显示车辆',
      locationText: order.driver_location_text || (order.driver_latitude && order.driver_longitude ? `${order.driver_latitude}, ${order.driver_longitude}` : '暂无位置')
    };
  },

  applyKeyword(rows, keyword) {
    const text = String(keyword || '').trim().toLowerCase();
    if (!text) return rows;
    return rows.filter((item) => [
      item.oid,
      item.order_date,
      item.pickup_location,
      item.dropoff_location,
      item.guest_name,
      item.guest_contact,
      item.driver_name,
      item.plate_number,
      item.dispatch_status,
      item.settlement_status
    ].filter(Boolean).join(' ').toLowerCase().indexOf(text) >= 0);
  },

  statusLabel(status) {
    const labels = {
      unassigned: '未派车',
      auction_listed: '发布中',
      listed: '发布中',
      bidding: '竞拍中',
      auction_claimed: '已接单',
      claimed: '已接单',
      assigned: '已派车',
      completed: '已完成',
      returned: '已回库',
      expired: '流拍',
      cancelled: '已取消'
    };
    return labels[status] || status || '-';
  },

  settlementLabel(status) {
    const labels = {
      pending: '待结算',
      payment_requested: '车公司已请款',
      receipt_uploaded: '已上传回执',
      paid: '车公司确认收款',
      settled: '已结算'
    };
    return labels[status] || status || '-';
  }
});

