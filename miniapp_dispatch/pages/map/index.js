const api = require('../../utils/api');

Page({
  data: {
    locations: [],
    assignments: [],
    filteredDrivers: [],
    filteredOrders: [],
    markers: [],
    latitude: 34.6937,
    longitude: 135.5023,
    scale: 11,
    query: '',
    mode: 'drivers',
    selected: null
  },

  onShow() {
    this.loadData();
  },

  loadData() {
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
  }
});
