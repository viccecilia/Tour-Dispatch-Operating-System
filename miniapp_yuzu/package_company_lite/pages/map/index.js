const api = require('../../utils/api');

const LOCATION_CACHE_KEY = 'dispatch_driver_location_cache';
const LOCATION_DENIED_CACHE_KEY = 'dispatch_driver_location_denied_cache';
const LOCATION_CACHE_TTL_MS = 24 * 60 * 60 * 1000;
const LOCATION_DENIED_TTL_MS = 60 * 60 * 1000;
const DRIVER_LOCATION_REFRESH_MS = 10000;
const FLEET_LOCATION_REFRESH_MS = 15000;

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
    includePoints: [],
    circles: [],
    latitude: 34.6937,
    longitude: 135.5023,
    scale: 11,
    query: '',
    mode: 'drivers',
    selected: null,
    helpTip: null
  },
  _locationTimer: null,
  _fleetTimer: null,
  _locationRefreshing: false,
  _fleetRefreshing: false,
  _mapContext: null,

  onShow() {
    api.setActiveTab('/package_company_lite/pages/map/index');
    this.refreshTabBar();
    const session = api.getSession();
    if (!this.hasValidSession(session)) {
      this.stopRealtimeRefresh();
      this.setData({
        locations: [],
        assignments: [],
        filteredDrivers: [],
        filteredOrders: [],
        markers: [],
        circles: [],
        selected: null
      });
      wx.redirectTo({ url: '/pages/login/index?port=dispatch' });
      return;
    }
    const role = api.getRole(session);
    const isDriver = role === 'driver';
    this.setData({
      role,
      isDriver,
      driverId: Number(session && session.user && session.user.profile_id || 0)
    });
    this.ensureMapContext(isDriver);
    this.loadData();
    this.startRealtimeRefresh();
  },

  onHide() {
    this.stopRealtimeRefresh();
  },

  onUnload() {
    this.stopRealtimeRefresh();
  },

  onReady() {
    this.ensureMapContext();
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

  hasValidSession(session) {
    return Boolean(session && session.token);
  },

  ensureMapContext(isDriver) {
    const driverMode = typeof isDriver === 'boolean' ? isDriver : this.data.isDriver;
    const mapId = driverMode ? 'dispatchDriverMap' : 'dispatchFleetMap';
    this._mapContext = wx.createMapContext(mapId, this);
  },

  loadData() {
    if (!this.hasValidSession(api.getSession())) return;
    if (this.data.isDriver) {
      this.loadDriverMap({ recenter: true });
      return;
    }
    Promise.all([
      api.fleetLocations().catch(() => ({ locations: [] })),
      api.assignments().catch(() => ({ assignments: [] }))
    ]).then((results) => {
      const locationRes = results && results[0] || { locations: [] };
      const assignmentRes = results && results[1] || { assignments: [] };
      const locations = this.decorateLocations(locationRes.locations || []);
      const assignments = this.decorateAssignments(assignmentRes.assignments || []);
      const markers = this.buildFleetMarkers(locations, null);
      const first = markers[0];
      this.setData({
        locations,
        assignments,
        markers,
        circles: [],
        latitude: first ? first.latitude : this.data.latitude,
        longitude: first ? first.longitude : this.data.longitude,
        selected: null
      });
      this.syncViewport(markers, first ? {
        latitude: first.latitude,
        longitude: first.longitude,
        scale: 11
      } : null);
      this.applyFilter();
    });
  },

  refreshFleetLocations() {
    if (!this.hasValidSession(api.getSession())) {
      this.stopRealtimeRefresh();
      return;
    }
    if (this.data.isDriver || this._fleetRefreshing) return;
    this._fleetRefreshing = true;
    Promise.all([
      api.fleetLocations().catch(() => ({ locations: [] })),
      api.assignments().catch(() => ({ assignments: [] }))
    ]).then((results) => {
      const locationRes = results && results[0] || { locations: [] };
      const assignmentRes = results && results[1] || { assignments: [] };
      const locations = this.decorateLocations(locationRes.locations || []);
      const assignments = this.decorateAssignments(assignmentRes.assignments || []);
      const selected = this.refreshSelectedLocation(locations, assignments);
      const markers = this.buildFleetMarkers(locations, selected && selected.assignment ? selected.assignment : null);
      const nextData = {
        locations,
        assignments,
        markers,
        selected
      };
      if (selected && selected.latitude != null && selected.longitude != null) {
        nextData.latitude = selected.latitude;
        nextData.longitude = selected.longitude;
        nextData.scale = 14;
      }
      this.setData(nextData);
      this.applyFilter();
    }).finally(() => {
      this._fleetRefreshing = false;
    });
  },

  loadDriverMap(options) {
    const recenter = !options || options.recenter !== false;
    if (!this.hasValidSession(api.getSession())) return;
    const driverId = this.data.driverId;
    if (!driverId) return;
    Promise.all([
      api.driverAssignments(driverId).catch(() => ({ assignments: [] })),
      api.driverWorkbench(driverId).catch(() => ({}))
    ]).then((results) => {
      const assignmentRes = results && results[0] || { assignments: [] };
      const workbench = results && results[1] || {};
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
      this.refreshDriverLocation(recenter);
    });
  },

  manualRefresh() {
    if (this.data.isDriver) {
      this.loadDriverMap({ recenter: false });
      return;
    }
    this.refreshFleetLocations();
  },

  decorateLocations(locations) {
    return locations.map((item, index) => ({
      ...item,
      markerId: 1000 + index,
      hasLocation: this.isValidCoordinate(item.latitude, item.longitude),
      locationText: this.isValidCoordinate(item.latitude, item.longitude)
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

  buildFleetMarkers(locations, assignment) {
    return this.buildMarkers(locations).concat(this.buildAssignmentMarkers(assignment, 5000));
  },

  ensureDriverLocationMarker() {
    const cached = this.getCachedLocation();
    if (cached) {
      this.applyDriverLocationMarker(cached);
      return;
    }
    if (this.getDeniedLocationCache()) return;
    wx.getLocation({
      type: 'gcj02',
      success: (res) => {
        const location = { latitude: res.latitude, longitude: res.longitude };
        this.setCachedLocation(location);
        this.applyDriverLocationMarker(location);
      },
      fail: () => {
        this.setDeniedLocationCache();
      }
    });
  },

  refreshDriverLocation(force) {
    if (!this.hasValidSession(api.getSession())) {
      this.stopRealtimeRefresh();
      return;
    }
    if (!this.data.isDriver || !this.data.driverId || this._locationRefreshing) return;
    this._locationRefreshing = true;
    this.getFreshLocation((location) => {
      this._locationRefreshing = false;
      if (!location || location.latitude == null || location.longitude == null) {
        if (!force) return;
        this.ensureDriverLocationMarker();
        return;
      }
      this.setCachedLocation(location);
      this.applyDriverLocationMarker(location, { recenter: !!force });
      api.submitDriverLocation({
        driver_id: this.data.driverId,
        assignment_id: this.data.currentAssignment && (this.data.currentAssignment.assignment_id || this.data.currentAssignment.id),
        order_id: this.data.currentAssignment && this.data.currentAssignment.order_id,
        latitude: location.latitude,
        longitude: location.longitude,
        location_text: '实时位置'
      }).catch((err) => {
        console.warn('[driver realtime location upload failed]', err);
      });
    });
  },

  applyDriverLocationMarker(location, options) {
    const recenter = !options || options.recenter !== false;
    if (!location || location.latitude == null || location.longitude == null) return;
    const latitude = Number(location.latitude);
    const longitude = Number(location.longitude);
    if (!this.isValidCoordinate(latitude, longitude)) return;
    const assignmentMarkers = this.buildDriverAssignmentMarkers(this.data.currentAssignment);
    const markers = [{
      id: 1,
      latitude,
      longitude,
      title: '我的位置',
      width: 28,
      height: 28,
      callout: {
        content: '我的位置',
        color: '#0f172a',
        fontSize: 12,
        borderRadius: 8,
        bgColor: '#ffffff',
        padding: 8,
        display: 'ALWAYS'
      }
    }].concat(assignmentMarkers);
    this.setData({
      latitude,
      longitude,
      scale: 14,
      markers,
      circles: [{
        latitude,
        longitude,
        radius: 80,
        color: '#14b8a655',
        fillColor: '#14b8a61f',
        strokeWidth: 1
      }]
    });
    if (recenter) {
      this.syncViewport(markers, { latitude, longitude, scale: 14 });
    }
  },

  buildDriverAssignmentMarkers(assignment) {
    if (!assignment) return [];
    const markers = [];
    const pickupLat = Number(assignment.pickup_latitude);
    const pickupLng = Number(assignment.pickup_longitude);
    const dropoffLat = Number(assignment.dropoff_latitude);
    const dropoffLng = Number(assignment.dropoff_longitude);
    if (this.isValidCoordinate(pickupLat, pickupLng)) {
      markers.push({
        id: 21,
        latitude: pickupLat,
        longitude: pickupLng,
        title: '起点',
        width: 26,
        height: 26,
        callout: {
          content: `起点\n${assignment.pickup_location || '-'}`,
          color: '#075985',
          fontSize: 11,
          borderRadius: 8,
          bgColor: '#ecfeff',
          padding: 8,
          display: 'BYCLICK'
        }
      });
    }
    if (this.isValidCoordinate(dropoffLat, dropoffLng)) {
      markers.push({
        id: 22,
        latitude: dropoffLat,
        longitude: dropoffLng,
        title: '终点',
        width: 26,
        height: 26,
        callout: {
          content: `终点\n${assignment.dropoff_location || '-'}`,
          color: '#9a3412',
          fontSize: 11,
          borderRadius: 8,
          bgColor: '#fff7ed',
          padding: 8,
          display: 'BYCLICK'
        }
      });
    }
    return markers;
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
    const assignment = this.data.assignments.find((item) => Number(item.driver_id || 0) === driverId) || null;
    const nextData = {
      selected: {
        driverId,
        title: driver.driver_name || '司机',
        meta: `${driver.plate_number || '未绑定车辆'} · ${driver.locationText}`,
        sub: driver.reported_at || driver.created_at || '',
        latitude: driver.hasLocation ? Number(driver.latitude) : null,
        longitude: driver.hasLocation ? Number(driver.longitude) : null,
        assignment
      }
    };
    if (driver.hasLocation) {
      nextData.latitude = Number(driver.latitude);
      nextData.longitude = Number(driver.longitude);
      nextData.scale = 14;
    }
    nextData.markers = this.buildFleetMarkers(this.data.locations, assignment);
    this.setData(nextData);
    this.syncViewport(nextData.markers, driver.hasLocation ? {
      latitude: Number(driver.latitude),
      longitude: Number(driver.longitude),
      scale: 14
    } : null);
  },

  focusOrder(e) {
    const assignmentId = Number(e.currentTarget.dataset.assignmentId);
    const order = this.data.assignments.find((item) => Number(item.assignment_id || item.id) === assignmentId);
    if (!order) return;
    const driver = this.data.locations.find((item) => Number(item.driver_id) === Number(order.driver_id));
    const nextData = {
      selected: {
        assignmentId,
        title: `${order.oid || order.order_id} · ${order.driver_name || '未派司机'}`,
        meta: order.timeText,
        sub: order.routeText,
        latitude: driver && driver.hasLocation ? Number(driver.latitude) : null,
        longitude: driver && driver.hasLocation ? Number(driver.longitude) : null,
        assignment: order
      }
    };
    if (driver && driver.hasLocation) {
      nextData.latitude = Number(driver.latitude);
      nextData.longitude = Number(driver.longitude);
      nextData.scale = 14;
    }
    nextData.markers = this.buildFleetMarkers(this.data.locations, order);
    this.setData(nextData);
    this.syncViewport(nextData.markers, driver && driver.hasLocation ? {
      latitude: Number(driver.latitude),
      longitude: Number(driver.longitude),
      scale: 14
    } : null);
  },

  onMarkerTap(e) {
    const markerId = Number(e.markerId);
    const driver = this.data.locations.find((item) => Number(item.markerId) === markerId);
    if (!driver) return;
    const assignment = this.data.assignments.find((item) => Number(item.driver_id || 0) === Number(driver.driver_id || 0)) || null;
    this.setData({
      selected: {
        driverId: driver.driver_id,
        title: driver.driver_name || '司机',
        meta: `${driver.plate_number || '未绑定车辆'} · ${driver.locationText}`,
        sub: driver.reported_at || driver.created_at || '',
        latitude: driver.hasLocation ? Number(driver.latitude) : null,
        longitude: driver.hasLocation ? Number(driver.longitude) : null,
        assignment
      },
      markers: this.buildFleetMarkers(this.data.locations, assignment)
    });
    this.syncViewport(this.buildFleetMarkers(this.data.locations, assignment), driver.hasLocation ? {
      latitude: Number(driver.latitude),
      longitude: Number(driver.longitude),
      scale: 14
    } : null);
  },

  buildAssignmentMarkers(assignment, baseId = 20) {
    if (!assignment) return [];
    const markers = [];
    const pickupLat = Number(assignment.pickup_latitude);
    const pickupLng = Number(assignment.pickup_longitude);
    const dropoffLat = Number(assignment.dropoff_latitude);
    const dropoffLng = Number(assignment.dropoff_longitude);
    if (this.isValidCoordinate(pickupLat, pickupLng)) {
      markers.push({
        id: baseId + 1,
        latitude: pickupLat,
        longitude: pickupLng,
        title: '起点',
        width: 24,
        height: 24,
        callout: {
          content: `起点\n${assignment.pickup_location || '-'}`,
          color: '#075985',
          fontSize: 11,
          borderRadius: 8,
          bgColor: '#ecfeff',
          padding: 8,
          display: 'BYCLICK'
        }
      });
    }
    if (this.isValidCoordinate(dropoffLat, dropoffLng)) {
      markers.push({
        id: baseId + 2,
        latitude: dropoffLat,
        longitude: dropoffLng,
        title: '终点',
        width: 24,
        height: 24,
        callout: {
          content: `终点\n${assignment.dropoff_location || '-'}`,
          color: '#9a3412',
          fontSize: 11,
          borderRadius: 8,
          bgColor: '#fff7ed',
          padding: 8,
          display: 'BYCLICK'
        }
      });
    }
    return markers;
  },

  toIncludePoints(markers) {
    return (markers || []).map((item) => ({
      latitude: Number(item.latitude),
      longitude: Number(item.longitude)
    })).filter((item) => this.isValidCoordinate(item.latitude, item.longitude));
  },

  isValidCoordinate(latitude, longitude) {
    const lat = Number(latitude);
    const lng = Number(longitude);
    return !Number.isNaN(lat)
      && !Number.isNaN(lng)
      && lat >= -90
      && lat <= 90
      && lng >= -180
      && lng <= 180;
  },

  syncViewport(markers, fallback) {
    const points = this.toIncludePoints(markers);
    if (this._mapContext && points.length >= 2) {
      this._mapContext.includePoints({
        points,
        padding: [48, 48, 48, 48]
      });
      return;
    }
    if (fallback && fallback.latitude != null && fallback.longitude != null) {
      const nextData = {
        latitude: Number(fallback.latitude),
        longitude: Number(fallback.longitude)
      };
      if (fallback.scale != null) nextData.scale = fallback.scale;
      this.setData(nextData);
    }
  },

  moveToCurrentLocation() {
    this.ensureMapContext();
    if (this._mapContext && typeof this._mapContext.moveToLocation === 'function') {
      this._mapContext.moveToLocation();
      return;
    }
    this.getFreshLocation((location) => {
      if (!location || location.latitude == null || location.longitude == null) {
        wx.showToast({ title: '未获取到当前位置', icon: 'none' });
        return;
      }
      this.setData({
        latitude: Number(location.latitude),
        longitude: Number(location.longitude),
        scale: 16
      });
    });
  },

  navigateToCurrentDropoff() {
    const item = this.data.currentAssignment;
    if (!item) {
      wx.showToast({ title: '当前没有任务', icon: 'none' });
      return;
    }
    this.openLocationPoint(item.dropoff_latitude, item.dropoff_longitude, item.dropoff_location || '终点');
  },

  openLocationPoint(latitude, longitude, name) {
    const lat = Number(latitude);
    const lng = Number(longitude);
    if (!this.isValidCoordinate(lat, lng)) {
      wx.showToast({ title: '终点暂未定位', icon: 'none' });
      return;
    }
    wx.openLocation({
      latitude: lat,
      longitude: lng,
      name: name || '终点',
      address: name || '终点',
      scale: 18
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
    if (this.getDeniedLocationCache()) {
      done({ latitude: null, longitude: null });
      return;
    }
    this.getFreshLocation(done);
  },

  getFreshLocation(done) {
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

  startRealtimeRefresh() {
    this.stopRealtimeRefresh();
    if (this.data.isDriver) {
      this.refreshDriverLocation(true);
      this._locationTimer = setInterval(() => this.refreshDriverLocation(false), DRIVER_LOCATION_REFRESH_MS);
      return;
    }
    this.refreshFleetLocations();
    this._fleetTimer = setInterval(() => this.refreshFleetLocations(), FLEET_LOCATION_REFRESH_MS);
  },

  stopRealtimeRefresh() {
    if (this._locationTimer) {
      clearInterval(this._locationTimer);
      this._locationTimer = null;
    }
    if (this._fleetTimer) {
      clearInterval(this._fleetTimer);
      this._fleetTimer = null;
    }
    this._locationRefreshing = false;
    this._fleetRefreshing = false;
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

  getDeniedLocationCache() {
    try {
      const cached = wx.getStorageSync(LOCATION_DENIED_CACHE_KEY);
      const createdAt = Number(cached && cached.created_at || 0);
      return Boolean(createdAt && Date.now() - createdAt <= LOCATION_DENIED_TTL_MS);
    } catch (err) {
      return false;
    }
  },

  setDeniedLocationCache() {
    try {
      wx.setStorageSync(LOCATION_DENIED_CACHE_KEY, { created_at: Date.now() });
    } catch (err) {
      console.warn('[driver location denied cache failed]', err);
    }
  },

  refreshSelectedLocation(locations, assignments) {
    const selected = this.data.selected;
    if (!selected) return null;
    if (selected.driverId) {
      const driver = locations.find((item) => Number(item.driver_id) === Number(selected.driverId));
      if (!driver) return selected;
      return {
        ...selected,
        meta: `${driver.plate_number || '未绑定车辆'} · ${driver.locationText}`,
        sub: driver.reported_at || driver.created_at || '',
        latitude: driver.hasLocation ? Number(driver.latitude) : null,
        longitude: driver.hasLocation ? Number(driver.longitude) : null,
        assignment: assignments.find((item) => Number(item.driver_id || 0) === Number(selected.driverId)) || null
      };
    }
    if (selected.assignmentId) {
      const order = assignments.find((item) => Number(item.assignment_id || item.id) === Number(selected.assignmentId));
      if (!order) return selected;
      const driver = locations.find((item) => Number(item.driver_id) === Number(order.driver_id));
      return {
        ...selected,
        meta: order.timeText,
        sub: order.routeText,
        latitude: driver && driver.hasLocation ? Number(driver.latitude) : null,
        longitude: driver && driver.hasLocation ? Number(driver.longitude) : null,
        assignment: order
      };
    }
    return selected;
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

