const api = require('../../utils/api');

Page({
  data: {
    query: '',
    mode: 'orders',
    orders: [],
    drivers: [],
    vehicles: [],
    results: []
  },

  onShow() {
    this.loadData();
  },

  loadData() {
    Promise.all([
      api.assignments().catch(() => ({ assignments: [] })),
      api.unassignedOrders().catch(() => ({ orders: [] })),
      api.drivers().catch(() => ({ drivers: [] })),
      api.vehicles().catch(() => ({ vehicles: [] }))
    ]).then(([assignments, unassigned, drivers, vehicles]) => {
      const assignedOrders = (assignments.assignments || []).map((item) => ({ ...item, is_assigned: true }));
      const pendingOrders = (unassigned.orders || []).map((item) => ({ ...item, is_assigned: false }));
      this.setData({
        orders: assignedOrders.concat(pendingOrders),
        drivers: drivers.drivers || [],
        vehicles: vehicles.vehicles || []
      });
      this.applySearch();
    });
  },

  onQuery(e) {
    this.setData({ query: e.detail.value || '' });
    this.applySearch();
  },

  setMode(e) {
    this.setData({ mode: e.currentTarget.dataset.mode || 'orders' });
    this.applySearch();
  },

  applySearch() {
    const query = String(this.data.query || '').trim().toLowerCase();
    const source = this.data.mode === 'drivers'
      ? this.data.drivers
      : this.data.mode === 'vehicles'
        ? this.data.vehicles
        : this.data.orders;
    const filtered = query
      ? source.filter((item) => this.searchText(item).includes(query))
      : source.slice(0, 30);
    this.setData({ results: filtered.slice(0, 50).map((item) => this.toResult(item)) });
  },

  searchText(item) {
    return Object.keys(item)
      .map((key) => item[key])
      .filter((value) => value !== null && value !== undefined)
      .join(' ')
      .toLowerCase();
  },

  toResult(item) {
    if (this.data.mode === 'drivers') {
      return {
        key: `driver-${item.id}`,
        title: item.name || '司机',
        meta: `${item.phone || '-'} · ${item.driver_code || '-'} · ${item.status || '-'}`,
        badge: item.status || '-'
      };
    }
    if (this.data.mode === 'vehicles') {
      return {
        key: `vehicle-${item.id}`,
        title: item.plate_number || item.plate_no || '车辆',
        meta: `${item.vehicle_type || '-'} · ${item.seat_count || item.seats || '-'}座`,
        badge: item.status || '-'
      };
    }
    return {
      key: `order-${item.assignment_id || item.id}`,
      title: `${item.oid || item.order_id || item.id} · ${item.pickup_location || '-'} -> ${item.dropoff_location || '-'}`,
      meta: `${item.order_date || '-'} ${item.start_time || ''} · ${item.driver_name || '未派司机'} · ${item.plate_number || ''}`,
      badge: item.is_assigned ? (item.execution_status || item.status || '已派') : '未派'
    };
  }
});
