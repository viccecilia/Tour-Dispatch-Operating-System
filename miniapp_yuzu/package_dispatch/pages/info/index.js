const api = require('../../utils/api');

const VEHICLE_REMINDER_DAYS = 30;
const DRIVER_HEALTH_REMINDER_DAYS = 30;
const HIDDEN_RESOURCE_VEHICLE_TAILS = ['7721', '3724', '7728'];
const HIDDEN_DRIVER_NAMES = [
  '刘明海',
  '劉明海',
  '刘晟',
  '劉晟',
  '王爽',
  '楊増福',
  '滝澤雅禾',
  '富塚紀子',
  '陳鈴',
  '唐洋洲',
  '谷口張延瑾',
  '谷口延瑾',
  '福田弘一'
];

Page({
  data: {
    session: null,
    section: 'vehicles',
    loading: false,
    search: '',
    summary: {
      driverTotal: 0,
      healthDue: 0,
      licenseDue: 0,
      vehicleTotal: 0,
      pdfTotal: 0,
      categoryTotal: 0,
      vehicleInspectionDue: 0,
      threeMonthDue: 0
    },
    drivers: [],
    retiredDrivers: [],
    vehicles: [],
    vehicleInspectionAlerts: [],
    threeMonthAlerts: [],
    healthAlerts: [],
    visibleRows: [],
    expandedDriverId: '',
    driverStatusLabels: ['在职', '休假', '离职'],
    driverStatusValues: ['available', 'resting', 'retired'],
    vehicleStatusLabels: ['运行中', '修理中', '废车'],
    vehicleStatusValues: ['available', 'maintenance', 'retired'],
    vehicleListMode: 'available',
    vehicleListFilters: [
      { label: '运行', value: 'available' },
      { label: '维修', value: 'maintenance' },
      { label: '废车', value: 'retired' }
    ],
    vehicleListModeIndex: 0,
    vehicleListModeLabel: '运行',
    driverListMode: 'active',
    driverListFilters: [
      { label: '在职', value: 'active' },
      { label: '休假', value: 'resting' },
      { label: '离职', value: 'retired' }
    ],
    officeFilter: 'all',
    officeFilterIndex: 0,
    officeFilterLabel: '全部',
    officeFilters: [
      { label: '全部', value: 'all' },
      { label: '大阪', value: 'osaka' },
      { label: '京都', value: 'kyoto' }
    ],
    driverListModeIndex: 0,
    driverListModeLabel: '在职',
    title: '车辆信息',
    hint: '查看全部车辆基础资料、车检点检记录，并下载车辆 PDF。'
  },

  onShow() {
    api.setActiveTab('/package_dispatch/pages/info/index');
    this.refreshTabBar();
    const session = api.getSession();
    const cachedSection = wx.getStorageSync('operations_info_section') || 'vehicles';
    const section = cachedSection === 'drivers' ? 'drivers' : 'vehicles';
    this.setData({ session, section });
    this.loadInfo();
  },

  refreshTabBar() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) this.getTabBar().refresh();
  },

  loadInfo() {
    this.setData({ loading: true });
    api.resourceLibrary().then((library) => {
      const libraryDrivers = library.drivers || [];
      const vehicles = this.mergeVehicles(library.vehicles || [], []);
      const drivers = this.mergeDrivers(libraryDrivers, [])
        .filter((driver) => !this.isRetiredDriverStatus(driver.status || driver.driverStatus))
        .filter((driver) => !this.isHiddenDriver(driver));
      const retiredDrivers = this.mergeDrivers(libraryDrivers, [])
        .filter((driver) => this.isRetiredDriverStatus(driver.status || driver.driverStatus))
        .filter((driver) => !this.isHiddenDriver(driver));
      const alerts = this.buildAlerts(drivers, vehicles);
      const summary = this.buildSummary(drivers, vehicles, library.summary || {}, alerts);
      const copy = this.copyForSection(this.data.section);
      this.setData({
        drivers,
        retiredDrivers,
        vehicles,
        vehicleInspectionAlerts: alerts.vehicleInspection,
        threeMonthAlerts: alerts.threeMonth,
        healthAlerts: alerts.health,
        summary,
        title: copy.title,
        hint: copy.hint,
        visibleRows: this.rowsForSection(this.data.section, drivers, vehicles, this.data.search, this.data.officeFilter, retiredDrivers, this.data.driverListMode, this.data.vehicleListMode),
        loading: false
      });
    }).catch(() => {
      this.setData({ loading: false });
      wx.showToast({ title: '信息读取失败', icon: 'none' });
    });
  },

  mergeVehicles(libraryVehicles, apiVehicles) {
    const rows = [];
    const seen = {};
    (libraryVehicles || []).forEach((item) => {
      const row = this.decorateVehicle(item);
      if (this.isHiddenVehicle(row)) return;
      const key = row.suffix || row.title;
      seen[key] = row;
      seen[row.title] = row;
      rows.push(row);
    });
    (apiVehicles || []).forEach((item) => {
      const suffix = this.lastDigits(item.plate_number || item.vehicle_code);
      const row = this.decorateVehicle(item);
      const existing = seen[suffix] || seen[item.plate_number] || seen[row.title];
      if (existing) {
        Object.assign(existing, {
          resourceId: row.resourceId,
          status: row.status,
          statusValue: row.statusValue,
          statusLabel: row.statusLabel,
          statusIndex: row.statusIndex
        });
        return;
      }
      if (this.isHiddenVehicle(row)) return;
      rows.push(row);
    });
    return rows.sort((a, b) => String(a.suffix || a.title).localeCompare(String(b.suffix || b.title), 'zh-Hans-CN'));
  },

  mergeDrivers(libraryDrivers, apiDrivers) {
    const rows = [];
    const seen = {};
    const indexRow = (row) => {
      this.driverMergeKeys(row).forEach((key) => {
        if (key) seen[key] = row;
      });
    };
    (libraryDrivers || []).forEach((item) => {
      const row = this.decorateDriver(item);
      indexRow(row);
      rows.push(row);
    });
    (apiDrivers || []).forEach((item) => {
      const apiRow = this.decorateDriver(item);
      const existing = this.driverMergeKeys(apiRow).map((key) => seen[key]).filter(Boolean)[0];
      if (existing) {
        Object.assign(existing, {
          resourceId: apiRow.resourceId,
          status: apiRow.status,
          driverStatus: apiRow.driverStatus,
          statusValue: apiRow.statusValue,
          statusLabel: apiRow.statusLabel,
          statusIndex: apiRow.statusIndex
        });
        indexRow(existing);
        return;
      }
      indexRow(apiRow);
      rows.push(apiRow);
    });
    return rows.sort((a, b) => String(a.title).localeCompare(String(b.title), 'zh-Hans-CN'));
  },

  driverMergeKeys(row) {
    const title = this.normalizeDriverMergeText(row && row.title);
    const phone = this.lastDigits(row && row.phone || row && row.meta);
    return [
      row && row.driverCode,
      row && row.resourceId ? `resource:${row.resourceId}` : '',
      title ? `name:${title}` : '',
      phone ? `phone:${phone}` : ''
    ].filter(Boolean);
  },

  normalizeDriverMergeText(value) {
    return String(value || '').replace(/[\s\u3000()（）·・]/g, '');
  },

  isRetiredDriverStatus(status) {
    const text = String(status || '').toLowerCase();
    return text === 'retired' || text === 'resigned';
  },

  isHiddenDriver(driver) {
    const text = [
      driver && driver.name,
      driver && driver.driver_name,
      driver && driver.display_name,
      driver && driver.title,
      driver && driver['運転手名']
    ].filter(Boolean).join('');
    const normalized = this.normalizeHiddenDriverName(text);
    if (!normalized) return false;
    return HIDDEN_DRIVER_NAMES.some((name) => {
      const target = this.normalizeHiddenDriverName(name);
      return normalized === target || normalized.indexOf(target) >= 0 || target.indexOf(normalized) >= 0;
    });
  },

  normalizeHiddenDriverName(value) {
    return String(value || '').replace(/[\s\u3000()（）·・]/g, '');
  },

  isHiddenVehicle(vehicle) {
    const text = [
      vehicle && vehicle.suffix,
      vehicle && vehicle.title,
      vehicle && vehicle.plate_number,
      vehicle && vehicle.plate,
      vehicle && vehicle.id
    ].filter(Boolean).join(' ');
    return HIDDEN_RESOURCE_VEHICLE_TAILS.some((tail) => text.indexOf(tail) >= 0);
  },

  decorateDriver(driver) {
    const name = driver.name || driver.driver_name || driver['運転手名'] || '-';
    const code = driver.driver_code || driver.code || driver['運転手ID'] || '';
    const phone = driver.phone || driver.mobile || driver['携帯電話番号'] || '';
    const healthDate = driver.health_check_date || driver['健康诊断日期'] || '';
    const healthDue = driver.health_check_due_date || this.addDays(healthDate, 365);
    const licenseDue = driver.license_due_date || driver.license_expiry_date || driver['免许有効期限'] || '';
    const residenceDue = driver.residence_due_date || driver.residence_expiry_date || driver['再留期限有效日期'] || '';
    const statusValue = this.normalizeResourceDriverStatus(driver.status || driver.driver_status || driver.driverStatus || '');
    const officeText = driver.office || driver.branch || driver.sales_office || driver['所属営業所'] || '';
    const officeType = this.officeTypeForResource([officeText, name, code].join(' '));
    return {
      id: driver.id || code || name,
      resourceId: driver.id || '',
      type: 'driver',
      title: name,
      driverCode: code,
      healthExamDate: healthDate,
      status: driver.status || driver.driver_status || '',
      driverStatus: driver.driver_status || driver.driverStatus || driver.status || '',
      statusValue,
      statusLabel: this.driverStatusLabel(statusValue),
      statusIndex: this.driverStatusIndex(statusValue),
      officeText,
      officeType,
      officeLabel: this.officeLabel(officeType),
      meta: [code, phone].filter(Boolean).join(' · ') || '人员资料',
      body: `体检 ${healthDate || '-'} / 到期 ${healthDue || '-'} · 驾照 ${licenseDue || '-'}`,
      searchText: [
        name, code, phone, officeText, driver.wechat, driver.line, driver.whatsapp, driver.kakao,
        driver.email, driver.mail, driver['所属営業所'], driver['特长'], driver['メールアドレス']
      ].filter(Boolean).join(' '),
      fields: [
        this.field('所属营业所', officeText),
        this.field('手机号', phone),
        this.field('邮箱', driver.email || driver.mail || driver['メールアドレス']),
        this.field('状态', driver.status || driver['状態']),
        this.field('在留资格', driver.residence_status || driver['在留資格']),
        this.field('在留到期', residenceDue),
        this.field('健康体检日', healthDate),
        this.field('健康体检到期', healthDue),
        this.field('驾照到期', licenseDue),
        this.field('备注', driver.remark || driver['来源/备注'])
      ].filter(Boolean)
    };
  },

  decorateVehicle(vehicle) {
    const plate = vehicle.plate_number || vehicle.plate || vehicle['车牌号'] || '-';
    const suffix = vehicle.suffix || vehicle['后四位'] || this.lastDigits(plate);
    const docs = (vehicle.docs || vehicle.files || []).map((item) => this.decorateDoc(item));
    const docGroups = this.groupDocs(docs);
    const vehicleInspectionDate = this.normalizeDate(vehicle.vehicle_inspection_due_date || vehicle.shaken_due_date || vehicle['车检到期'] || vehicle['車検満了日']);
    const latestThreeMonthDate = this.latestDocDate(docs, '3ヶ月点検')
      || this.normalizeDate(vehicle.three_month_inspection_date || vehicle.latest_inspection_date || vehicle['3ヶ月点検日期']);
    const annualInspectionDate = this.latestDocDate(docs, '車検')
      || this.latestDocDate(docs, '车检')
      || this.latestDocDate(docs, '自動車檢查証記録事項')
      || this.latestDocDate(docs, '自動車検査証記録事項')
      || this.latestDocDate(docs, '自動車')
      || this.latestDocDate(docs, '12ヶ月点検')
      || this.normalizeDate(vehicle.shaken_date || vehicle.annual_inspection_date || vehicle.latest_vehicle_inspection_date || vehicle['車検日期'] || vehicle['12ヶ月点検日期']);
    const nextRequired = this.nextVehicleRequiredNode(vehicleInspectionDate, latestThreeMonthDate, annualInspectionDate);
    const statusValue = this.normalizeResourceVehicleStatus(vehicle.status || vehicle.vehicle_status || vehicle.maintenance_status || '');
    const officeText = vehicle.office || vehicle.branch || vehicle.sales_office || vehicle.vehicle_group || vehicle['所属営業所'] || vehicle['事务所'] || '';
    const officeType = this.officeTypeForResource([officeText, plate, suffix, vehicle.vehicle_type || vehicle.car_model || vehicle['车型'] || ''].join(' '));
    return {
      id: vehicle.id || vehicle.folder || plate,
      resourceId: vehicle.resourceId || vehicle.resource_id || vehicle.vehicle_id || (vehicle.plate_number || vehicle.plate_short_code || vehicle.status ? vehicle.id : ''),
      type: 'vehicle',
      title: plate,
      suffix,
      status: vehicle.status || '',
      statusValue,
      statusLabel: this.vehicleStatusLabel(statusValue),
      statusIndex: this.vehicleStatusIndex(statusValue),
      officeText,
      officeType,
      officeLabel: this.officeLabel(officeType),
      meta: [vehicle.vehicle_type || vehicle.car_model || vehicle['车型'], vehicle.chassis_number || vehicle.chassis || vehicle['车台番号']]
        .filter(Boolean).join(' · ') || '车辆资料',
      vehicleInspectionDueIso: vehicleInspectionDate ? vehicleInspectionDate.iso : '',
      vehicleInspectionDueText: vehicleInspectionDate ? vehicleInspectionDate.text : '',
      nextRequiredType: nextRequired.type,
      nextRequiredLabel: nextRequired.label,
      nextRequiredIso: nextRequired.date ? nextRequired.date.iso : '',
      nextRequiredText: nextRequired.date ? nextRequired.date.text : '',
      vehicleInspectionAlertIso: nextRequired.type === 'vehicle' && vehicleInspectionDate && nextRequired.date ? nextRequired.date.iso : '',
      vehicleInspectionAlertText: nextRequired.type === 'vehicle' && vehicleInspectionDate && nextRequired.date ? nextRequired.date.text : '',
      threeMonthDueIso: nextRequired.type === 'inspection' && nextRequired.date ? nextRequired.date.iso : '',
      threeMonthDueText: nextRequired.type === 'inspection' && nextRequired.date ? nextRequired.date.text : '',
      latestThreeMonthText: latestThreeMonthDate ? latestThreeMonthDate.text : '',
      body: `${nextRequired.label || '下一节点'} ${nextRequired.date ? nextRequired.date.text : '-'} · PDF ${docs.length}`,
      docCount: docs.length,
      docs,
      docGroups,
      searchText: [
        plate, suffix, officeText, vehicle.vehicle_code, vehicle.vehicle_type, vehicle.car_model, vehicle.color,
        vehicle.chassis_number, vehicle.chassis, vehicle.model_code, vehicle.folder,
        docs.map((doc) => `${doc.name} ${doc.category}`).join(' ')
      ].filter(Boolean).join(' '),
      fields: [
        this.field('后四位', suffix),
        this.field('事务所', this.officeLabel(officeType) || officeText),
        this.field('车型', vehicle.vehicle_type || vehicle.car_model || vehicle['车型']),
        this.field('型式', vehicle.model_code || vehicle['型式']),
        this.field('车台番号', vehicle.chassis_number || vehicle.chassis || vehicle['车台番号']),
        this.field('车检到期', vehicleInspectionDate && vehicleInspectionDate.text),
        this.field('下一应做事项', nextRequired.label && nextRequired.date ? `${nextRequired.label} ${nextRequired.date.text}` : ''),
        this.field('3个月点检到期', nextRequired.type === 'inspection' && nextRequired.date && nextRequired.date.text),
        this.field('最近3个月点检', latestThreeMonthDate && latestThreeMonthDate.text),
        this.field('最近车检/12个月点检', annualInspectionDate && annualInspectionDate.text),
        this.field('PDF资料', docs.length ? `${docs.length} 个文件` : '')
      ].filter(Boolean)
    };
  },

  decorateDoc(doc) {
    const fileKey = doc.file_key || doc.href || '';
    return {
      name: doc.name || '车辆资料.pdf',
      category: doc.category || '其他',
      date: doc.date || '无日期',
      sizeLabel: doc.size_label || '',
      fileKey,
      url: doc.download_url || (fileKey ? api.resourceLibraryFileUrl(fileKey) : '')
    };
  },

  groupDocs(docs) {
    const byCategory = {};
    (docs || []).forEach((doc) => {
      const key = doc.category || '其他';
      if (!byCategory[key]) byCategory[key] = [];
      byCategory[key].push(doc);
    });
    return Object.keys(byCategory).sort().map((category) => ({ category, files: byCategory[category] }));
  },

  buildSummary(drivers, vehicles, librarySummary, alerts) {
    const licenseDue = drivers.filter((item) => this.isDueSoon(this.valueOfField(item.fields, '驾照到期'))).length;
    const pdfTotal = vehicles.reduce((sum, item) => sum + Number(item.docCount || 0), 0);
    return {
      driverTotal: drivers.length || Number(librarySummary.drivers || 0),
      healthDue: alerts.health.length,
      licenseDue,
      vehicleTotal: vehicles.length || Number(librarySummary.vehicles || 0),
      pdfTotal: pdfTotal || Number(librarySummary.pdf_files || 0),
      categoryTotal: Number(librarySummary.categories || 0),
      vehicleInspectionDue: alerts.vehicleInspection.length,
      threeMonthDue: alerts.threeMonth.length
    };
  },

  buildAlerts(drivers, vehicles) {
    return {
      vehicleInspection: this.buildVehicleAlerts(vehicles, 'vehicleInspectionAlertIso', 'vehicleInspectionAlertText'),
      threeMonth: this.buildVehicleAlerts(vehicles, 'threeMonthDueIso', 'threeMonthDueText'),
      health: this.buildDriverHealthAlerts(drivers)
    };
  },

  buildVehicleAlerts(vehicles, isoKey, textKey) {
    return (vehicles || [])
      .map((item) => {
        const days = this.daysUntil(item[isoKey]);
        if (days === null || days > VEHICLE_REMINDER_DAYS) return null;
        return {
          id: `${isoKey}-${item.id}`,
          title: item.title,
          meta: `${item[textKey] || '-'} · 完成后请上传PDF材料`,
          status: this.dueStatusText(days),
          sortDays: days,
          tone: days < 0 ? 'danger' : days <= 7 ? 'warning' : 'normal'
        };
      })
      .filter(Boolean)
      .sort((a, b) => this.alertSortValue(a.sortDays) - this.alertSortValue(b.sortDays));
  },

  buildDriverHealthAlerts(drivers) {
    return (drivers || [])
      .map((item) => {
        const due = this.valueOfField(item.fields, '健康体检到期');
        const days = this.daysUntil(due);
        if (days === null || days > DRIVER_HEALTH_REMINDER_DAYS) return null;
        return {
          id: `health-${item.id}`,
          title: item.title,
          meta: due,
          status: this.dueStatusText(days),
          sortDays: days,
          tone: days < 0 ? 'danger' : days <= 7 ? 'warning' : 'normal'
        };
      })
      .filter(Boolean)
      .sort((a, b) => this.alertSortValue(a.sortDays) - this.alertSortValue(b.sortDays));
  },

  rowsForSection(section, drivers, vehicles, search, officeFilter = 'all', retiredDrivers = [], driverListMode = 'active', vehicleListMode = 'available') {
    let rows = (vehicles || []).filter((item) => {
      const status = this.normalizeResourceVehicleStatus(item.statusValue || item.status || item.vehicleStatus);
      return status === vehicleListMode;
    });
    if (section === 'drivers') {
      if (driverListMode === 'retired') {
        rows = retiredDrivers;
      } else {
        rows = (drivers || []).filter((item) => {
          const status = this.normalizeResourceDriverStatus(item.statusValue || item.status || item.driverStatus);
          return driverListMode === 'resting' ? status === 'resting' : status !== 'resting' && status !== 'retired';
        });
      }
    }
    const keyword = String(search || '').trim().toLowerCase();
    return rows
      .filter((item) => this.matchesOfficeFilter(item, officeFilter))
      .filter((item) => !keyword || String(`${item.title} ${item.meta} ${item.body} ${item.searchText || ''} ${item.officeLabel || ''}`).toLowerCase().indexOf(keyword) >= 0);
  },

  switchSection(e) {
    const section = e.currentTarget.dataset.section || 'vehicles';
    wx.setStorageSync('operations_info_section', section);
    const copy = this.copyForSection(section);
    this.setData({
      section,
      expandedDriverId: '',
      title: copy.title,
      hint: copy.hint,
      visibleRows: this.rowsForSection(section, this.data.drivers, this.data.vehicles, this.data.search, this.data.officeFilter, this.data.retiredDrivers, this.data.driverListMode, this.data.vehicleListMode)
    });
  },

  onSearch(e) {
    const search = e.detail.value || '';
    this.setData({
      search,
      expandedDriverId: '',
      visibleRows: this.rowsForSection(this.data.section, this.data.drivers, this.data.vehicles, search, this.data.officeFilter, this.data.retiredDrivers, this.data.driverListMode, this.data.vehicleListMode)
    });
  },

  switchOfficeFilter(e) {
    const officeFilter = (e.currentTarget.dataset || {}).office || 'all';
    const officeFilterIndex = Math.max(0, this.data.officeFilters.findIndex((item) => item.value === officeFilter));
    const officeFilterItem = this.data.officeFilters[officeFilterIndex] || this.data.officeFilters[0];
    this.setData({
      officeFilter,
      officeFilterIndex,
      officeFilterLabel: officeFilterItem.label,
      expandedDriverId: '',
      visibleRows: this.rowsForSection(this.data.section, this.data.drivers, this.data.vehicles, this.data.search, officeFilter, this.data.retiredDrivers, this.data.driverListMode, this.data.vehicleListMode)
    });
  },

  onOfficeFilterChange(e) {
    const officeFilterIndex = Number(e.detail.value || 0);
    const officeFilterItem = this.data.officeFilters[officeFilterIndex] || this.data.officeFilters[0] || { label: '全部', value: 'all' };
    this.setData({
      officeFilterIndex,
      officeFilter: officeFilterItem.value,
      officeFilterLabel: officeFilterItem.label,
      expandedDriverId: '',
      visibleRows: this.rowsForSection(this.data.section, this.data.drivers, this.data.vehicles, this.data.search, officeFilterItem.value, this.data.retiredDrivers, this.data.driverListMode, this.data.vehicleListMode)
    });
  },

  switchDriverListMode(e) {
    const driverListMode = (e.currentTarget.dataset || {}).mode || 'active';
    const driverListModeIndex = Math.max(0, this.data.driverListFilters.findIndex((item) => item.value === driverListMode));
    const driverListModeItem = this.data.driverListFilters[driverListModeIndex] || this.data.driverListFilters[0];
    this.setData({
      driverListMode,
      driverListModeIndex,
      driverListModeLabel: driverListModeItem.label,
      expandedDriverId: '',
      visibleRows: this.rowsForSection(this.data.section, this.data.drivers, this.data.vehicles, this.data.search, this.data.officeFilter, this.data.retiredDrivers, driverListMode, this.data.vehicleListMode)
    });
  },

  onDriverListModeChange(e) {
    const driverListModeIndex = Number(e.detail.value || 0);
    const driverListModeItem = this.data.driverListFilters[driverListModeIndex] || this.data.driverListFilters[0] || { label: '在职', value: 'active' };
    this.setData({
      driverListModeIndex,
      driverListMode: driverListModeItem.value,
      driverListModeLabel: driverListModeItem.label,
      expandedDriverId: '',
      visibleRows: this.rowsForSection(this.data.section, this.data.drivers, this.data.vehicles, this.data.search, this.data.officeFilter, this.data.retiredDrivers, driverListModeItem.value, this.data.vehicleListMode)
    });
  },

  onVehicleListModeChange(e) {
    const vehicleListModeIndex = Number(e.detail.value || 0);
    const vehicleListModeItem = this.data.vehicleListFilters[vehicleListModeIndex] || this.data.vehicleListFilters[0] || { label: '运行', value: 'available' };
    this.setData({
      vehicleListModeIndex,
      vehicleListMode: vehicleListModeItem.value,
      vehicleListModeLabel: vehicleListModeItem.label,
      expandedDriverId: '',
      visibleRows: this.rowsForSection(this.data.section, this.data.drivers, this.data.vehicles, this.data.search, this.data.officeFilter, this.data.retiredDrivers, this.data.driverListMode, vehicleListModeItem.value)
    });
  },

  toggleDriverRow(e) {
    const id = String((e.currentTarget.dataset || {}).id || '');
    if (!id) return;
    this.setData({ expandedDriverId: this.data.expandedDriverId === id ? '' : id });
  },

  noop() {},

  updateDriverStatusByLibrary(dataset, status, driverKey) {
    return api.updateResourceDriverStatus({
      driver_key: driverKey,
      driver_code: dataset.driverCode || '',
      phone: dataset.phone || '',
      name: dataset.title || '',
      status,
      driver_status: status
    });
  },

  isNotFoundError(err) {
    const message = String((err && (err.error || err.detail || err.errMsg || err.message)) || '').toLowerCase();
    return Number(err && err.statusCode) === 404 || message.indexOf('not_found') >= 0 || message.indexOf('not found') >= 0;
  },

  updateDriverStatus(e) {
    const dataset = e.currentTarget.dataset || {};
    const resourceId = dataset.resourceId || dataset.id || '';
    const driverKey = dataset.driverCode || dataset.phone || dataset.title || '';
    const index = Number(e.detail.value || 0);
    const status = this.data.driverStatusValues[index] || 'available';
    const label = this.driverStatusLabel(status);
    if (!resourceId && !driverKey) {
      wx.showToast({ title: '缺少人员识别信息', icon: 'none' });
      return;
    }
    wx.showModal({
      title: '调整人员状态',
      content: `${dataset.title || '人员'}\n状态改为：${label}`,
      confirmText: '更新',
      success: (res) => {
        if (!res.confirm) return;
        wx.showLoading({ title: '更新中' });
        const task = resourceId
          ? api.updateResourceDriver(resourceId, { status, driver_status: status }).catch((err) => {
            if (driverKey && this.isNotFoundError(err)) {
              return this.updateDriverStatusByLibrary(dataset, status, driverKey);
            }
            return Promise.reject(err);
          })
          : this.updateDriverStatusByLibrary(dataset, status, driverKey);
        task.then(() => {
          wx.hideLoading();
          wx.showToast({ title: '已更新', icon: 'success' });
          this.loadInfo();
        }).catch((err) => {
          wx.hideLoading();
          wx.showToast({ title: err && err.error ? err.error : '更新失败', icon: 'none' });
        });
      }
    });
  },

  updateVehicleStatus(e) {
    const dataset = e.currentTarget.dataset || {};
    const resourceId = dataset.resourceId || dataset.id || '';
    const index = Number(e.detail.value || 0);
    const status = this.data.vehicleStatusValues[index] || 'available';
    const label = this.vehicleStatusLabel(status);
    const vehicleKey = dataset.suffix || dataset.title || '';
    if (!resourceId && !vehicleKey) {
      wx.showToast({ title: '这条车辆资料暂不能改状态', icon: 'none' });
      return;
    }
    wx.showModal({
      title: '调整车辆状态',
      content: `${dataset.title || '车辆'}\n状态改为：${label}`,
      confirmText: '更新',
      success: (res) => {
        if (!res.confirm) return;
        wx.showLoading({ title: '更新中' });
        const task = resourceId
          ? api.updateResourceVehicle(resourceId, { status }).catch((err) => {
            if (vehicleKey && this.isNotFoundError(err)) {
              return api.updateResourceVehicleStatus({ vehicle_key: vehicleKey, status, vehicle_status: status });
            }
            return Promise.reject(err);
          })
          : api.updateResourceVehicleStatus({ vehicle_key: vehicleKey, status, vehicle_status: status });
        task.then(() => {
          wx.hideLoading();
          wx.showToast({ title: '已更新', icon: 'success' });
          this.loadInfo();
        }).catch((err) => {
          wx.hideLoading();
          wx.showToast({ title: err && err.error ? err.error : '更新失败', icon: 'none' });
        });
      }
    });
  },

  updateDriverHealthDate(e) {
    const dataset = e.currentTarget.dataset || {};
    const driverKey = dataset.key || dataset.title || '';
    const healthCheckDate = e.detail.value || '';
    if (!driverKey || !healthCheckDate) return;
    wx.showModal({
      title: '更新体检日期',
      content: `${dataset.title || driverKey}\n体检日期更新为 ${healthCheckDate}？`,
      confirmText: '更新',
      success: (res) => {
        if (!res.confirm) return;
        wx.showLoading({ title: '更新中' });
        api.updateResourceDriverHealth({
          driver_key: driverKey,
          health_check_date: healthCheckDate
        }).then(() => {
          wx.hideLoading();
          wx.showToast({ title: '已更新', icon: 'success' });
          this.loadInfo();
        }).catch((err) => {
          wx.hideLoading();
          wx.showToast({ title: err && err.error ? err.error : '更新失败', icon: 'none' });
        });
      }
    });
  },

  uploadDriverHealthDocument(e) {
    const dataset = e.currentTarget.dataset || {};
    const driverKey = dataset.key || dataset.title || '';
    const healthCheckDate = dataset.date || '';
    if (!driverKey) return;
    if (!healthCheckDate) {
      wx.showToast({ title: '请先选择体检日期', icon: 'none' });
      return;
    }
    wx.chooseMessageFile({
      count: 1,
      type: 'all',
      success: (chooseRes) => {
        const file = chooseRes.tempFiles && chooseRes.tempFiles[0];
        if (!file || !file.path) return;
        const fs = wx.getFileSystemManager();
        fs.readFile({
          filePath: file.path,
          encoding: 'base64',
          success: (readRes) => {
            wx.showModal({
              title: '上传体检资料',
              content: `${dataset.title || driverKey}\n体检日期 ${healthCheckDate}\n${file.name || '体检资料'}`,
              confirmText: '上传',
              success: (modalRes) => {
                if (!modalRes.confirm) return;
                wx.showLoading({ title: '上传中' });
                api.updateResourceDriverHealth({
                  driver_key: driverKey,
                  health_check_date: healthCheckDate,
                  file_name: file.name || 'health-check',
                  content_type: this.contentTypeForFile(file.name || ''),
                  file_base64: readRes.data
                }).then(() => {
                  wx.hideLoading();
                  wx.showToast({ title: '已上传', icon: 'success' });
                  this.loadInfo();
                }).catch((err) => {
                  wx.hideLoading();
                  wx.showToast({ title: err && err.error ? err.error : '上传失败', icon: 'none' });
                });
              }
            });
          },
          fail: () => wx.showToast({ title: '读取文件失败', icon: 'none' })
        });
      }
    });
  },

  contentTypeForFile(fileName) {
    const lower = String(fileName || '').toLowerCase();
    if (lower.endsWith('.pdf')) return 'application/pdf';
    if (lower.endsWith('.png')) return 'image/png';
    if (lower.endsWith('.webp')) return 'image/webp';
    return 'image/jpeg';
  },

  updateVehicleInspectionDate(e) {
    const dataset = e.currentTarget.dataset || {};
    const vehicleKey = dataset.key || dataset.title || '';
    const inspectionDate = e.detail.value || '';
    const inspectionType = dataset.type || 'inspection';
    if (!vehicleKey || !inspectionDate) return;
    wx.showLoading({ title: '更新中' });
    api.updateResourceVehicleInspection({
      vehicle_key: vehicleKey,
      inspection_type: inspectionType,
      inspection_date: inspectionDate
    }).then(() => {
      wx.hideLoading();
      wx.showToast({ title: '已更新', icon: 'success' });
      this.loadInfo();
    }).catch((err) => {
      wx.hideLoading();
      wx.showToast({ title: err && err.error ? err.error : '更新失败', icon: 'none' });
    });
  },

  uploadVehicleInspectionDocument(e) {
    const dataset = e.currentTarget.dataset || {};
    const vehicleKey = dataset.key || dataset.title || '';
    const inspectionType = dataset.type || 'inspection';
    const inspectionDate = dataset.date || this.todayIso();
    if (!vehicleKey) return;
    wx.chooseMessageFile({
      count: 1,
      type: 'all',
      success: (chooseRes) => {
        const file = chooseRes.tempFiles && chooseRes.tempFiles[0];
        if (!file || !file.path) return;
        wx.getFileSystemManager().readFile({
          filePath: file.path,
          encoding: 'base64',
          success: (readRes) => {
            wx.showLoading({ title: '上传中' });
            api.updateResourceVehicleInspection({
              vehicle_key: vehicleKey,
              inspection_type: inspectionType,
              inspection_date: inspectionDate,
              file_name: file.name || 'vehicle-inspection',
              content_type: this.contentTypeForFile(file.name || ''),
              file_base64: readRes.data
            }).then(() => {
              wx.hideLoading();
              wx.showToast({ title: '已上传', icon: 'success' });
              this.loadInfo();
            }).catch((err) => {
              wx.hideLoading();
              wx.showToast({ title: err && err.error ? err.error : '上传失败', icon: 'none' });
            });
          },
          fail: () => wx.showToast({ title: '读取文件失败', icon: 'none' })
        });
      }
    });
  },

  todayIso() {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${now.getFullYear()}-${month}-${day}`;
  },

  downloadDoc(e) {
    const url = e.currentTarget.dataset.url || '';
    const name = e.currentTarget.dataset.name || '车辆资料.pdf';
    const session = api.getSession();
    if (!url) {
      wx.showToast({ title: '文件地址为空', icon: 'none' });
      return;
    }
    wx.showLoading({ title: '下载中' });
    wx.downloadFile({
      url,
      header: session && session.token ? { Authorization: `Bearer ${session.token}` } : {},
      success: (res) => {
        if (res.statusCode !== 200) {
          wx.showToast({ title: '下载失败', icon: 'none' });
          return;
        }
        wx.openDocument({
          filePath: res.tempFilePath,
          fileType: 'pdf',
          showMenu: true,
          fail: () => wx.showToast({ title: `${name} 已下载，打开失败`, icon: 'none' })
        });
      },
      fail: () => wx.showToast({ title: '下载失败', icon: 'none' }),
      complete: () => wx.hideLoading()
    });
  },

  copyForSection(section) {
    return {
      vehicles: { title: '车辆信息', hint: '查看全部车辆基础资料、车检点检记录，并下载车辆 PDF。' },
      drivers: { title: '人员信息', hint: '查看司机和人员联系方式、证件、体检与在留期限。' }
    }[section] || { title: '车辆信息', hint: '查看全部车辆基础资料、车检点检记录，并下载车辆 PDF。' };
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

  lastDigits(value) {
    const digits = String(value || '').replace(/\D/g, '');
    return digits.slice(-4).replace(/^0+(?=\d)/, '');
  },

  normalizeResourceDriverStatus(status) {
    const text = String(status || '').trim().toLowerCase();
    if (['retired', 'resigned', 'deleted'].indexOf(text) >= 0 || status === '离职') return 'retired';
    if (['resting', 'leave', 'off', 'vacation'].indexOf(text) >= 0 || status === '休假') return 'resting';
    return 'available';
  },

  driverStatusLabel(status) {
    const value = this.normalizeResourceDriverStatus(status);
    return { available: '在职', resting: '休假', retired: '离职' }[value] || '在职';
  },

  driverStatusIndex(status) {
    const value = this.normalizeResourceDriverStatus(status);
    return Math.max(0, this.data.driverStatusValues.indexOf(value));
  },

  normalizeResourceVehicleStatus(status) {
    const text = String(status || '').trim().toLowerCase();
    if (['retired', 'removed', 'decommissioned', 'deleted'].indexOf(text) >= 0 || status === '废车') return 'retired';
    if (['maintenance', 'repair'].indexOf(text) >= 0 || status === '修理中') return 'maintenance';
    return 'available';
  },

  vehicleStatusLabel(status) {
    const value = this.normalizeResourceVehicleStatus(status);
    return { available: '运行中', maintenance: '修理中', retired: '废车' }[value] || '运行中';
  },

  vehicleStatusIndex(status) {
    const value = this.normalizeResourceVehicleStatus(status);
    return Math.max(0, this.data.vehicleStatusValues.indexOf(value));
  },

  officeTypeForResource(value) {
    const text = String(value || '').toLowerCase();
    if (text.indexOf('京都') >= 0 || text.indexOf('kyoto') >= 0) return 'kyoto';
    if (text.indexOf('大阪') >= 0 || text.indexOf('osaka') >= 0 || text.indexOf('なにわ') >= 0) return 'osaka';
    return 'osaka';
  },

  officeLabel(type) {
    return { osaka: '大阪', kyoto: '京都' }[type] || '';
  },

  matchesOfficeFilter(item, officeFilter) {
    if (!officeFilter || officeFilter === 'all') return true;
    return String(item && item.officeType || '') === officeFilter;
  },

  isDueSoon(dateText) {
    const days = this.daysUntil(dateText);
    return days !== null && days <= DRIVER_HEALTH_REMINDER_DAYS;
  },

  daysUntil(dateText) {
    if (!dateText) return null;
    const normalized = this.normalizeDate(dateText);
    if (!normalized) return null;
    dateText = normalized.iso;
    const target = new Date(`${dateText}T00:00:00`);
    if (Number.isNaN(target.getTime())) return null;
    const today = new Date();
    const base = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    return Math.ceil((target.getTime() - base.getTime()) / 86400000);
  },

  alertSortValue(days) {
    if (days === null || days === undefined || Number.isNaN(Number(days))) return 99999;
    const value = Number(days);
    if (value < 0) return value;
    return 10000 + value;
  },

  dueStatusText(days) {
    if (days < 0) return `已过期 ${Math.abs(days)} 天`;
    if (days === 0) return '今天到期';
    return `${days} 天后`;
  },

  latestDocDate(docs, categoryKeyword) {
    const candidates = (docs || [])
      .filter((doc) => String(doc.category || doc.name || '').indexOf(categoryKeyword) >= 0)
      .map((doc) => this.normalizeDate(doc.date || doc.name))
      .filter(Boolean)
      .sort((a, b) => String(b.iso).localeCompare(String(a.iso)));
    return candidates[0] || null;
  },

  normalizeDate(value) {
    const raw = String(value || '').trim();
    if (!raw || raw === '-' || /^\d{1,4}$/.test(raw)) return null;
    let match = raw.match(/(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})/);
    if (match) return this.dateObject(Number(match[1]), Number(match[2]), Number(match[3]));
    match = raw.match(/令和\s*(\d+)\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?/);
    if (match) return this.dateObject(2018 + Number(match[1]), Number(match[2]), Number(match[3]));
    match = raw.match(/R\s*(\d)(\d{2})(\d{2})/i);
    if (match) return this.dateObject(2018 + Number(match[1]), Number(match[2]), Number(match[3]));
    match = raw.match(/20(\d{2})(\d{2})(\d{2})/);
    if (match) return this.dateObject(2000 + Number(match[1]), Number(match[2]), Number(match[3]));
    return null;
  },

  dateObject(year, month, day) {
    if (!year || month < 1 || month > 12 || day < 1 || day > 31) return null;
    const date = new Date(year, month - 1, day);
    if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null;
    return { iso: this.formatDate(date), text: `令和${year - 2018}年${month}月${day}日` };
  },

  addMonths(dateText, months) {
    const normalized = this.normalizeDate(dateText);
    if (!normalized) return null;
    const parts = normalized.iso.split('-').map((item) => Number(item));
    const date = new Date(parts[0], parts[1] - 1, parts[2]);
    date.setMonth(date.getMonth() + months);
    return this.dateObject(date.getFullYear(), date.getMonth() + 1, date.getDate());
  },

  nextVehicleRequiredNode(vehicleInspectionDue, latestThreeMonthDate, latestVehicleInspectionDate) {
    const nextShaken = vehicleInspectionDue || (latestVehicleInspectionDate ? this.addMonths(latestVehicleInspectionDate.iso, 12) : null);
    const lastShaken = vehicleInspectionDue
      ? this.addMonths(vehicleInspectionDue.iso, -12)
      : latestVehicleInspectionDate || (nextShaken ? this.addMonths(nextShaken.iso, -12) : null);
    if (!lastShaken) {
      const fallback = latestThreeMonthDate ? this.addMonths(latestThreeMonthDate.iso, 3) : nextShaken;
      return { type: fallback === nextShaken ? 'vehicle' : 'inspection', label: fallback === nextShaken ? '车检' : '3个月点检', date: fallback };
    }
    const completedIso = [lastShaken, latestThreeMonthDate]
      .filter(Boolean)
      .map((item) => item.iso)
      .sort()
      .pop();
    const nodes = [
      { type: 'inspection', label: '3个月点检', date: this.addMonths(lastShaken.iso, 3) },
      { type: 'inspection', label: '3个月点检', date: this.addMonths(lastShaken.iso, 6) },
      { type: 'inspection', label: '3个月点检', date: this.addMonths(lastShaken.iso, 9) },
      { type: 'vehicle', label: '车检', date: nextShaken || this.addMonths(lastShaken.iso, 12) }
    ]
      .filter((item) => item.date)
      .sort((a, b) => String(a.date.iso).localeCompare(String(b.date.iso)));
    const shakenNode = nodes.find((item) => item.type === 'vehicle');
    const shakenDays = shakenNode ? this.daysUntil(shakenNode.date.iso) : null;
    if (shakenNode && shakenDays !== null && shakenDays <= VEHICLE_REMINDER_DAYS) return shakenNode;
    const pendingNodes = nodes.filter((item) => !completedIso || item.date.iso > completedIso);
    const overdueNodes = pendingNodes
      .map((item) => ({ ...item, days: this.daysUntil(item.date.iso) }))
      .filter((item) => item.days !== null && item.days < 0)
      .sort((a, b) => String(b.date.iso).localeCompare(String(a.date.iso)));
    if (overdueNodes.length) {
      const node = overdueNodes[0];
      return { type: node.type, label: node.label, date: node.date };
    }
    const next = pendingNodes.find((item) => {
      const days = this.daysUntil(item.date.iso);
      return days === null || days <= VEHICLE_REMINDER_DAYS;
    }) || pendingNodes[0];
    if (next) return next;
    const nextCycleBase = nextShaken || lastShaken;
    return { type: 'inspection', label: '3个月点检', date: this.addMonths(nextCycleBase.iso, 3) };
  },

  addDays(dateText, days) {
    if (!dateText) return '';
    const date = new Date(`${dateText}T00:00:00`);
    if (Number.isNaN(date.getTime())) return '';
    date.setDate(date.getDate() + days);
    return this.formatDate(date);
  },

  formatDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  }
});
