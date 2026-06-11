const api = require('../../utils/api');

const LOCATION_CACHE_KEY = 'dispatch_driver_location_cache';
const LOCATION_CACHE_TTL_MS = 24 * 60 * 60 * 1000;

Page({
  data: {
    role: '',
    isDriver: false,
    driverId: 0,
    locations: [],
    assignments: [],
    currentAssignment: null,
    upcomingAssignments: [],
    nextAction: null,
    filteredDrivers: [],
    filteredOrders: [],
    markers: [],
    latitude: 34.6937,
    longitude: 135.5023,
    scale: 11,
    query: '',
    mode: 'drivers',
    selected: null,
    helpTip: null
  },

  onShow() {
    api.setActiveTab('/package_dispatch/pages/map/index');
    this.refreshTabBar();
    const session = api.getSession();
    const role = api.getRole(session);
    const isDriver = role === 'driver';
    this.setData({
      role,
      isDriver,
      driverId: Number(session && session.user && session.user.profile_id || 0)
    });
    this.loadData();
  },

  refreshTabBar() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().refresh();
    }
  },

  showHelp(e) {
    const type = e.currentTarget.dataset.type;
    const contentMap = {
      driver: '司机端地图只围绕本人今日任务，查看当前订单和后续任务，并按节点上报出发、到达等状态。',
      fleet: '车队地图显示在线司机、执行订单和目标位置。可以按司机、车辆、订单或路线搜索。'
    };
    this.setData({
      helpTip: {
        title: type === 'driver' ? '当前任务' : '车队地图',
        content: contentMap[type] || '暂无说明'
      }
    });
  },

  hideHelp() {
    this.setData({ helpTip: null });
  },

  noop() {},

  loadData() {
    if (this.data.isDriver) {
      this.loadDriverMap();
      return;
    }
    Promise.all([
      api.fleetLocations().catch(() => ({ locations: [] })),
      api.assignments().catch(() => ({ assignments: [] }))
    ]).then(([locationRes, assignmentRes]) => {
      const locations = this.decorateLocations(locationRes.locations || []);
      const assignments = this.decorateAssignments(assignmentRes.assignments || []);
      const markers = this.buildMarkers(locations);
      const first = markers[0];
      this.setData({
        locations,
        assignments,
        markers,
        latitude: first ? first.latitude : this.data.latitude,
        longitude: first ? first.longitude : this.data.longitude,
        selected: null
      });
      this.applyFilter();
    });
  },

  loadDriverMap() {
    const driverId = this.data.driverId;
    if (!driverId) return;
    Promise.all([
      api.driverAssignments(driverId).catch(() => ({ assignments: [] })),
      api.driverWorkbench(driverId).catch(() => ({}))
    ]).then(([assignmentRes, workbench]) => {
      const today = this.today();
      const assignments = (assignmentRes.assignments || [])
        .filter((item) => this.isOnDate(item, today))
        .map((item) => this.decorateDriverAssignment(item))
        .sort((a, b) => String(a.start_time || '').localeCompare(String(b.start_time || '')));
      const current = this.pickCurrentAssignment(assignments, workbench.current_assignment);
      const upcoming = assignments.filter((item) => !current || Number(item.assignment_id || item.id) !== Number(current.assignment_id || current.id));
      this.setData({
        assignments,
        currentAssignment: current,
        upcomingAssignments: upcoming,
        nextAction: this.nextDriverAction(current),
        filteredOrders: assignments,
        selected: null
      });
    });
  },

  decorateLocations(locations) {
    return locations.map((item, index) => ({
      ...item,
      markerId: 1000 + index,
      hasLocation: Boolean(item.latitude && item.longitude),
      locationText: item.latitude && item.longitude
        ? `${Number(item.latitude).toFixed(4)}, ${Number(item.longitude).toFixed(4)}`
        : '暂无定位',
      searchText: [
        item.driver_name,
        item.driver_code,
        item.plate_number,
        item.vehicle_plate,
        item.location_text,
        item.reported_at,
        item.created_at
      ].filter(Boolean).join(' ').toLowerCase()
    }));
  },

  decorateAssignments(assignments) {
    return assignments.map((item) => ({
      ...item,
      routeText: `${item.pickup_location || '-'} → ${item.dropoff_location || '-'}`,
      timeText: `${item.order_date || '-'} ${item.start_time || '--:--'}-${item.end_time || '--:--'}`,
      searchText: [
        item.oid,
        item.order_id,
        item.driver_name,
        item.plate_number,
        item.pickup_location,
        item.dropoff_location,
        item.execution_status,
        item.status
      ].filter(Boolean).join(' ').toLowerCase()
    }));
  },

  decorateDriverAssignment(item) {
    const status = item.execution_status || item.status || 'assigned';
    return {
      ...item,
      rawStatus: status,
      routeText: `${item.pickup_location || '-'} -> ${item.dropoff_location || '-'}`,
      timeText: `${item.order_date || '-'} ${item.start_time || '--:--'}`,
      statusLabel: this.driverStatusLabel(status)
    };
  },

  buildMarkers(locations) {
    return locations
      .filter((item) => item.hasLocation)
      .map((item) => ({
        id: item.markerId,
        latitude: Number(item.latitude),
        longitude: Number(item.longitude),
        title: item.driver_name || item.plate_number || '司机位置',
        width: 28,
        height: 28,
        callout: {
          content: `${item.driver_name || '司机'}\n${item.plate_number || ''}`,
          color: '#0f172a',
          fontSize: 12,
          borderRadius: 8,
          bgColor: '#ffffff',
          padding: 8,
          display: 'BYCLICK'
        }
      }));
  },

  onSearchInput(e) {
    this.setData({ query: e.detail.value || '' });
    this.applyFilter();
  },

  setMode(e) {
    this.setData({ mode: e.currentTarget.dataset.mode || 'drivers' });
    this.applyFilter();
  },

  applyFilter() {
    const query = String(this.data.query || '').trim().toLowerCase();
    const filteredDrivers = query
      ? this.data.locations.filter((item) => item.searchText.includes(query))
      : this.data.locations;
    const filteredOrders = query
      ? this.data.assignments.filter((item) => item.searchText.includes(query))
      : this.data.assignments;
    this.setData({ filteredDrivers, filteredOrders });
  },

  focusDriver(e) {
    const driverId = Number(e.currentTarget.dataset.driverId);
    const driver = this.data.locations.find((item) => Number(item.driver_id) === driverId);
    if (!driver) return;
    const nextData = {
      selected: {
        title: driver.driver_name || '司机',
        meta: `${driver.plate_number || '未绑定车辆'} · ${driver.locationText}`,
        sub: driver.reported_at || driver.created_at || ''
      }
    };
    if (driver.hasLocation) {
      nextData.latitude = Number(driver.latitude);
      nextData.longitude = Number(driver.longitude);
      nextData.scale = 14;
    }
    this.setData(nextData);
  },

  focusOrder(e) {
    const assignmentId = Number(e.currentTarget.dataset.assignmentId);
    const order = this.data.assignments.find((item) => Number(item.assignment_id || item.id) === assignmentId);
    if (!order) return;
    const driver = this.data.locations.find((item) => Number(item.driver_id) === Number(order.driver_id));
    const nextData = {
      selected: {
        title: `${order.oid || order.order_id} · ${order.driver_name || '未派司机'}`,
        meta: order.timeText,
        sub: order.routeText
      }
    };
    if (driver && driver.hasLocation) {
      nextData.latitude = Number(driver.latitude);
      nextData.longitude = Number(driver.longitude);
      nextData.scale = 14;
    }
    this.setData(nextData);
  },

  onMarkerTap(e) {
    const markerId = Number(e.markerId);
    const driver = this.data.locations.find((item) => Number(item.markerId) === markerId);
    if (!driver) return;
    this.setData({
      selected: {
        title: driver.driver_name || '司机',
        meta: `${driver.plate_number || '未绑定车辆'} · ${driver.locationText}`,
        sub: driver.reported_at || driver.created_at || ''
      }
    });
  },

  submitCurrentReport() {
    const item = this.data.currentAssignment;
    const action = this.data.nextAction;
    if (!item || !action || action.disabled) return;
    this.setData({ selected: { title: '正在提交', meta: action.label, sub: '' } });
    this.withLocation((location) => {
      api.submitDriverReport({
        driver_id: this.data.driverId,
        assignment_id: item.assignment_id || item.id,
        report_type: action.reportType,
        latitude: location.latitude,
        longitude: location.longitude,
        location_text: action.label,
        note: JSON.stringify({ action: action.reportType })
      }).then((result) => {
        if (result && result.success === false) {
          wx.showToast({ title: this.reportError(result), icon: 'none' });
          return;
        }
        wx.showToast({ title: action.success, icon: 'success' });
        this.loadDriverMap();
      }).catch(() => {
        wx.showToast({ title: '提交失败', icon: 'none' });
      });
    });
  },

  withLocation(done) {
    const cached = this.getCachedLocation();
    if (cached) {
      done(cached);
      return;
    }
    wx.getLocation({
      type: 'gcj02',
      success: (res) => {
        const location = { latitude: res.latitude, longitude: res.longitude };
        this.setCachedLocation(location);
        done(location);
      },
      fail: () => done({ latitude: null, longitude: null })
    });
  },

  getCachedLocation() {
    try {
      const cached = wx.getStorageSync(LOCATION_CACHE_KEY);
      if (!cached || !cached.latitude || !cached.longitude) return null;
      const createdAt = Number(cached.created_at || 0);
      if (createdAt && Date.now() - createdAt > LOCATION_CACHE_TTL_MS) return null;
      return { latitude: cached.latitude, longitude: cached.longitude };
    } catch (err) {
      return null;
    }
  },

  setCachedLocation(location) {
    try {
      wx.setStorageSync(LOCATION_CACHE_KEY, { ...location, created_at: Date.now() });
    } catch (err) {
      console.warn('[driver location cache failed]', err);
    }
  },

  pickCurrentAssignment(assignments, workbenchCurrent) {
    const id = Number(workbenchCurrent && (workbenchCurrent.assignment_id || workbenchCurrent.id) || 0);
    if (id) {
      const matched = assignments.find((item) => Number(item.assignment_id || item.id) === id);
      if (matched) return matched;
    }
    return assignments.find((item) => ['departed', 'arrived', 'in_service'].indexOf(item.rawStatus) >= 0)
      || assignments.find((item) => ['assigned', 'confirmed'].indexOf(item.rawStatus) >= 0)
      || null;
  },

  nextDriverAction(item) {
    if (!item) return { label: '今日暂无当前任务', disabled: true };
    const status = item.rawStatus || 'assigned';
    if (status === 'assigned') return { label: '确认接单', reportType: 'confirm_order', success: '已确认' };
    if (status === 'confirmed') return { label: '出发上车点', reportType: 'depart_yard', success: '已出发' };
    if (status === 'departed') return { label: '到达上车点', reportType: 'arrive_pickup', success: '已到达上车点' };
    if (status === 'arrived') return { label: '开始服务', reportType: 'start_service', success: '已开始服务' };
    if (status === 'in_service') return { label: '到达终点', reportType: 'complete_order', success: '已到达终点' };
    return { label: '任务已完成', disabled: true };
  },

  driverStatusLabel(status) {
    if (['departed', 'arrived', 'in_service'].indexOf(status) >= 0) return '正在执行';
    if (status === 'completed' || status === 'returned') return '已完成';
    return '待执行';
  },

  reportError(result) {
    return {
      execution_status_duplicate_or_regression_not_allowed: '状态已更新，请刷新',
      execution_status_skip_not_allowed: '请按流程顺序操作',
      assignment_not_found_for_driver: '未找到司机任务',
      location_out_of_range: '当前位置不在节点附近'
    }[result && result.error] || '提交失败';
  },

  isOnDate(item, date) {
    const start = item.order_date || date;
    const end = item.end_date || start;
    return start <= date && end >= date;
  },

  today() {
    const date = new Date();
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  }
});

