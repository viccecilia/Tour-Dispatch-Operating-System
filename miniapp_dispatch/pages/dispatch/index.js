const api = require('../../utils/api');

Page({
  data: {
    orders: [],
    visibleOrders: [],
    pickupOrders: [],
    dropoffOrders: [],
    charterOrders: [],
    timeGroups: [],
    activeTimeGroup: 'all',
    drivers: [],
    vehicles: [],
    assignments: [],
    locations: [],
    selectedOrderIds: [],
    driverId: '',
    vehicleId: '',
    activeResourceTab: 'drivers',
    loading: false,
    message: '',
    conflictText: '',
    canAssign: false,
    assignButtonText: '请选择订单',
    preview: {
      orders: 0,
      route: '请选择订单',
      driver: '未选择司机',
      vehicle: '未选择车辆'
    }
  },

  onShow() {
    this.loadAll();
  },

  loadAll() {
    this.setData({ loading: true, message: '', conflictText: '' });
    Promise.all([
      api.unassignedOrders(),
      api.drivers(),
      api.vehicles(),
      api.assignments(),
      api.fleetLocations().catch(() => ({ locations: [] }))
    ])
      .then(([orders, drivers, vehicles, assignments, locations]) => {
        const activeAssignments = assignments.assignments || [];
        const decoratedOrders = this.decorateOrders(this.sortOrders(orders.orders || []));
        const timeGroups = this.buildTimeGroups(decoratedOrders);
        this.setData({
          orders: decoratedOrders,
          timeGroups,
          visibleOrders: this.filterVisibleOrders(decoratedOrders, this.data.activeTimeGroup),
          pickupOrders: decoratedOrders.filter((item) => item.dispatchKind === 'pickup'),
          dropoffOrders: decoratedOrders.filter((item) => item.dispatchKind === 'dropoff'),
          charterOrders: decoratedOrders.filter((item) => item.dispatchKind === 'charter'),
          drivers: this.decorateDrivers(drivers.drivers || [], activeAssignments, locations.locations || []),
          vehicles: this.decorateVehicles(vehicles.vehicles || [], activeAssignments),
          assignments: activeAssignments.slice(0, 16),
          locations: locations.locations || [],
          loading: false
        });
        this.updatePreview();
      })
      .catch(() => {
        this.setData({ loading: false, message: '无法加载派车数据，请检查后端服务。' });
        this.updatePreview();
      });
  },


  decorateOrders(orders) {
    return orders.slice(0, 50).map((item) => ({
      ...item,
      selected: this.data.selectedOrderIds.includes(Number(item.id)),
      dispatchKind: this.classifyAirportOrder(item),
      routeText: `${item.pickup_location || '-'} -> ${item.dropoff_location || '-'}`,
      timeText: `${item.order_date || '-'} ${item.start_time || '--:--'}-${item.end_time || '--:--'}`
    }));
  },

  classifyAirportOrder(order) {
    const type = String(order.order_type || '').toLowerCase();
    const pickup = String(order.pickup_location || '').toLowerCase();
    const dropoff = String(order.dropoff_location || '').toLowerCase();
    const allText = `${type} ${pickup} ${dropoff} ${String(order.remark || '').toLowerCase()}`;
    const airportWords = ['机场', '空港', 'kix', '関空', '关空', '关西', '成田', '羽田', '伊丹', '神户机场', '神戸空港'];
    if (type.includes('charter') || allText.includes('包车') || allText.includes('包車')) return 'charter';
    if (type.includes('airport_pickup') || type.includes('接机')) return 'pickup';
    if (type.includes('airport_dropoff') || type.includes('送机')) return 'dropoff';
    const pickupAirport = airportWords.some((word) => pickup.includes(String(word).toLowerCase()));
    const dropoffAirport = airportWords.some((word) => dropoff.includes(String(word).toLowerCase()));
    if (pickupAirport && !dropoffAirport) return 'pickup';
    if (dropoffAirport && !pickupAirport) return 'dropoff';
    if (String(order.remark || '').includes('接机')) return 'pickup';
    if (String(order.remark || '').includes('送机')) return 'dropoff';
    return 'pickup';
  },

  sortOrders(orders) {
    return orders.slice().sort((a, b) => {
      const left = `${a.order_date || ''} ${a.start_time || ''} ${a.pickup_location || ''}`;
      const right = `${b.order_date || ''} ${b.start_time || ''} ${b.pickup_location || ''}`;
      return left.localeCompare(right, 'zh-Hans-CN');
    });
  },

  buildTimeGroups(orders) {
    const groups = [
      { key: 'all', label: '全部未派车', from: 0, to: 24, count: 0, summary: '所有时间段' },
      { key: 'morning', label: '06:00 - 10:00', from: 6, to: 10, count: 0, summary: '早班接送优先' },
      { key: 'midday', label: '10:00 - 14:00', from: 10, to: 14, count: 0, summary: '午间包车/送迎' },
      { key: 'afternoon', label: '14:00 - 18:00', from: 14, to: 18, count: 0, summary: '下午订单' },
      { key: 'evening', label: '18:00 以后', from: 18, to: 24, count: 0, summary: '晚间和跨日订单' }
    ];
    orders.forEach((order) => {
      groups[0].count += 1;
      const hour = this.startHour(order);
      const group = groups.find((item) => item.key !== 'all' && hour >= item.from && hour < item.to);
      if (group) group.count += 1;
    });
    return groups;
  },

  startHour(order) {
    const hour = Number(String(order.start_time || '').slice(0, 2));
    return Number.isFinite(hour) ? hour : 0;
  },

  filterVisibleOrders(orders, groupKey) {
    if (groupKey === 'all') return orders.slice(0, 50);
    const group = this.data.timeGroups.find((item) => item.key === groupKey);
    if (!group) return orders.slice(0, 50);
    return orders.filter((order) => {
      const hour = this.startHour(order);
      return hour >= group.from && hour < group.to;
    }).slice(0, 50);
  },

  selectTimeGroup(e) {
    const key = e.currentTarget.dataset.key || 'all';
    this.setData({
      activeTimeGroup: key,
      visibleOrders: this.filterVisibleOrders(this.data.orders, key)
    });
  },

  decorateDrivers(drivers, assignments, locations) {
    const selectedWindows = this.getSelectedOrderWindows();
    return drivers.map((driver) => {
      const current = assignments.find((item) => Number(item.driver_id) === Number(driver.id));
      const location = locations.find((item) => Number(item.driver_id) === Number(driver.id));
      const conflict = this.hasResourceTimeConflict(assignments, 'driver_id', driver.id, selectedWindows);
      return {
        ...driver,
        selected: String(this.data.driverId) === String(driver.id),
        isBusy: Boolean(current),
        isOnline: Boolean(location),
        hasSelectedTimeConflict: conflict,
        availabilityText: selectedWindows.length ? (conflict ? '冲突' : '可派') : (location ? '在线' : '未上线'),
        statusClass: selectedWindows.length ? (conflict ? 'busy' : 'online') : (location ? 'online' : ''),
        onlineText: location ? '在线' : '未上线',
        currentTask: current ? `${current.pickup_location || '-'} -> ${current.dropoff_location || '-'}` : '空闲',
        nextFreeTime: current ? (current.end_time || '待确认') : '现在可用',
        distanceText: location && location.distance_text ? location.distance_text : '距离待估'
      };
    })
      .sort((a, b) => {
        if (a.hasSelectedTimeConflict !== b.hasSelectedTimeConflict) return a.hasSelectedTimeConflict ? 1 : -1;
        if (a.isBusy !== b.isBusy) return a.isBusy ? 1 : -1;
        if (a.isOnline !== b.isOnline) return a.isOnline ? -1 : 1;
        return String(a.name || '').localeCompare(String(b.name || ''), 'zh-Hans-CN');
      })
      .slice(0, 16);
  },

  decorateVehicles(vehicles, assignments) {
    const selectedWindows = this.getSelectedOrderWindows();
    return vehicles.map((vehicle) => {
      const current = assignments.find((item) => Number(item.vehicle_id) === Number(vehicle.id));
      const maintenanceRisk = vehicle.maintenance_status && vehicle.maintenance_status !== 'available';
      const conflict = this.hasResourceTimeConflict(assignments, 'vehicle_id', vehicle.id, selectedWindows);
      return {
        ...vehicle,
        selected: String(this.data.vehicleId) === String(vehicle.id),
        isBusy: Boolean(current),
        hasMaintenanceRisk: Boolean(maintenanceRisk),
        hasSelectedTimeConflict: conflict,
        shortPlate: String(vehicle.plate_number || '').slice(-4) || vehicle.plate_number,
        availabilityText: selectedWindows.length ? (conflict ? '冲突' : '可派') : (current ? '占用中' : '空闲'),
        statusClass: selectedWindows.length ? (conflict ? 'busy' : 'online') : (current ? 'busy' : 'online'),
        availableText: current ? '占用中' : '空闲',
        riskText: maintenanceRisk ? '维护风险' : '状态正常',
        etcText: vehicle.etc_status || 'ETC待确认',
        seatText: `${vehicle.seat_count || '-'}座`
      };
    })
      .sort((a, b) => {
        if (a.hasSelectedTimeConflict !== b.hasSelectedTimeConflict) return a.hasSelectedTimeConflict ? 1 : -1;
        if (a.isBusy !== b.isBusy) return a.isBusy ? 1 : -1;
        if (a.hasMaintenanceRisk !== b.hasMaintenanceRisk) return a.hasMaintenanceRisk ? 1 : -1;
        return String(a.plate_number || '').localeCompare(String(b.plate_number || ''), 'ja-JP');
      })
      .slice(0, 16);
  },

  getSelectedOrderWindows() {
    return this.data.orders
      .filter((item) => this.data.selectedOrderIds.includes(Number(item.id)))
      .map((item) => this.toWindow(item))
      .filter(Boolean);
  },

  hasResourceTimeConflict(assignments, key, resourceId, selectedWindows) {
    if (!selectedWindows.length) return false;
    return assignments
      .filter((item) => Number(item[key]) === Number(resourceId))
      .some((item) => {
        const activeWindow = this.toWindow(item);
        return activeWindow && selectedWindows.some((selected) => this.windowsOverlap(selected, activeWindow));
      });
  },

  toWindow(item) {
    const start = this.toTimeValue(item.order_date, item.start_time);
    let end = this.toTimeValue(item.end_date || item.order_date, item.end_time);
    if (!start || !end) return null;
    if (end <= start) end += 24 * 60 * 60 * 1000;
    return { start, end };
  },

  toTimeValue(dateText, timeText) {
    if (!dateText || !timeText || !String(timeText).includes(':')) return null;
    const date = String(dateText).split('-').map((part) => Number(part));
    const time = String(timeText).split(':').map((part) => Number(part));
    if (date.length < 3 || time.length < 2 || date.some(Number.isNaN) || time.some(Number.isNaN)) return null;
    return new Date(date[0], date[1] - 1, date[2], time[0], time[1], 0, 0).getTime();
  },

  windowsOverlap(first, second) {
    return first.start < second.end && second.start < first.end;
  },

  setResourceTab(e) {
    this.setData({ activeResourceTab: e.currentTarget.dataset.tab || 'drivers' });
  },

  toggleOrder(e) {
    const id = Number(e.currentTarget.dataset.id);
    const selected = this.data.selectedOrderIds.slice();
    const idx = selected.indexOf(id);
    if (idx >= 0) selected.splice(idx, 1);
    else selected.push(id);
    this.setData({ selectedOrderIds: selected });
    this.refreshDecorations();
  },

  selectDriver(e) {
    this.setData({ driverId: String(e.currentTarget.dataset.id) });
    this.refreshDecorations();
  },

  selectVehicle(e) {
    this.setData({ vehicleId: String(e.currentTarget.dataset.id) });
    this.refreshDecorations();
  },

  refreshDecorations() {
    const decoratedOrders = this.decorateOrders(this.data.orders);
    this.setData({
      orders: decoratedOrders,
      visibleOrders: this.filterVisibleOrders(decoratedOrders, this.data.activeTimeGroup),
      pickupOrders: decoratedOrders.filter((item) => item.dispatchKind === 'pickup'),
      dropoffOrders: decoratedOrders.filter((item) => item.dispatchKind === 'dropoff'),
      charterOrders: decoratedOrders.filter((item) => item.dispatchKind === 'charter'),
      drivers: this.decorateDrivers(this.data.drivers, this.data.assignments, this.data.locations),
      vehicles: this.decorateVehicles(this.data.vehicles, this.data.assignments)
    });
    this.updatePreview();
  },

  smartRouteSort() {
    const selectedSet = new Set(this.data.selectedOrderIds.map(Number));
    const selected = this.data.orders.filter((item) => selectedSet.has(Number(item.id)));
    if (!selected.length) {
      this.setData({ orders: this.decorateOrders(this.sortOrders(this.data.orders)), message: '已按时间和起点排序订单池。' });
      this.updatePreview();
      return;
    }
    const sortedSelected = this.sortOrders(selected);
    const rest = this.data.orders.filter((item) => !selectedSet.has(Number(item.id)));
    this.setData({
      orders: this.decorateOrders(sortedSelected.concat(this.sortOrders(rest))),
      message: `已为 ${sortedSelected.length} 单按时间和起点接龙。`
    });
    this.updatePreview();
  },

  updatePreview() {
    const selectedOrders = this.data.orders.filter((item) => this.data.selectedOrderIds.includes(Number(item.id)));
    const driver = this.data.drivers.find((item) => String(item.id) === String(this.data.driverId));
    const vehicle = this.data.vehicles.find((item) => String(item.id) === String(this.data.vehicleId));
    let assignButtonText = '请选择订单';
    if (selectedOrders.length && !driver) assignButtonText = '请选择司机';
    else if (selectedOrders.length && driver && !vehicle) assignButtonText = '请选择车辆';
    else if (selectedOrders.length && driver && vehicle) assignButtonText = '确认派车';

    this.setData({
      canAssign: Boolean(selectedOrders.length && driver && vehicle),
      assignButtonText,
      preview: {
        orders: selectedOrders.length,
        route: selectedOrders.length ? selectedOrders.map((item) => item.oid || item.id).join(' / ') : '请选择订单',
        driver: driver ? driver.name : '未选择司机',
        vehicle: vehicle ? vehicle.plate_number : '未选择车辆'
      }
    });
  },

  assign() {
    if (!this.data.canAssign) {
      wx.showToast({ title: this.data.assignButtonText, icon: 'none' });
      return;
    }
    this.setData({ loading: true, conflictText: '', message: '' });
    api.assignOrders({
      order_ids: this.data.selectedOrderIds,
      driver_id: Number(this.data.driverId),
      vehicle_id: Number(this.data.vehicleId)
    })
      .then((res) => {
        if (res && res.success === false) {
          this.setData({
            loading: false,
            conflictText: this.formatConflicts(res.conflicts || [])
          });
          this.updatePreview();
          return;
        }
        wx.showToast({ title: '已派发给司机' });
        this.setData({
          selectedOrderIds: [],
          driverId: '',
          vehicleId: '',
          activeResourceTab: 'drivers',
          message: '司机端会收到新订单通知。'
        });
        this.loadAll();
      })
      .catch(() => {
        this.setData({ loading: false, message: '派车失败，请检查网络或后端服务。' });
        this.updatePreview();
      });
  },

  formatConflicts(conflicts) {
    if (!conflicts.length) return '存在冲突，请重新选择司机或车辆。';
    return conflicts.map((item) => {
      if (item.type === 'driver_time_overlap') return `司机时间冲突：订单 ${item.order_id}`;
      if (item.type === 'vehicle_time_overlap') return `车辆时间冲突：订单 ${item.order_id}`;
      if (item.type === 'order_already_assigned') return `订单已派车：${item.order_id}`;
      return `${item.type || '冲突'}：${item.order_id || '-'}`;
    }).join('；');
  }
});
