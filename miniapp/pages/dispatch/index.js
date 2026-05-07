const api = require('../../utils/api');

Page({
  data: {
    loading: false,
    orders: [],
    assignments: [],
    drivers: [],
    vehicles: [],
    selectedOrderIds: [],
    driverIndex: -1,
    vehicleIndex: -1,
    conflicts: [],
    routeLinks: [],
    message: ''
  },

  onShow() {
    this.loadAll();
  },

  loadAll() {
    this.setData({ loading: true, message: '', conflicts: [] });
    Promise.all([
      api.unassignedOrders(),
      api.dispatchDrivers(),
      api.dispatchVehicles(),
      api.dispatchAssignments()
    ]).then(([ordersRes, driversRes, vehiclesRes, assignmentsRes]) => {
      this.setData({
        orders: ordersRes.orders || [],
        drivers: driversRes.drivers || [],
        vehicles: vehiclesRes.vehicles || [],
        assignments: assignmentsRes.assignments || [],
        loading: false
      });
    }).catch(() => {
      this.setData({ loading: false, message: '派车数据加载失败' });
    });
  },

  onToggleOrder(event) {
    const id = Number(event.currentTarget.dataset.id);
    const selected = this.data.selectedOrderIds.slice();
    const index = selected.indexOf(id);
    if (index >= 0) {
      selected.splice(index, 1);
    } else {
      selected.push(id);
    }
    this.setData({ selectedOrderIds: selected });
    this.loadRouteSuggestion(selected);
  },

  isSelected(id) {
    return this.data.selectedOrderIds.indexOf(id) >= 0;
  },

  onDriverChange(event) {
    this.setData({ driverIndex: Number(event.detail.value) });
  },

  onVehicleChange(event) {
    this.setData({ vehicleIndex: Number(event.detail.value) });
  },

  loadRouteSuggestion(orderIds) {
    if (!orderIds.length) {
      this.setData({ routeLinks: [] });
      return;
    }
    api.routeSuggestion(orderIds).then((res) => {
      this.setData({ routeLinks: res.links || [] });
    });
  },

  onAssign() {
    if (!this.data.selectedOrderIds.length) {
      wx.showToast({ title: '请选择订单', icon: 'none' });
      return;
    }
    if (this.data.driverIndex < 0 || this.data.vehicleIndex < 0) {
      wx.showToast({ title: '请选择司机和车辆', icon: 'none' });
      return;
    }
    const driver = this.data.drivers[this.data.driverIndex];
    const vehicle = this.data.vehicles[this.data.vehicleIndex];
    api.assignOrders({
      order_ids: this.data.selectedOrderIds,
      driver_id: driver.id,
      vehicle_id: vehicle.id
    }).then((res) => {
      if (!res.success) {
        this.setData({ conflicts: res.conflicts || [], message: '存在时间冲突，未执行派车' });
        return;
      }
      wx.showToast({ title: '派车成功' });
      this.setData({ selectedOrderIds: [], conflicts: [], routeLinks: [], message: '派车成功' });
      this.loadAll();
    });
  },

  onCancel(event) {
    const assignmentId = event.currentTarget.dataset.id;
    api.cancelAssignment({ assignment_id: assignmentId }).then((res) => {
      if (!res.success) {
        wx.showToast({ title: '取消失败', icon: 'none' });
        return;
      }
      wx.showToast({ title: '已取消' });
      this.loadAll();
    });
  }
});
