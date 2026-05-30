const api = require('../../utils/api');

Page({
  data: {
    session: null,
    section: 'drivers',
    loading: false,
    search: '',
    summary: {
      driverTotal: 0,
      healthDue: 0,
      licenseDue: 0,
      vehicleTotal: 0,
      vehicleNormal: 0,
      vehicleRepair: 0,
      vehicleRetired: 0,
      attendanceTotal: 0,
      incidentTotal: 0
    },
    drivers: [],
    vehicles: [],
    attendanceRows: [],
    visibleRows: [],
    title: '司机资料',
    hint: '只读查询司机联系方式、体检、驾照和在留到期。'
  },

  onShow() {
    api.setActiveTab('/pages/info/index');
    this.refreshTabBar();
    const session = api.getSession();
    const section = wx.getStorageSync('operations_info_section') || 'drivers';
    this.setData({ session, section });
    this.loadInfo();
  },

  refreshTabBar() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) this.getTabBar().refresh();
  },

  loadInfo() {
    this.setData({ loading: true });
    Promise.all([
      api.drivers().catch(() => ({ drivers: [] })),
      api.vehicles().catch(() => ({ vehicles: [] })),
      api.assignments().catch(() => ({ assignments: [] })),
      api.dashboard().catch(() => ({ counts: {} }))
    ]).then(([driversRes, vehiclesRes, assignmentsRes, dashboard]) => {
      const drivers = (driversRes.drivers || []).map((item) => this.decorateDriver(item));
      const vehicles = (vehiclesRes.vehicles || []).map((item) => this.decorateVehicle(item));
      const attendanceRows = this.buildAttendanceRows(assignmentsRes.assignments || []);
      const summary = this.buildSummary(drivers, vehicles, attendanceRows, dashboard.counts || {});
      const visibleRows = this.rowsForSection(this.data.section, drivers, vehicles, attendanceRows, this.data.search);
      const copy = this.copyForSection(this.data.section);
      this.setData({
        drivers,
        vehicles,
        attendanceRows,
        summary,
        visibleRows,
        title: copy.title,
        hint: copy.hint,
        loading: false
      });
    }).catch(() => {
      this.setData({ loading: false });
      wx.showToast({ title: '信息读取失败', icon: 'none' });
    });
  },

  switchSection(e) {
    const section = e.currentTarget.dataset.section || 'drivers';
    wx.setStorageSync('operations_info_section', section);
    const copy = this.copyForSection(section);
    this.setData({
      section,
      title: copy.title,
      hint: copy.hint,
      visibleRows: this.rowsForSection(section, this.data.drivers, this.data.vehicles, this.data.attendanceRows, this.data.search)
    });
  },

  onSearch(e) {
    const search = e.detail.value || '';
    this.setData({
      search,
      visibleRows: this.rowsForSection(this.data.section, this.data.drivers, this.data.vehicles, this.data.attendanceRows, search)
    });
  },

  decorateDriver(driver) {
    const healthDue = driver.health_check_due_date || this.addDays(driver.health_check_date, 365);
    const licenseDue = driver.license_due_date || driver.license_expiry_date;
    return {
      id: driver.id,
      title: driver.name || driver.driver_name || '-',
      meta: `${driver.driver_code || driver.code || '-'} · ${driver.phone || driver.mobile || '-'}`,
      body: `体检 ${driver.health_check_date || '-'} / 到期 ${healthDue || '-'} · 驾照 ${licenseDue || '-'}`,
      searchText: [
        driver.name, driver.driver_name, driver.driver_code, driver.code, driver.phone, driver.mobile,
        driver.wechat, driver.line, driver.whatsapp, driver.kakao, driver.email, driver.mail
      ].filter(Boolean).join(' '),
      fields: [
        this.field('所属营业所', driver.office || driver.branch || driver.sales_office),
        this.field('手机号', driver.phone || driver.mobile),
        this.field('微信', driver.wechat),
        this.field('LINE', driver.line),
        this.field('WhatsApp', driver.whatsapp),
        this.field('Kakao', driver.kakao),
        this.field('邮箱', driver.email || driver.mail),
        this.field('健康体检日', driver.health_check_date),
        this.field('健康体检到期', healthDue),
        this.field('驾照到期', licenseDue),
        this.field('在留资格', driver.residence_status),
        this.field('在留到期', driver.residence_due_date || driver.residence_expiry_date)
      ].filter(Boolean)
    };
  },

  decorateVehicle(vehicle) {
    const recentInspection = vehicle.latest_inspection_date || vehicle.last_inspection_date || vehicle.inspection_date || '';
    const recentShaken = vehicle.latest_vehicle_inspection_date || vehicle.last_vehicle_inspection_date || vehicle.vehicle_inspection_date || vehicle.shaken_registration_date || '';
    return {
      id: vehicle.id || vehicle.plate_number,
      title: vehicle.plate_number || '-',
      meta: `${vehicle.color || '-'} · ${vehicle.vehicle_type || vehicle.car_model || '-'}`,
      body: `最近点检 ${recentInspection || '-'} · 最近年检 ${recentShaken || '-'}`,
      searchText: [
        vehicle.plate_number, vehicle.vehicle_code, vehicle.vehicle_type, vehicle.car_model, vehicle.color,
        recentInspection, recentShaken, vehicle.first_registration_date, vehicle.initial_registration_date,
        vehicle.company_registration_date, vehicle.company_join_date
      ].filter(Boolean).join(' '),
      fields: [
        this.field('车牌', vehicle.plate_number),
        this.field('颜色', vehicle.color),
        this.field('型号', vehicle.vehicle_type || vehicle.car_model),
        this.field('最近点检日期', recentInspection),
        this.field('最近年检日期', recentShaken),
        this.field('初登录时间', vehicle.first_registration_date || vehicle.initial_registration_date),
        this.field('到社时间', vehicle.company_registration_date || vehicle.company_join_date)
      ].filter(Boolean)
    };
  },
  buildAttendanceRows(assignments) {
    const today = this.formatDate(new Date());
    return (assignments || [])
      .filter((item) => String(item.order_date || '').slice(0, 10) === today)
      .map((item) => ({
        id: item.assignment_id || item.id,
        title: item.driver_name || '未定司机',
        meta: `${item.plate_number || '未定车辆'} · ${item.start_time || '--:--'}`,
        body: `${item.pickup_location || '-'} -> ${item.dropoff_location || '-'}`,
        searchText: [item.driver_name, item.plate_number, item.oid, item.order_id, item.pickup_location, item.dropoff_location].filter(Boolean).join(' '),
        fields: [
          this.field('日期', item.order_date),
          this.field('出库车辆', item.plate_number),
          this.field('出勤司机', item.driver_name),
          this.field('睡眠时间', item.sleep_hours || item.sleep_time),
          this.field('出库点呼', item.depart_call_time),
          this.field('出库时间', item.departure_time || item.vehicle_out_time),
          this.field('入库时间', item.return_time || item.vehicle_in_time),
          this.field('休息时间', item.rest_time || item.break_time),
          this.field('入库点呼', item.return_call_time)
        ].filter(Boolean)
      }));
  },

  buildSummary(drivers, vehicles, attendanceRows, counts) {
    const healthDue = drivers.filter((item) => this.isDueSoon(this.valueOfField(item.fields, '健康体检到期'))).length;
    const licenseDue = drivers.filter((item) => this.isDueSoon(this.valueOfField(item.fields, '驾照到期'))).length;
    const vehicleNormal = vehicles.filter((item) => item.meta.indexOf('正常') >= 0).length;
    const vehicleRepair = vehicles.filter((item) => item.meta.indexOf('维修') >= 0).length;
    const vehicleRetired = vehicles.filter((item) => item.meta.indexOf('减车') >= 0).length;
    return {
      driverTotal: drivers.length,
      healthDue,
      licenseDue,
      vehicleTotal: vehicles.length,
      vehicleNormal,
      vehicleRepair,
      vehicleRetired,
      attendanceTotal: attendanceRows.length,
      incidentTotal: Number(counts.exception_orders || counts.incident_orders || 0)
    };
  },

  rowsForSection(section, drivers, vehicles, attendanceRows, search) {
    const rows = section === 'vehicles' ? vehicles : section === 'attendance' ? attendanceRows : drivers;
    const keyword = String(search || '').trim().toLowerCase();
    if (!keyword) return rows;
    return rows.filter((item) => String(`${item.title} ${item.meta} ${item.body} ${item.searchText || ''}`).toLowerCase().indexOf(keyword) >= 0);
  },

  copyForSection(section) {
    return {
      drivers: { title: '司机资料', hint: '只读查询司机联系方式、体检、驾照和在留到期。' },
      vehicles: { title: '车辆资料', hint: '只读查询车辆状态、点检、年检、轮胎和维修说明。' },
      attendance: { title: '今日出勤', hint: '查看今日出勤司机、车辆、出入库和休息申报。完整周/月统计在 Web 出勤台账。' }
    }[section] || { title: '司机资料', hint: '只读查询司机联系方式、体检、驾照和在留到期。' };
  },

  field(label, value) {
    const text = value === undefined || value === null ? '' : String(value).trim();
    if (!text || text === '-') return null;
    return { label, value: text };
  },

  valueOfField(fields, label) {
    const hit = (fields || []).find((item) => item.label === label);
    return hit ? hit.value : '';
  },

  isDueSoon(dateText) {
    const days = this.daysUntil(dateText);
    return days !== null && days <= 30;
  },

  daysUntil(dateText) {
    if (!dateText) return null;
    const target = new Date(`${dateText}T00:00:00`);
    if (Number.isNaN(target.getTime())) return null;
    const today = new Date();
    const base = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    return Math.ceil((target.getTime() - base.getTime()) / 86400000);
  },

  addDays(dateText, days) {
    if (!dateText) return '';
    const date = new Date(`${dateText}T00:00:00`);
    if (Number.isNaN(date.getTime())) return '';
    date.setDate(date.getDate() + days);
    return this.formatDate(date);
  },

  vehicleStatusText(status) {
    const raw = String(status || '').toLowerCase();
    if (raw.indexOf('retired') >= 0 || raw.indexOf('removed') >= 0 || raw.indexOf('减车') >= 0) return '减车';
    if (raw.indexOf('maintenance') >= 0 || raw.indexOf('repair') >= 0 || raw.indexOf('维修') >= 0) return '维修';
    return '正常';
  },

  formatDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  }
});
