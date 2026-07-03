const api = require('../../utils/api');

Page({
  data: {
    office: 'all',
    offices: [
      { key: 'all', label: '全部' },
      { key: 'osaka', label: '大阪' },
      { key: 'kyoto', label: '京都' },
      { key: 'unknown', label: '未标注' }
    ],
    summary: { total: 0, working: 0, idle: 0, alerts: 0 },
    workingRows: [],
    idleRows: [],
    alertRows: [],
    allVehicles: [],
    assignments: []
  },

  onShow() {
    api.setActiveTab('/package_company_lite/pages/attendance-vehicles/index');
    this.refreshTabBar();
    this.loadData();
  },

  refreshTabBar() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) this.getTabBar().refresh();
  },

  switchOffice(e) {
    const office = e.currentTarget.dataset.office || 'all';
    this.setData({ office });
    this.rebuildRows(office, this.data.allVehicles, this.data.assignments);
  },

  loadData() {
    Promise.all([
      api.vehicles().catch(() => ({ vehicles: [] })),
      api.assignments().catch(() => ({ assignments: [] }))
    ]).then((results) => {
      const vehicles = ((results[0] && results[0].vehicles) || []).map((item) => this.decorateVehicle(item));
      const assignments = (results[1] && results[1].assignments) || [];
      this.setData({ allVehicles: vehicles, assignments });
      this.rebuildRows(this.data.office, vehicles, assignments);
    }).catch(() => {
      wx.showToast({ title: '车辆出勤读取失败', icon: 'none' });
    });
  },

  rebuildRows(office, vehicles, assignments) {
    const today = this.formatDate(new Date());
    const todayAssignments = (assignments || []).filter((item) => {
      return String(item.order_date || item.start_date || '').slice(0, 10) === today;
    });
    const byVehicle = {};
    todayAssignments.forEach((item) => {
      const id = Number(item.vehicle_id || 0);
      const plate = String(item.plate_number || '').trim();
      const key = id || plate;
      if (!key) return;
      if (!byVehicle[key]) byVehicle[key] = [];
      byVehicle[key].push(item);
    });

    const filtered = (vehicles || [])
      .filter((item) => this.officeMatches(office, item.officeKey))
      .filter((item) => !item.retired);
    const workingRows = [];
    const idleRows = [];
    const alertRows = [];

    filtered.forEach((vehicle) => {
      const tasks = byVehicle[vehicle.id] || byVehicle[vehicle.plate] || [];
      const row = {
        ...vehicle,
        taskLine: tasks.length ? this.taskLine(tasks[0], tasks.length) : '今天暂无任务',
        statusText: tasks.length ? `${tasks.length} 单` : vehicle.statusText
      };
      if (tasks.length) workingRows.push(row);
      else idleRows.push(row);

      const alerts = this.vehicleAlerts(vehicle);
      if (alerts.length) {
        alertRows.push({
          ...vehicle,
          alertText: alerts.join(' / '),
          alertLevel: alerts.some((text) => text.indexOf('已过期') >= 0 || text.indexOf('维修') >= 0) ? '注意' : '临近'
        });
      }
    });

    this.setData({
      workingRows,
      idleRows,
      alertRows,
      summary: {
        total: filtered.length,
        working: workingRows.length,
        idle: idleRows.length,
        alerts: alertRows.length
      }
    });
  },

  decorateVehicle(vehicle) {
    const officeRaw = vehicle.office || vehicle.branch || vehicle.sales_office || vehicle.depot || vehicle.base || '';
    const officeKey = this.officeKey(officeRaw);
    const statusRaw = vehicle.status || vehicle.vehicle_status || '';
    const inspectionDate = vehicle.latest_inspection_date || vehicle.last_inspection_date || vehicle.inspection_date || '';
    const shakenDate = vehicle.latest_vehicle_inspection_date || vehicle.last_vehicle_inspection_date || vehicle.vehicle_inspection_date || vehicle.shaken_due_date || '';
    const retired = this.isRetiredStatus(statusRaw);
    return {
      id: Number(vehicle.id || 0),
      plate: vehicle.plate_number || vehicle.vehicle_code || '-',
      model: vehicle.vehicle_type || vehicle.car_model || vehicle.model || '-',
      officeRaw,
      officeKey,
      officeLabel: this.officeLabel(officeKey),
      statusRaw,
      statusText: retired ? '减车' : this.isMaintenanceStatus(statusRaw) ? '维修' : '空闲',
      retired,
      maintenance: this.isMaintenanceStatus(statusRaw),
      inspectionDate,
      shakenDate
    };
  },

  taskLine(task, count) {
    const route = `${task.pickup_location || '-'} -> ${task.dropoff_location || '-'}`;
    const time = task.start_time || '--:--';
    const driver = task.driver_name || '未定司机';
    return `${time} | ${route} | ${driver}${count > 1 ? ` | 共 ${count} 单` : ''}`;
  },

  vehicleAlerts(vehicle) {
    const alerts = [];
    if (vehicle.maintenance) alerts.push('车辆维修状态');
    const inspectionAge = this.daysSince(vehicle.inspectionDate);
    if (inspectionAge !== null && inspectionAge > 90) alerts.push(`点检已超过${inspectionAge}天`);
    const shakenDays = this.daysUntil(vehicle.shakenDate);
    if (shakenDays !== null && shakenDays <= 30) {
      alerts.push(shakenDays < 0 ? `车检已过期${Math.abs(shakenDays)}天` : `车检${shakenDays}天后到期`);
    }
    return alerts;
  },

  isMaintenanceStatus(status) {
    const text = String(status || '').toLowerCase();
    return text.indexOf('maintenance') >= 0 || text.indexOf('repair') >= 0 || text.indexOf('维修') >= 0;
  },

  isRetiredStatus(status) {
    const text = String(status || '').toLowerCase();
    return text.indexOf('retired') >= 0
      || text.indexOf('deleted') >= 0
      || text.indexOf('removed') >= 0
      || text.indexOf('减车') >= 0
      || text.indexOf('出售') >= 0
      || text.indexOf('报废') >= 0;
  },

  officeMatches(filter, officeKey) {
    return filter === 'all' || filter === officeKey;
  },

  officeKey(value) {
    const text = String(value || '').toLowerCase();
    if (text.indexOf('大阪') >= 0 || text.indexOf('osaka') >= 0) return 'osaka';
    if (text.indexOf('京都') >= 0 || text.indexOf('kyoto') >= 0) return 'kyoto';
    return 'unknown';
  },

  officeLabel(key) {
    return { osaka: '大阪营业所', kyoto: '京都营业所', unknown: '未标注营业所' }[key] || '未标注营业所';
  },

  daysUntil(dateText) {
    if (!dateText) return null;
    const target = new Date(`${dateText}T00:00:00`);
    if (Number.isNaN(target.getTime())) return null;
    const now = new Date();
    const base = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return Math.ceil((target.getTime() - base.getTime()) / 86400000);
  },

  daysSince(dateText) {
    if (!dateText) return null;
    const target = new Date(`${dateText}T00:00:00`);
    if (Number.isNaN(target.getTime())) return null;
    const now = new Date();
    const base = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return Math.floor((base.getTime() - target.getTime()) / 86400000);
  },

  formatDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  }
});
