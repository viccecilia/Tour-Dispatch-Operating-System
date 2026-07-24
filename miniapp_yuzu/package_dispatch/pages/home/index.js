const api = require('../../utils/api');

const HOME_HIDDEN_RESOURCE_VEHICLE_TAILS = ['7721', '3724', '7728'];
const RESOURCE_VEHICLE_REMINDER_DAYS = 30;
const RESOURCE_DRIVER_HEALTH_REMINDER_DAYS = 30;
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

const HOME_TITLE_BY_ROLE = {
  admin: '管理首页',
  dispatcher: '调度首页',
  operations_manager: '运管首页',
  driver: '司机首页'
};

Page({
  data: {
    username: '',
    password: '',
    session: null,
    roleLabel: '',
    heroName: '统一账号登录',
    heroMeta: '调度 / 管理 / 司机 / 运行管理统一入口',
    statusLabel: '未出库',
    statusHint: '确认接单后进入任务页完成出库。',
    canDispatch: false,
    canFinance: false,
    canDriverTasks: false,
    isOperationsManager: false,
    isDriverTheme: false,
    canViewDriverWorkload: false,
    operationsStatus: { label: '运行监控中', hint: '车辆点检、车检、司机证件和今日任务异常会在这里汇总。', tone: 'normal' },
    operationsOverview: {
      taskTotal: 0,
      taskActive: 0,
      taskPending: 0,
      taskCompleted: 0,
      vehicleTotal: 0,
      vehicleAvailable: 0,
      vehicleMaintenance: 0,
      vehicleRetired: 0,
      driverTotal: 0,
      driverHealthDue: 0,
      driverLicenseDue: 0,
      driverDueTotal: 0,
      attendanceWarnings: 0
    },
    operationsRows: [],
    operationsTaskRows: [],
    operationsVehicleRows: [],
    operationsDriverRows: [],
    operationsAttendanceRows: [],
    operationsSection: 'tasks',
    operationsDetailTitle: '司机任务',
    operationsDetailHint: '查看今日全部司机任务、执行状态和车辆分配。',
    operationsDetailRows: [],
    operationsDetailUnit: '条',
    dashboard: { counts: {}, latest_orders: [], fleet_status: {} },
    driverAssignments: [],
    panelMode: 'orders',
    panelTitle: '今日订单',
    panelHint: '点击订单进入任务页处理。',
    panelUnit: '条',
    panelRows: [],
    driverOrderChipLabel: '今日订单',
    driverOrderChipCount: 0,
    allOrderChipCount: 0,
    driverOrderChipAlert: false,
    driverStats: [],
    visibleDriverStats: [],
    pressureExpanded: false,
    notifications: [],
    unassignedRows: [],
    dispatchAllRows: [],
    dispatchOverview: {
      todayAssigned: 0,
      todayActive: 0,
      todayTotal: 0,
      unassignedToday: 0,
      driverTotal: 0,
      vehicleTotal: 0,
      idleDrivers: 0,
      idleVehicles: 0,
      hiaceTotal: 0,
      idleHiace: 0,
      alphardTotal: 0,
      idleAlphard: 0,
      vehicleTypeRows: []
    },
    resourceSummary: {
      vehicleTotal: 0,
      driverTotal: 0,
      pdfTotal: 0,
      categoryTotal: 0,
      vehicleInspectionDue: 0,
      threeMonthDue: 0,
      healthDue: 0,
      licenseDue: 0,
      residenceDue: 0,
      alertTotal: 0
    },
    resourceVehicleAlerts: [],
    resourceInspectionAlerts: [],
    resourceHealthAlerts: [],
    resourceLicenseAlerts: [],
    resourceResidenceAlerts: [],
    resourceAlertRows: [],
    visibleResourceAlertRows: [],
    resourceAlertFilter: 'all',
    resourceAllVehicleRows: [],
    resourceAllDriverRows: [],
    resourceVehicleRows: [],
    resourceDriverRows: [],
    resourcePdfRows: [],
    resourceError: '',
    resourceFocus: 'alerts',
    resourceOfficeFilter: 'all',
    driverStatusLabels: ['出勤', '休假', '离职'],
    driverStatusValues: ['available', 'resting', 'retired'],
    officeFilters: [
      { label: '全部', value: 'all' },
      { label: '大阪', value: 'osaka' },
      { label: '京都', value: 'kyoto' }
    ],
    resourceExpandedSection: '',
    expandedHomeVehicleId: '',
    expandedHomeDriverId: '',
    dispatchTaskRows: [],
    idleDriverRows: [],
    idleVehicleRows: [],
    vehicleIdleTypeRows: [],
    error: '',
    loading: false,
    autoLoginTried: false,
    wechatAutoLoginEnabled: false,
    wechatBindingRequired: false,
    pendingPromptKey: ''
  },

  onShow() {
    api.syncEnvironmentBaseUrl();
    api.setActiveTab('/package_dispatch/pages/home/index');
    const session = api.getSession();
    this.setSessionState(session);
    this.refreshTabBar();
    if (this.data.session) {
      console.info('[dispatch home session]', {
        baseUrl: api.getBaseUrl(),
        role: api.getRole(this.data.session),
        hasToken: !!(this.data.session && this.data.session.token)
      });
      this.loadDashboard();
      return;
    }
    console.warn('[dispatch home missing session]', {
      baseUrl: api.getBaseUrl(),
      hasUnified: !!wx.getStorageSync('yuzu_session'),
      hasDispatch: !!wx.getStorageSync(`dispatcher_session:${api.getBaseUrl()}`),
      hasDispatchPlain: !!wx.getStorageSync('dispatcher_session')
    });
    wx.setStorageSync('yuzu_selected_port', 'dispatch');
    wx.reLaunch({ url: '/pages/login/index?port=dispatch' });
  },

  loadLoginMode() {
    this.setData({ loading: true, error: '' });
    api.appConfig()
      .then((config) => {
        const settings = (config && config.settings) || config || {};
        console.info('[dispatch-mobile app-config]', settings);
        this.setData({
          wechatAutoLoginEnabled: !!settings.wechat_auto_login_enabled,
          wechatBindingRequired: !!settings.wechat_binding_required
        });
        if (api.isManualLogout && api.isManualLogout()) {
          this.setData({ loading: false, autoLoginTried: true });
          return;
        }
        if (settings.wechat_auto_login_enabled) {
          this.setData({ loading: false });
          this.tryWechatAutoLogin();
          return;
        }
        this.setData({ loading: false });
      })
      .catch((err) => {
        console.warn('[dispatch-mobile app-config failed]', err);
        this.setData({ loading: false });
      });
  },

  tryWechatAutoLogin() {
    if (this.data.autoLoginTried) return;
    this.setData({ autoLoginTried: true, loading: true, error: '' });
    this.getWechatLoginCode()
      .catch((err) => {
        if (api.isLocalBaseUrl && api.isLocalBaseUrl()) return '';
        return Promise.reject(err);
      })
      .then((wxCode) => api.loginWechat(wxCode))
      .then((res) => {
        api.setSession(res);
        this.setSessionState(res);
        this.setData({ loading: false });
        this.refreshTabBar();
        return this.loadDashboard();
      })
      .catch(() => this.setData({ loading: false }));
  },

  setSessionState(session) {
    const role = api.getRole(session);
    const labels = { admin: '管理', dispatcher: '调度', operations_manager: '运行管理', driver: '司机' };
    const dispatcher = (session && session.dispatcher) || {};
    const user = (session && session.user) || {};
    const heroName = dispatcher.dispatcher_name || user.name || user.username || '统一账号登录';
    const heroCode = dispatcher.dispatcher_code || user.account_code || user.code || '';
    const roleLabel = labels[role] || '账号';
    const heroMeta = session ? [heroCode, roleLabel].filter(Boolean).join(' - ') : '调度 / 管理 / 司机 / 运行管理统一入口';
    wx.setNavigationBarTitle({ title: HOME_TITLE_BY_ROLE[role] || '首页' });
    this.setData({
      session,
      roleLabel,
      heroName,
      heroMeta,
      canDispatch: api.canAccess('dispatch', session),
      canFinance: api.canAccess('finance', session),
      canDriverTasks: role === 'driver',
      isOperationsManager: role === 'operations_manager',
      isDriverTheme: role === 'driver',
      canViewDriverWorkload: ['admin', 'dispatcher'].indexOf(role) >= 0
    });
  },

  refreshTabBar() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) this.getTabBar().refresh();
  },

  onUsername(e) {
    this.setData({ username: e.detail.value });
  },

  onPassword(e) {
    this.setData({ password: e.detail.value });
  },

  login() {
    this.setData({ loading: true, error: '' });
    const account = String(this.data.username || '').trim();
    const password = String(this.data.password || '');
    const isPhone = /^\+?[\d\s-]{6,}$/.test(account) || /^[A-Za-z0-9]+-[\d\s-]{6,}$/.test(account);
    const loginWithCode = this.data.wechatAutoLoginEnabled || this.data.wechatBindingRequired;
    const codeTask = loginWithCode ? this.getWechatLoginCode().catch(() => '') : Promise.resolve('');
    codeTask
      .then((wxCode) => (isPhone ? api.loginPhone(account, password, wxCode) : api.login(account, password, wxCode)))
      .catch(() => (isPhone ? api.loginPhone(account.replace(/[^\d]/g, ''), password, '') : Promise.reject({ error: 'login_failed' })))
      .then((res) => {
        api.setSession(res);
        this.setSessionState(res);
        this.setData({ loading: false });
        this.refreshTabBar();
        return this.loadDashboard();
      })
      .catch((err) => {
        const error = err && err.error === 'wechat_binding_mismatch'
          ? '该账号已绑定其他微信，请联系管理员解除绑定。'
          : err && err.error === 'wechat_code_exchange_unavailable'
            ? '微信绑定未配置，请先在云端配置小程序 AppSecret。'
            : '登录失败，请检查账号密码或后端服务。';
        this.setData({ loading: false, error });
      });
  },

  getWechatLoginCode() {
    return new Promise((resolve, reject) => {
      wx.login({
        success: (res) => (res.code ? resolve(res.code) : reject({ error: 'wechat_login_failed' })),
        fail: () => reject({ error: 'wechat_login_failed' })
      });
    });
  },

  loadDashboard() {
    this.setData({ loading: true, error: '' });
    const emptyDashboard = { counts: {}, latest_orders: [], fleet_status: {} };
    const canViewDriverWorkload = this.data.canViewDriverWorkload;
    const session = this.data.session || {};
    const role = api.getRole(session);
    const canViewOperations = role === 'operations_manager';
    const canViewResources = role !== 'driver';
    const driverId = session.user && session.user.profile_id ? session.user.profile_id : 0;
    const notificationTask = role === 'driver' && driverId
      ? api.driverNotifications(driverId).catch(() => ({ notifications: [] }))
      : api.notifications().catch(() => ({ notifications: [] }));
    const driverTask = role === 'driver' && driverId
      ? api.driverAssignments(driverId).catch(() => ({ assignments: [] }))
      : Promise.resolve({ assignments: [] });
    const workbenchTask = role === 'driver' && driverId
      ? api.driverWorkbench(driverId).catch(() => ({}))
      : Promise.resolve({});
    const profileTask = role === 'driver' && driverId
      ? api.driverProfile(driverId).catch(() => ({ driver: null }))
      : Promise.resolve({ driver: null });
    const vehicleTask = (canViewOperations || this.data.canDispatch)
      ? api.vehicles().catch(() => ({ vehicles: [] }))
      : Promise.resolve({ vehicles: [] });
    const unassignedTask = this.data.canDispatch
      ? api.unassignedOrders().catch(() => ({ orders: [] }))
      : Promise.resolve({ orders: [] });
    const dispatchDraftTask = this.data.canDispatch
      ? api.drafts().catch(() => ({ drafts: [] }))
      : Promise.resolve({ drafts: [] });
    const resourceTask = canViewResources
      ? api.resourceLibrary()
        .then((library) => {
          const summary = (library && library.summary) || {};
          console.info('[dispatch resource library loaded]', {
            vehicles: Array.isArray(library && library.vehicles) ? library.vehicles.length : 0,
            drivers: Array.isArray(library && library.drivers) ? library.drivers.length : 0,
            pdf: summary.pdf_files || summary.pdfTotal || 0
          });
          return library;
        })
        .catch((err) => {
          console.warn('[dispatch resource library failed]', err);
          return { vehicles: [], drivers: [], summary: {}, resourceError: err && (err.error || err.detail || err.errMsg) || 'resource_failed' };
        })
      : Promise.resolve({ vehicles: [], drivers: [], summary: {} });

    return Promise.all([
      api.dashboard().catch((err) => {
        console.warn('[dispatch-mobile dashboard failed]', err);
        return emptyDashboard;
      }),
      notificationTask,
      (canViewDriverWorkload || canViewOperations) ? api.assignments().catch(() => ({ assignments: [] })) : Promise.resolve({ assignments: [] }),
      (canViewDriverWorkload || canViewOperations) ? api.drivers().catch(() => ({ drivers: [] })) : Promise.resolve({ drivers: [] }),
      driverTask,
      workbenchTask,
      profileTask,
      vehicleTask,
      unassignedTask,
      dispatchDraftTask,
      resourceTask
    ])
      .then((results) => {
        const dashboard = results && results[0];
        const notifications = results && results[1];
        const assignments = results && results[2];
        const drivers = results && results[3];
        const driverAssignments = results && results[4];
        const workbench = results && results[5];
        const profile = results && results[6];
        const vehicles = results && results[7];
        const unassigned = results && results[8];
        const dispatchDrafts = results && results[9];
        const resourceLibrary = results && results[10];
        const safeDashboard = dashboard || emptyDashboard;
        const allAssignments = Array.isArray(assignments && assignments.assignments) ? assignments.assignments : [];
        const allDrivers = Array.isArray(drivers && drivers.drivers) ? drivers.drivers : [];
        const allVehicles = Array.isArray(vehicles && vehicles.vehicles) ? vehicles.vehicles : [];
        const tenantId = this.currentTenantId();
        const draftRows = (Array.isArray(dispatchDrafts && dispatchDrafts.drafts) ? dispatchDrafts.drafts : [])
          .filter((item) => !tenantId || !item.tenant_id || Number(item.tenant_id) === tenantId)
          .filter((item) => item.parse_status !== 'confirmed' && item.parse_status !== 'discarded')
          .map((item) => this.decorateUnassignedOrder(Object.assign({}, item, { kind: 'draft' })));
        const orderRows = (Array.isArray(unassigned && unassigned.orders) ? unassigned.orders : [])
          .filter((item) => !tenantId || !item.tenant_id || Number(item.tenant_id) === tenantId)
          .map((item) => this.decorateUnassignedOrder(Object.assign({}, item, { kind: 'order' })));
        const unassignedRows = this.sortDispatchRows(draftRows.concat(orderRows)).slice(0, 160);
        const driverStats = canViewDriverWorkload ? this.buildDriverStats(allAssignments, allDrivers) : [];
        const assignmentSourceRows = Array.isArray(driverAssignments && driverAssignments.assignments) ? driverAssignments.assignments : [];
        const workbenchPendingRows = Array.isArray(workbench && workbench.pending_assignments) ? workbench.pending_assignments : [];
        const driverRows = this.mergeDriverAssignments(assignmentSourceRows, workbenchPendingRows)
          .map((item) => this.decorateAssignment(item));
        const today = this.formatDate(new Date());
        const dispatchAssignments = allAssignments
          .filter((item) => !tenantId || !item.tenant_id || Number(item.tenant_id) === tenantId)
          .map((item) => this.decorateAssignment(item));
        const dispatchAllRows = this.sortDispatchRows(dispatchAssignments.concat(unassignedRows)).slice(0, 220);
        const pendingRows = driverRows.filter((item) => item.rawStatus === 'assigned');
        const todayRows = driverRows.filter((item) => this.isAssignmentOnDate(item, today));
        const exceptionRows = driverRows.filter((item) => ['incident', 'exception', 'delayed'].indexOf(String(item.order_status || item.status || '')) >= 0);
        const resourceOverview = this.buildResourceOverview(resourceLibrary || {}, allDrivers, allVehicles);
        const visibleResourceAlertRows = this.filterResourceAlertRows(
          resourceOverview.alertRows,
          this.data.resourceAlertFilter
        );
        const filteredResourceRows = this.filterResourceRowsByOffice(resourceOverview.vehicleRows, resourceOverview.driverRows, this.data.resourceOfficeFilter);
        const availabilityDrivers = allDrivers.length ? allDrivers : this.resourceDriversForAvailability(resourceOverview.driverRows);
        const availabilityVehicles = allVehicles.length ? allVehicles : this.resourceVehiclesForAvailability(resourceOverview.vehicleRows);
        const todayDispatchRows = dispatchAssignments.filter((item) => this.isAssignmentOnDate(item, today));
        const dispatchOverview = this.buildDispatchOverview(todayDispatchRows, availabilityDrivers, availabilityVehicles, unassignedRows);
        const idleResources = this.buildIdleResources(todayDispatchRows, availabilityDrivers, availabilityVehicles);
        const dueRows = this.buildDueRows(profile.driver);
        const notificationRows = (Array.isArray(notifications && notifications.notifications) ? notifications.notifications : [])
          .filter((item) => !this.isSuppressedDriverNotification(item))
          .slice(0, 30)
          .map((item) => this.decorateNotification(item));
        const unreadRows = notificationRows.filter((item) => item.rawStatus !== 'read');
        const nextDashboard = Object.assign({}, safeDashboard, {
          counts: Object.assign({}, safeDashboard.counts || {})
        });
        if (role === 'driver') {
          nextDashboard.counts.today_orders = todayRows.length;
          nextDashboard.counts.pending_confirmations = pendingRows.length;
          nextDashboard.counts.exception_orders = exceptionRows.length;
          nextDashboard.counts.notifications_unread = unreadRows.length;
          nextDashboard.counts.notifications_total = notificationRows.length;
        }
        if (this.data.canDispatch) {
          nextDashboard.counts.unassigned_orders = unassignedRows.length;
          nextDashboard.counts.notifications_unread = unreadRows.length;
          nextDashboard.counts.notifications_total = notificationRows.length;
        }
        const status = this.computeDriverStatus(driverRows, workbench);
        const operations = role === 'operations_manager'
          ? this.buildOperationsDashboard(nextDashboard, allAssignments, allDrivers, allVehicles)
          : {
            status: this.data.operationsStatus,
            overview: this.data.operationsOverview,
            rows: this.data.operationsRows,
            taskRows: this.data.operationsTaskRows,
            vehicleRows: this.data.operationsVehicleRows,
            driverRows: this.data.operationsDriverRows,
            attendanceRows: this.data.operationsAttendanceRows,
            detail: this.buildOperationsDetail(
              this.data.operationsSection,
              this.data.operationsTaskRows,
              this.data.operationsVehicleRows,
              this.data.operationsDriverRows,
              this.data.operationsAttendanceRows
            )
          };
        const preferredPanelMode = !this.data.canDispatch && pendingRows.length && this.data.panelMode === 'orders'
          ? 'pending'
          : this.data.panelMode;
        const panel = this.data.canDispatch
          ? this.buildDispatchPanel(this.data.panelMode, unassignedRows, unreadRows, dispatchAllRows, driverStats, resourceOverview.alertRows)
          : this.buildPanel(preferredPanelMode, todayRows, driverRows, pendingRows, exceptionRows, unreadRows);
        const operationsDetail = role === 'operations_manager' && this.data.operationsSection === 'notifications'
          ? this.buildOperationsNotificationDetail(notificationRows)
          : operations.detail;
        this.setData({
          dashboard: nextDashboard,
          driverAssignments: driverRows,
          panelMode: preferredPanelMode,
          unassignedRows,
          dispatchAllRows,
          driverOrderChipLabel: this.data.canDispatch ? '待委派订单' : (pendingRows.length ? '待确认派单' : '今日订单'),
          driverOrderChipCount: this.data.canDispatch ? unassignedRows.length : (pendingRows.length || todayRows.length),
          allOrderChipCount: this.data.canDispatch ? dispatchAllRows.length : driverRows.length,
          driverOrderChipAlert: false,
          notifications: notificationRows,
          statusLabel: status.label,
          statusHint: status.hint,
          operationsStatus: operations.status,
          operationsOverview: operations.overview,
          operationsRows: operations.rows,
          operationsTaskRows: operations.taskRows,
          operationsVehicleRows: operations.vehicleRows,
          operationsDriverRows: operations.driverRows,
          operationsAttendanceRows: operations.attendanceRows,
          operationsDetailTitle: operationsDetail.title,
          operationsDetailHint: operationsDetail.hint,
          operationsDetailRows: operationsDetail.rows,
          operationsDetailUnit: operationsDetail.unit,
          panelTitle: panel.title,
          panelHint: panel.hint,
          panelUnit: panel.unit || '条',
          panelRows: panel.rows,
          driverStats,
          visibleDriverStats: this.visibleDriverStats(driverStats, this.data.pressureExpanded),
          dispatchOverview,
          resourceSummary: resourceOverview.summary,
          resourceVehicleAlerts: resourceOverview.vehicleInspectionAlerts,
          resourceInspectionAlerts: resourceOverview.threeMonthAlerts,
          resourceHealthAlerts: resourceOverview.healthAlerts,
          resourceLicenseAlerts: resourceOverview.licenseAlerts,
          resourceResidenceAlerts: resourceOverview.residenceAlerts,
          resourceAlertRows: resourceOverview.alertRows,
          visibleResourceAlertRows,
          resourceAllVehicleRows: resourceOverview.vehicleRows,
          resourceAllDriverRows: resourceOverview.driverRows,
          resourceVehicleRows: filteredResourceRows.vehicles,
          resourceDriverRows: filteredResourceRows.drivers,
          resourcePdfRows: resourceOverview.pdfRows,
          resourceError: resourceOverview.error,
          vehicleIdleTypeRows: dispatchOverview.vehicleTypeRows || [],
          dispatchTaskRows: todayDispatchRows.slice(0, 8),
          idleDriverRows: idleResources.idleDriverRows,
          idleVehicleRows: idleResources.idleVehicleRows,
          loading: false
        });
        if (role !== 'driver') this.refreshResourceOverview();
        this.promptPendingAssignments(role, pendingRows);
      })
      .catch((err) => {
        console.error('[dispatch home load failed]', err);
        this.setData({ loading: false, error: '无法加载移动首页。' });
      });
  },

  promptPendingAssignments(role, pendingRows) {
    if (role !== 'driver') return;
    if (!pendingRows.length) {
      if (this.data.pendingPromptKey) this.setData({ pendingPromptKey: '' });
      return;
    }
    if (this.data.pendingPromptKey === 'active') return;
    this.setData({ pendingPromptKey: 'active' });
    wx.showModal({
      title: '待确认派单',
      content: `你有 ${pendingRows.length} 个待确认派单，请在首页列表中逐单确认。`,
      showCancel: false,
      confirmText: '知道了'
    });
  },

  buildOperationsDashboard(dashboard, assignments, drivers, vehicles) {
    const counts = dashboard.counts || {};
    const fleetStatus = dashboard.fleet_status || counts.vehicle_status || {};
    const today = this.formatDate(new Date());
    const todayAssignments = assignments.filter((item) => (item.order_date || '').slice(0, 10) === today);
    const activeStatuses = ['departed', 'arrived', 'in_service'];
    const completedStatuses = ['completed', 'returned'];
    const activeTasks = todayAssignments.filter((item) => activeStatuses.indexOf(String(item.execution_status || item.status || '')) >= 0);
    const completedTasks = todayAssignments.filter((item) => completedStatuses.indexOf(String(item.execution_status || item.status || '')) >= 0);
    const pendingTasks = todayAssignments.filter((item) => String(item.execution_status || item.status || '') === 'assigned');
    const healthDue = drivers.filter((driver) => {
      const days = this.daysUntil(driver.health_check_due_date || driver.health_check_date);
      return days !== null && days <= 30;
    });
    const licenseDue = drivers.filter((driver) => {
      const days = this.daysUntil(driver.license_due_date || driver.license_expiry_date);
      return days !== null && days <= 30;
    });
    const vehicleCounts = this.countVehicleStatuses(vehicles);
    const maintenanceVehicles = vehicleCounts.maintenance || Number(fleetStatus.maintenance || fleetStatus.repair || fleetStatus.in_maintenance || 0);
    const retiredVehicles = vehicleCounts.retired || Number(fleetStatus.retired || fleetStatus.removed || 0);
    const alertCount = Number(counts.resource_alerts || 0)
      + Number(counts.exception_orders || counts.incident_orders || 0)
      + healthDue.length
      + licenseDue.length
      + maintenanceVehicles;
    const status = alertCount > 0
      ? { label: '有预警', hint: '请优先确认车辆到期、司机证件和今日任务异常。', tone: 'warning' }
      : { label: '正常', hint: '今日车辆、司机资料和任务暂无明显风险。', tone: 'normal' };
    const rows = [
      {
        id: 'ops-tasks',
        title: '全部司机今日任务',
        meta: `今日 ${todayAssignments.length} 单 · 执行中 ${activeTasks.length} · 待执行 ${pendingTasks.length}`,
        body: this.sampleAssignmentText(todayAssignments),
        priority: activeTasks.length || pendingTasks.length ? 'normal' : 'low',
        action: 'map',
        actionText: '地图'
      },
      {
        id: 'ops-vehicles',
        title: '所有车辆状态',
        meta: `正常 ${vehicleCounts.available || Number(fleetStatus.available || 0)} · 维修 ${maintenanceVehicles} · 减车 ${retiredVehicles}`,
        body: '维修车辆可派车但需提示；减车车辆不进入可派列表。',
        priority: maintenanceVehicles || retiredVehicles ? 'high' : 'low',
        action: 'map',
        actionText: '查看'
      },
      {
        id: 'ops-drivers',
        title: '所有司机资料',
        meta: `司机 ${drivers.length} 人 · 体检预警 ${healthDue.length} · 驾照预警 ${licenseDue.length}`,
        body: this.sampleDriverDueText(healthDue, licenseDue),
        priority: healthDue.length || licenseDue.length ? 'high' : 'low',
        action: 'profile',
        actionText: '资料'
      },
      {
        id: 'ops-attendance',
        title: '今日出勤状态',
        meta: `已完成 ${completedTasks.length} · 运行中 ${activeTasks.length} · 待执行 ${pendingTasks.length}`,
        body: '出勤台账包含睡眠、出库点呼、出入库、休息申报和拘束时间。',
        priority: Number(counts.unreported_assignments || 0) ? 'high' : 'normal',
        action: 'detail',
        actionText: '详情'
      }
    ];
    const taskRows = todayAssignments
      .slice()
      .sort((a, b) => `${a.start_time || ''}`.localeCompare(`${b.start_time || ''}`))
      .map((item) => ({
        id: item.assignment_id || item.id,
        title: `${item.start_time || '--:--'} ${item.driver_name || '未定司机'}`,
        meta: `${item.plate_number || '未定车辆'} · ${this.statusText(item.execution_status || item.status)}`,
        body: `${item.pickup_location || '-'} -> ${item.dropoff_location || '-'}`
      }));
    const vehicleRows = (vehicles || []).map((vehicle) => ({
      id: vehicle.id || vehicle.plate_number,
      title: vehicle.plate_number || '-',
      meta: `${vehicle.vehicle_type || '-'} · ${this.vehicleStatusText(vehicle.status || vehicle.vehicle_status)}`,
      body: vehicle.maintenance_note || vehicle.repair_note || vehicle.remark || '车辆资料可查询',
      details: [
        this.detailLine('三个月点检', vehicle.latest_inspection_date || vehicle.last_inspection_date || vehicle.inspection_date),
        this.detailLine('点检到期', vehicle.inspection_due_date || vehicle.next_inspection_date),
        this.detailLine('年检到期', vehicle.vehicle_inspection_due_date || vehicle.shaken_due_date || vehicle.vehicle_check_due_date),
        this.detailLine('轮胎/颜色', [vehicle.tire_type || vehicle.snow_tire, vehicle.color].filter(Boolean).join(' / ')),
        this.detailLine('维修说明', vehicle.maintenance_note || vehicle.repair_note || vehicle.remark)
      ].filter(Boolean)
    }));
    const visibleDrivers = (drivers || []).filter((driver) => !this.isHiddenDriver(driver));
    const driverRows = visibleDrivers.map((driver) => {
      const healthDays = this.daysUntil(driver.health_check_due_date || driver.health_check_date);
      const licenseDays = this.daysUntil(driver.license_due_date || driver.license_expiry_date);
      return {
        id: driver.id,
        title: driver.name || driver.driver_name || '-',
        meta: `${driver.phone || driver.mobile || '-'} · ${driver.driver_code || driver.code || '-'}`,
        body: `体检 ${this.dueText(healthDays)} · 驾照 ${this.dueText(licenseDays)}`,
        details: [
          this.detailLine('所属营业所', driver.office || driver.branch || driver.sales_office),
          this.detailLine('手机号', driver.phone || driver.mobile),
          this.detailLine('微信/LINE', [driver.wechat, driver.line].filter(Boolean).join(' / ')),
          this.detailLine('WhatsApp/Kakao', [driver.whatsapp, driver.kakao].filter(Boolean).join(' / ')),
          this.detailLine('邮箱', driver.mail || driver.email),
          this.detailLine('健康体检日', driver.health_check_date),
          this.detailLine('健康体检到期', driver.health_check_due_date),
          this.detailLine('驾照到期', driver.license_due_date || driver.license_expiry_date),
          this.detailLine('在留到期', driver.residence_due_date || driver.residence_expiry_date)
        ].filter(Boolean)
      };
    });
    const attendanceRows = todayAssignments
      .slice()
      .sort((a, b) => `${a.driver_name || ''}${a.start_time || ''}`.localeCompare(`${b.driver_name || ''}${b.start_time || ''}`))
      .map((item) => ({
        id: `attendance-${item.assignment_id || item.id}`,
        title: item.driver_name || '未定司机',
        meta: `${item.plate_number || '未定车辆'} · ${this.statusText(item.execution_status || item.status)}`,
        body: `${item.start_time || '--:--'} ${item.pickup_location || '-'} -> ${item.dropoff_location || '-'}`,
        details: [
          this.detailLine('订单号', item.oid || item.order_id),
          this.detailLine('出库时间', item.departure_time || item.vehicle_out_time || item.checkout_time),
          this.detailLine('入库时间', item.return_time || item.vehicle_in_time || item.checkin_time),
          this.detailLine('休息时间', item.rest_time || item.break_time),
          this.detailLine('睡眠申报', item.sleep_hours || item.sleep_time)
        ].filter(Boolean)
      }));
    const detail = this.buildOperationsDetail(this.data.operationsSection, taskRows, vehicleRows, driverRows, attendanceRows);
    return {
      status,
      overview: {
        taskTotal: todayAssignments.length,
        taskActive: activeTasks.length,
        taskPending: pendingTasks.length,
        taskCompleted: completedTasks.length,
        vehicleTotal: vehicles.length || Number(counts.available_vehicles || 0) + Number(counts.outbound_vehicles || 0) + Number(counts.in_service_vehicles || 0) + Number(counts.returned_vehicles || 0) + maintenanceVehicles + retiredVehicles,
        vehicleAvailable: vehicleCounts.available || Number(fleetStatus.available || counts.available_vehicles || 0),
        vehicleMaintenance: maintenanceVehicles,
        vehicleRetired: retiredVehicles,
        driverTotal: visibleDrivers.length,
        driverHealthDue: healthDue.length,
        driverLicenseDue: licenseDue.length,
        driverDueTotal: healthDue.length + licenseDue.length,
        attendanceWarnings: Number(counts.unreported_assignments || 0)
      },
      rows,
      taskRows,
      vehicleRows,
      driverRows,
      attendanceRows,
      detail
    };
  },

  detailLine(label, value) {
    const text = value === undefined || value === null ? '' : String(value).trim();
    if (!text || text === '-') return null;
    return { label, value: text };
  },

  buildOperationsDetail(section, taskRows, vehicleRows, driverRows, attendanceRows) {
    const config = {
      tasks: {
        title: '司机任务',
        hint: '查看今日全部司机任务、执行状态和车辆分配。',
        unit: '条',
        rows: taskRows || []
      },
      vehicles: {
        title: '车辆状态',
        hint: '查看车辆状态、3 个月点检、年检到期、轮胎和维修说明。',
        unit: '台',
        rows: vehicleRows || []
      },
      drivers: {
        title: '司机资料',
        hint: '查看司机联系方式、健康体检、驾照和在留期限基础资料。',
        unit: '人',
        rows: driverRows || []
      },
      attendance: {
        title: '今日出勤状态',
        hint: '查看今日车辆和人员出勤、睡眠、点呼、出入库和休息申报。',
        unit: '条',
        rows: attendanceRows || []
      }
    };
    return config[section] || config.tasks;
  },
  dueText(days) {
    if (days === null) return '未登记';
    if (days < 0) return `过期 ${Math.abs(days)} 天`;
    return `剩余 ${days} 天`;
  },

  vehicleStatusText(status) {
    const raw = String(status || '').toLowerCase();
    if (raw.indexOf('retired') >= 0 || raw.indexOf('removed') >= 0 || raw.indexOf('减车') >= 0) return '减车';
    if (raw.indexOf('maintenance') >= 0 || raw.indexOf('repair') >= 0 || raw.indexOf('维修') >= 0) return '维修';
    return '正常';
  },

  countVehicleStatuses(vehicles) {
    return (vehicles || []).reduce((acc, vehicle) => {
      const status = String(vehicle.status || vehicle.vehicle_status || '').toLowerCase();
      if (status.indexOf('retired') >= 0 || status.indexOf('removed') >= 0 || status.indexOf('减车') >= 0) {
        acc.retired += 1;
      } else if (status.indexOf('maintenance') >= 0 || status.indexOf('repair') >= 0 || status.indexOf('维修') >= 0) {
        acc.maintenance += 1;
      } else {
        acc.available += 1;
      }
      return acc;
    }, { available: 0, maintenance: 0, retired: 0 });
  },

  sampleAssignmentText(assignments) {
    const sample = assignments.slice(0, 2).map((item) => `${item.driver_name || '-'} ${item.start_time || '--:--'} ${item.pickup_location || '-'} -> ${item.dropoff_location || '-'}`);
    return sample.length ? sample.join('\n') : '今日暂无司机任务。';
  },

  sampleDriverDueText(healthDue, licenseDue) {
    const health = healthDue[0] ? `体检：${healthDue[0].name || healthDue[0].driver_name || '-'} ${healthDue[0].health_check_due_date || healthDue[0].health_check_date || '-'}` : '';
    const license = licenseDue[0] ? `驾照：${licenseDue[0].name || licenseDue[0].driver_name || '-'} ${licenseDue[0].license_due_date || licenseDue[0].license_expiry_date || '-'}` : '';
    return [health, license].filter(Boolean).join('\n') || '司机资料暂无 30 天内到期项。';
  },

  decorateAssignment(item) {
    const rawStatus = item.execution_status || item.status || 'assigned';
    const guestBits = [];
    if (item.guest_name) guestBits.push(item.guest_name);
    if (item.guest_contact) {
      const region = this.detectPhoneRegion(item.guest_contact);
      guestBits.push(region ? `${item.guest_contact}（${region}）` : item.guest_contact);
    }
    if (item.passenger_count) guestBits.push(`${item.passenger_count}位`);
    if (item.luggage_count || item.luggage_count === 0) guestBits.push(`行李 ${item.luggage_count}`);
    const resourceBits = [item.driver_name || '未定司机', item.plate_number || '未定车辆'].filter(Boolean);
    const remark = String(item.remark || '').trim();
    const timeRangeText = this.assignmentTimeText(item);
    const routeText = this.assignmentRouteText(item);
    const orderNoText = item.oid || item.order_id || '订单';
    return Object.assign({}, item, {
      rawStatus,
      id: item.assignment_id || item.id,
      title: timeRangeText,
      meta: this.statusText(rawStatus),
      body: routeText,
      orderNoText,
      timeRangeText,
      routeText,
      guestLine: guestBits.join(' · '),
      resourceLine: resourceBits.join(' · '),
      remarkPreview: remark ? remark.slice(0, 60) : '',
      action: rawStatus === 'assigned' ? 'confirm' : 'task',
      actionText: rawStatus === 'assigned' ? '确认' : '查看'
    });
  },

  assignmentTimeText(item) {
    const startDate = item.order_date || item.start_date || '-';
    const startTime = item.start_time || '--:--';
    const endDate = item.end_date || '';
    const endTime = item.end_time || '';
    const startText = `${startDate} ${startTime}`;
    if (!endTime) return startText;
    if (endDate && endDate !== startDate) return `${startText} - ${endDate} ${endTime}`;
    return `${startText} - ${endTime}`;
  },

  assignmentRouteText(item) {
    return `${item.pickup_location || '-'} → ${item.dropoff_location || '-'}`;
  },

  mergeDriverAssignments(primaryRows, pendingRows) {
    const merged = [];
    const seen = {};
    (primaryRows || []).concat(pendingRows || []).forEach((item) => {
      const key = String(item.assignment_id || item.id || item.order_id || `${item.order_date}-${item.start_time}-${item.oid}`);
      if (!key || seen[key]) return;
      seen[key] = true;
      merged.push(item);
    });
    return merged.sort((a, b) => {
      const left = `${a.order_date || ''} ${a.start_time || ''} ${a.assignment_id || a.id || ''}`;
      const right = `${b.order_date || ''} ${b.start_time || ''} ${b.assignment_id || b.id || ''}`;
      return left.localeCompare(right, 'zh-Hans-CN');
    });
  },

  buildDispatchOverview(assignments, drivers, vehicles, unassignedRows) {
    const today = this.formatDate(new Date());
    const activeStatuses = ['departed', 'arrived', 'in_service'];
    const activeAssignments = (assignments || []).filter((item) => activeStatuses.indexOf(String(item.rawStatus || item.execution_status || item.status || '')) >= 0);
    const driverIds = new Set((assignments || []).map((item) => Number(item.driver_id || 0)).filter(Boolean));
    const vehicleIds = new Set((assignments || []).map((item) => Number(item.vehicle_id || 0)).filter(Boolean));
    const availableDrivers = (drivers || []).filter((item) => !this.isRetiredStatus(item.status));
    const availableVehicles = (vehicles || []).filter((item) => !this.isRetiredStatus(item.status || item.vehicle_status));
    const idleVehicles = availableVehicles.filter((item) => !vehicleIds.has(Number(item.id || 0)));
    const todayUnassigned = (unassignedRows || []).filter((item) => this.isAssignmentOnDate(item, today));
    const vehicleTypeRows = this.buildVehicleTypeRows(availableVehicles, idleVehicles);
    const tenSeat = vehicleTypeRows.find((item) => item.label === '10座') || { total: 0, idle: 0 };
    const alphard = vehicleTypeRows.find((item) => item.label === 'Alphard') || { total: 0, idle: 0 };
    return {
      todayAssigned: (assignments || []).length,
      todayActive: activeAssignments.length,
      todayTotal: (assignments || []).length + todayUnassigned.length,
      unassignedToday: todayUnassigned.length,
      driverTotal: availableDrivers.length,
      vehicleTotal: availableVehicles.length,
      idleDrivers: Math.max(0, availableDrivers.filter((item) => !driverIds.has(Number(item.id || 0))).length),
      idleVehicles: Math.max(0, idleVehicles.length),
      hiaceTotal: tenSeat.total,
      idleHiace: tenSeat.idle,
      tenSeatTotal: tenSeat.total,
      idleTenSeat: tenSeat.idle,
      alphardTotal: alphard.total,
      idleAlphard: alphard.idle,
      vehicleTypeRows
    };
  },

  buildIdleResources(assignments, drivers, vehicles) {
    const driverIds = new Set((assignments || []).map((item) => Number(item.driver_id || 0)).filter(Boolean));
    const vehicleIds = new Set((assignments || []).map((item) => Number(item.vehicle_id || 0)).filter(Boolean));
    const idleDriverRows = (drivers || [])
      .filter((item) => !this.isRetiredStatus(item.status))
      .filter((item) => !driverIds.has(Number(item.id || 0)))
      .map((item) => ({
        id: `idle-driver-${item.id}`,
        title: item.name || item.driver_name || '司机',
        meta: [item.driver_code || '-', item.phone || item.mobile || '-'].filter(Boolean).join(' · ')
      }));
    const idleVehicleRows = (vehicles || [])
      .filter((item) => !this.isRetiredStatus(item.status || item.vehicle_status))
      .filter((item) => !vehicleIds.has(Number(item.id || 0)))
      .map((item) => ({
        id: `idle-vehicle-${item.id}`,
        title: item.suffix || item.vehicle_code || this.lastDigits(item.plate_number || item.plate || item.vehicle_number) || '车辆',
        meta: [item.vehicle_type || '-', item.vehicle_color || item.color || '-'].filter(Boolean).join(' · ')
      }));
    return { idleDriverRows, idleVehicleRows };
  },

  resourceDriversForAvailability(rows) {
    return (rows || []).map((item, index) => ({
      id: item.resourceId || item.id || `resource-driver-${index}`,
      name: item.title,
      driver_name: item.title,
      driver_code: item.driverCode || '',
      phone: item.phone || item.meta || '',
      status: item.status || ''
    }));
  },

  resourceVehiclesForAvailability(rows) {
    return (rows || []).map((item, index) => ({
      id: item.resourceId || item.id || `resource-vehicle-${index}`,
      suffix: item.suffix || item.title,
      vehicle_code: item.title,
      plate_number: item.plate || item.meta || item.title,
      vehicle_type: item.vehicleType || item.vehicle_type || item.meta || '',
      vehicle_status: item.status || ''
    }));
  },

  buildResourceOverview(library, apiDrivers, apiVehicles) {
    const librarySummary = (library && library.summary) || {};
    const libVehicles = Array.isArray(library && library.vehicles) ? library.vehicles : [];
    const libDrivers = Array.isArray(library && library.drivers) ? library.drivers : [];
    const vehicles = libVehicles.length ? libVehicles : (apiVehicles || []);
    const drivers = libDrivers.length ? libDrivers : (apiDrivers || []);
    const vehicleRows = vehicles
      .map((item, index) => this.decorateResourceVehicle(item, index))
      .filter((item) => !this.isHiddenHomeResourceVehicle(item))
      .sort((a, b) => this.resourceVehicleRowSort(a, b));
    const driverRows = drivers
      .filter((item) => !this.isHiddenDriver(item))
      .map((item, index) => this.decorateResourceDriver(item, index))
      .sort((a, b) => this.resourceDriverRowSort(a, b));
    const vehicleInspectionAlerts = this.resourceVehicleAlerts(vehicleRows, 'vehicleInspectionAlertIso', 'vehicleInspectionAlertText', '车检');
    const threeMonthAlerts = this.resourceVehicleAlerts(vehicleRows, 'threeMonthIso', 'threeMonthText', '3个月点检');
    const healthAlerts = this.resourceDriverAlerts(driverRows, 'healthIso', 'healthText', 'healthExamDate', '人员体检');
    const licenseAlerts = this.resourceDriverAlerts(driverRows, 'licenseIso', 'licenseText', '', '驾照');
    const residenceAlerts = this.resourceDriverAlerts(driverRows, 'residenceIso', 'residenceText', '', '签证');
    const pdfTotal = vehicleRows.reduce((sum, item) => sum + Number(item.docCount || 0), 0);
    const rawVehicleTotal = Number(librarySummary.vehicles || librarySummary.vehicleTotal || 0) || vehicles.length;
    const rawDriverTotal = Number(librarySummary.drivers || librarySummary.driverTotal || 0) || drivers.length;
    const rawPdfTotal = Number(librarySummary.pdf_files || librarySummary.pdfTotal || 0) || pdfTotal;
    const rawCategoryTotal = Number(librarySummary.categories || librarySummary.categoryTotal || 0);
    const categorySet = {};
    vehicleRows.forEach((item) => (item.categories || []).forEach((category) => { categorySet[category] = true; }));
    const alertRows = vehicleInspectionAlerts
      .concat(threeMonthAlerts)
      .concat(healthAlerts)
      .concat(licenseAlerts)
      .concat(residenceAlerts)
      .sort((a, b) => {
        const left = Number(a.sortDays);
        const right = Number(b.sortDays);
        return (Number.isFinite(left) ? left : 9999) - (Number.isFinite(right) ? right : 9999);
      });
    const pdfRows = vehicleRows
      .filter((item) => Number(item.docCount || 0) > 0)
      .map((item) => ({
        id: `pdf-${item.id}`,
        title: item.title,
        meta: `${item.docCount || 0} 个 PDF · ${(item.categories || []).slice(0, 3).join('、') || '车辆资料'}`
      }));
    return {
      summary: {
        vehicleTotal: rawVehicleTotal,
        driverTotal: rawDriverTotal,
        pdfTotal: rawPdfTotal,
        categoryTotal: rawCategoryTotal || Object.keys(categorySet).length,
        vehicleInspectionDue: vehicleInspectionAlerts.length,
        threeMonthDue: threeMonthAlerts.length,
        healthDue: healthAlerts.length,
        licenseDue: licenseAlerts.length,
        residenceDue: residenceAlerts.length,
        alertTotal: alertRows.length
      },
      vehicleInspectionAlerts,
      threeMonthAlerts,
      healthAlerts,
      licenseAlerts,
      residenceAlerts,
      vehicleRows,
      driverRows,
      pdfRows,
      alertRows,
      error: library && library.resourceError ? library.resourceError : ''
    };
  },

  lastDigits(value) {
    const matches = String(value || '').match(/\d+/g);
    if (!matches || !matches.length) return '';
    const suffix = matches.join('').slice(-4);
    return suffix.replace(/^0+(?=\d)/, '');
  },

  decorateResourceVehicle(vehicle, index) {
    const docs = Array.isArray(vehicle.docs || vehicle.files) ? (vehicle.docs || vehicle.files) : [];
    const categories = docs.map((doc) => doc.category || '其他').filter(Boolean);
    const vehicleInspection = this.normalizeResourceDate(vehicle.vehicle_inspection_due_date || vehicle.shaken_due_date || vehicle['车检到期'] || vehicle['車検満了日']);
    const latestThreeMonth = this.latestResourceDocDate(docs, '3ヶ月点検')
      || this.normalizeResourceDate(vehicle.three_month_inspection_date || vehicle.latest_inspection_date || vehicle['3ヶ月点検日期']);
    const latestVehicleInspection = this.latestResourceDocDate(docs, '車検')
      || this.latestResourceDocDate(docs, '车检')
      || this.latestResourceDocDate(docs, '自動車檢查証記録事項')
      || this.latestResourceDocDate(docs, '自動車検査証記録事項')
      || this.latestResourceDocDate(docs, '自動車')
      || this.latestResourceDocDate(docs, '12ヶ月点検')
      || this.normalizeResourceDate(vehicle.shaken_date || vehicle.annual_inspection_date || vehicle.latest_vehicle_inspection_date || vehicle['車検日期'] || vehicle['12ヶ月点検日期']);
    const nextRequired = this.nextResourceVehicleNode(vehicleInspection, latestThreeMonth, latestVehicleInspection);
    const vehicleInspectionAlertIso = nextRequired.type === 'vehicle' && vehicleInspection && nextRequired.date ? nextRequired.date.iso : '';
    const threeMonthIso = nextRequired.type === 'inspection' && nextRequired.date ? nextRequired.date.iso : '';
    const riskDays = [this.resourceDaysUntil(vehicleInspectionAlertIso), this.resourceDaysUntil(threeMonthIso)]
      .filter((value) => value !== null && value <= RESOURCE_VEHICLE_REMINDER_DAYS)
      .sort((a, b) => a - b)[0];
    const plate = vehicle.plate_number || vehicle.plate || vehicle['车牌号'] || '';
    const suffix = vehicle.suffix || vehicle['后四位'] || this.lastDigits(plate);
    const vehicleType = vehicle.vehicle_type || vehicle.car_model || vehicle['车型'] || '';
    const officeText = vehicle.office || vehicle.branch || vehicle.sales_office || vehicle.vehicle_group || vehicle['所属営業所'] || vehicle['事务所'] || '';
    const officeType = this.officeTypeForResource([officeText, plate, suffix, vehicleType].join(' '));
    return {
      id: vehicle.id || vehicle.folder || vehicle.plate_number || index,
      resourceId: vehicle.id || '',
      title: suffix || plate || '车辆',
      vehicleKey: suffix || vehicle.id || vehicle.folder || plate || '',
      suffix,
      plate,
      vehicleType,
      officeText,
      officeType,
      officeLabel: this.officeLabel(officeType),
      meta: [plate, vehicleType]
        .filter(Boolean).join(' · ') || '车辆资料',
      docCount: docs.length,
      categories,
      vehicleInspectionIso: vehicleInspection ? vehicleInspection.iso : '',
      vehicleInspectionText: vehicleInspection ? vehicleInspection.text : '',
      latestVehicleInspectionIso: latestVehicleInspection ? latestVehicleInspection.iso : '',
      latestVehicleInspectionText: latestVehicleInspection ? latestVehicleInspection.text : '',
      nextRequiredType: nextRequired.type,
      nextRequiredLabel: nextRequired.label,
      nextRequiredIso: nextRequired.date ? nextRequired.date.iso : '',
      nextRequiredText: nextRequired.date ? nextRequired.date.text : '',
      vehicleInspectionAlertIso,
      vehicleInspectionAlertText: vehicleInspectionAlertIso ? nextRequired.date.text : '',
      threeMonthIso,
      threeMonthText: nextRequired.type === 'inspection' && nextRequired.date ? nextRequired.date.text : '',
      latestThreeMonthIso: latestThreeMonth ? latestThreeMonth.iso : '',
      latestThreeMonthText: latestThreeMonth ? latestThreeMonth.text : '',
      riskText: riskDays === undefined ? '' : this.resourceDueText(riskDays),
      riskTone: riskDays === undefined ? '' : (riskDays < 0 ? 'danger' : riskDays <= 7 ? 'warning' : 'normal')
    };
  },

  isHiddenHomeResourceVehicle(vehicle) {
    const text = [
      vehicle && vehicle.id,
      vehicle && vehicle.title,
      vehicle && vehicle.meta
    ].filter(Boolean).join(' ');
    return HOME_HIDDEN_RESOURCE_VEHICLE_TAILS.some((tail) => text.indexOf(tail) >= 0);
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

  decorateResourceDriver(driver, index) {
    const healthDate = driver.health_check_date || driver['健康诊断日期'] || '';
    const healthDue = driver.health_check_due_date || this.addDays(healthDate, 365);
    const health = this.normalizeResourceDate(healthDue);
    const license = this.normalizeResourceDate(driver.license_due_date || driver.license_expiry_date || driver['免许有効期限']);
    const residence = this.normalizeResourceDate(driver.residence_due_date || driver.residence_expiry_date || driver['再留期限有效日期'] || driver['在留期限有效日期']);
    const healthDays = health ? this.resourceDaysUntil(health.iso) : null;
    const rowId = driver.id || driver.driver_code || driver.code || driver.name || index;
    const officeText = driver.office || driver.branch || driver.sales_office || driver['所属営業所'] || '';
    const officeType = this.driverOfficeTypeForResource(officeText);
    const status = driver.status || driver.driver_status || driver['状態'] || '';
    const statusValue = this.normalizeResourceDriverStatus(status);
    return {
      id: String(rowId),
      resourceId: driver.id || '',
      title: driver.name || driver.driver_name || driver['運転手名'] || '人员',
      driverCode: driver.driver_code || driver.code || driver['運転手ID'] || '',
      phone: driver.phone || driver.mobile || driver['携帯電話番号'] || '',
      status,
      statusValue,
      statusLabel: this.driverStatusLabel(statusValue),
      statusIndex: this.driverStatusIndex(statusValue),
      healthExamDate: healthDate,
      officeText,
      officeType,
      officeLabel: this.officeLabel(officeType),
      meta: [driver.driver_code || driver.code || driver['運転手ID'], driver.phone || driver.mobile || driver['携帯電話番号']]
        .filter(Boolean).join(' · ') || '人员资料',
      healthIso: health ? health.iso : '',
      healthText: health ? health.text : '',
      licenseIso: license ? license.iso : '',
      licenseText: license ? license.text : '',
      residenceIso: residence ? residence.iso : '',
      residenceText: residence ? residence.text : '',
      riskText: healthDays !== null && healthDays <= RESOURCE_DRIVER_HEALTH_REMINDER_DAYS ? this.resourceDueText(healthDays) : '',
      riskTone: healthDays !== null && healthDays <= RESOURCE_DRIVER_HEALTH_REMINDER_DAYS ? (healthDays < 0 ? 'danger' : healthDays <= 7 ? 'warning' : 'normal') : ''
    };
  },

  officeTypeForResource(value) {
    const text = String(value || '').toLowerCase();
    if (text.indexOf('京都') >= 0 || text.indexOf('kyoto') >= 0) return 'kyoto';
    if (text.indexOf('大阪') >= 0 || text.indexOf('osaka') >= 0 || text.indexOf('なにわ') >= 0) return 'osaka';
    return '';
  },

  driverOfficeTypeForResource(value) {
    const text = String(value || '').toLowerCase();
    if (text.indexOf('京都') >= 0 || text.indexOf('kyoto') >= 0) return 'kyoto';
    return 'osaka';
  },

  normalizeResourceDriverStatus(status) {
    const text = String(status || '').trim().toLowerCase();
    if (['retired', 'resigned', 'deleted'].indexOf(text) >= 0 || status === '离职') return 'retired';
    if (['resting', 'leave', 'off', 'vacation'].indexOf(text) >= 0 || status === '休假') return 'resting';
    return 'available';
  },

  driverStatusLabel(status) {
    const value = this.normalizeResourceDriverStatus(status);
    return { available: '出勤', resting: '休假', retired: '离职' }[value] || '出勤';
  },

  driverStatusIndex(status) {
    const value = this.normalizeResourceDriverStatus(status);
    return Math.max(0, this.data.driverStatusValues.indexOf(value));
  },

  officeLabel(type) {
    return { osaka: '大阪', kyoto: '京都' }[type] || '';
  },

  matchesResourceOfficeFilter(item, officeFilter) {
    if (!officeFilter || officeFilter === 'all') return true;
    return String(item && item.officeType || '') === officeFilter;
  },

  filterResourceRowsByOffice(vehicleRows, driverRows, officeFilter) {
    return {
      vehicles: (vehicleRows || []).filter((item) => this.matchesResourceOfficeFilter(item, officeFilter)),
      drivers: (driverRows || []).filter((item) => this.matchesResourceOfficeFilter(item, officeFilter))
    };
  },

  resourceVehicleAlerts(rows, isoKey, textKey, label) {
    return (rows || [])
      .map((item) => {
        const days = this.resourceDaysUntil(item[isoKey]);
        if (days === null || days > RESOURCE_VEHICLE_REMINDER_DAYS) return null;
        return {
          id: `${label}-${item.id}`,
          title: item.title,
          vehicleKey: item.vehicleKey || item.suffix || item.title,
          vehicleInspectionIso: item.vehicleInspectionIso || '',
          vehicleInspectionText: item.vehicleInspectionText || '',
          latestVehicleInspectionIso: item.latestVehicleInspectionIso || '',
          latestVehicleInspectionText: item.latestVehicleInspectionText || '',
          threeMonthIso: item.threeMonthIso || '',
          threeMonthText: item.threeMonthText || '',
          latestThreeMonthIso: item.latestThreeMonthIso || '',
          latestThreeMonthText: item.latestThreeMonthText || '',
          alertType: label === '车检' ? 'vehicle' : 'inspection',
          meta: `${item[textKey] || '-'} · ${label}`,
          status: this.resourceDueText(days),
          sortDays: days,
          tone: days < 0 ? 'danger' : days <= 7 ? 'warning' : 'normal'
        };
      })
      .filter(Boolean)
      .sort((a, b) => a.sortDays - b.sortDays);
  },

  resourceDriverAlerts(rows, isoKey, textKey, examDateKey, label) {
    return (rows || [])
      .map((item) => {
        const days = this.resourceDaysUntil(item[isoKey]);
        if (days === null || days > 30) return null;
        return {
          id: `${label}-${item.id}`,
          driverId: item.id,
          title: item.title,
          driverCode: item.driverCode || '',
          healthExamDate: examDateKey ? (item[examDateKey] || '') : (item.healthExamDate || ''),
          healthText: item.healthText || '',
          licenseIso: item.licenseIso || '',
          licenseText: item.licenseText || '',
          residenceIso: item.residenceIso || '',
          residenceText: item.residenceText || '',
          alertType: label === '人员体检' ? 'health' : (label === '签证' ? 'residence' : 'license'),
          alertLabel: label,
          meta: `${item[textKey] || '-'} · ${label}`,
          status: this.resourceDueText(days),
          sortDays: days,
          tone: days < 0 ? 'danger' : days <= 7 ? 'warning' : 'normal'
        };
      })
      .filter(Boolean)
      .sort((a, b) => a.sortDays - b.sortDays);
  },

  resourceVehicleRowSort(a, b) {
    const left = this.resourceVehicleRowScore(a);
    const right = this.resourceVehicleRowScore(b);
    return left - right || String(a.title || '').localeCompare(String(b.title || ''), 'zh-Hans-CN');
  },

  resourceVehicleRowScore(item) {
    const days = [
      this.resourceDaysUntil(item.vehicleInspectionAlertIso),
      this.resourceDaysUntil(item.threeMonthIso)
    ].filter((value) => value !== null && value <= RESOURCE_VEHICLE_REMINDER_DAYS);
    return days.length ? Math.min.apply(null, days) : 9999;
  },

  resourceDriverRowSort(a, b) {
    const left = this.resourceDriverRowScore(a);
    const right = this.resourceDriverRowScore(b);
    return left - right || String(a.title || '').localeCompare(String(b.title || ''), 'zh-Hans-CN');
  },

  resourceDriverRowScore(item) {
    const days = this.resourceDaysUntil(item.healthIso);
    return days !== null && days <= RESOURCE_DRIVER_HEALTH_REMINDER_DAYS ? days : 9999;
  },

  latestResourceDocDate(docs, keyword) {
    const dates = (docs || [])
      .filter((doc) => String(doc.category || doc.name || '').indexOf(keyword) >= 0)
      .map((doc) => this.normalizeResourceDate(doc.date || doc.name))
      .filter(Boolean)
      .sort((a, b) => String(b.iso).localeCompare(String(a.iso)));
    return dates[0] || null;
  },

  nextResourceVehicleNode(vehicleInspectionDue, latestThreeMonthDate, latestVehicleInspectionDate) {
    const nextVehicleInspection = vehicleInspectionDue
      || (latestVehicleInspectionDate ? this.addResourceMonths(latestVehicleInspectionDate.iso, 12) : null);
    const cycleStart = vehicleInspectionDue
      ? this.addResourceMonths(vehicleInspectionDue.iso, -12)
      : latestVehicleInspectionDate
      || (nextVehicleInspection ? this.addResourceMonths(nextVehicleInspection.iso, -12) : null);
    if (!cycleStart) {
      const fallback = latestThreeMonthDate ? this.addResourceMonths(latestThreeMonthDate.iso, 3) : nextVehicleInspection;
      return {
        type: fallback === nextVehicleInspection ? 'vehicle' : 'inspection',
        label: fallback === nextVehicleInspection ? '车检' : '3个月点检',
        date: fallback
      };
    }
    const completedIso = [cycleStart, latestThreeMonthDate]
      .filter(Boolean)
      .map((item) => item.iso)
      .sort()
      .pop();
    const nodes = [
      { type: 'inspection', label: '3个月点检', date: this.addResourceMonths(cycleStart.iso, 3) },
      { type: 'inspection', label: '3个月点检', date: this.addResourceMonths(cycleStart.iso, 6) },
      { type: 'inspection', label: '3个月点检', date: this.addResourceMonths(cycleStart.iso, 9) },
      { type: 'vehicle', label: '车检', date: nextVehicleInspection || this.addResourceMonths(cycleStart.iso, 12) }
    ]
      .filter((item) => item.date)
      .sort((a, b) => String(a.date.iso).localeCompare(String(b.date.iso)));
    const vehicleNode = nodes.find((item) => item.type === 'vehicle');
    const vehicleDays = vehicleNode ? this.resourceDaysUntil(vehicleNode.date.iso) : null;
    if (vehicleNode && vehicleDays !== null && vehicleDays <= RESOURCE_VEHICLE_REMINDER_DAYS) return vehicleNode;
    const pendingNodes = nodes.filter((item) => !completedIso || item.date.iso > completedIso);
    const overdueNodes = pendingNodes
      .map((item) => ({ ...item, days: this.resourceDaysUntil(item.date.iso) }))
      .filter((item) => item.days !== null && item.days < 0)
      .sort((a, b) => String(b.date.iso).localeCompare(String(a.date.iso)));
    if (overdueNodes.length) {
      const node = overdueNodes[0];
      return { type: node.type, label: node.label, date: node.date };
    }
    const next = pendingNodes.find((item) => {
      const days = this.resourceDaysUntil(item.date.iso);
      return days === null || days <= RESOURCE_VEHICLE_REMINDER_DAYS;
    }) || pendingNodes[0];
    if (next) return next;
    const nextCycleBase = nextVehicleInspection || cycleStart;
    return { type: 'inspection', label: '3个月点检', date: this.addResourceMonths(nextCycleBase.iso, 3) };
  },

  addResourceMonths(dateText, months) {
    const normalized = this.normalizeResourceDate(dateText);
    if (!normalized) return null;
    const parts = normalized.iso.split('-').map((item) => Number(item));
    const date = new Date(parts[0], parts[1] - 1, parts[2]);
    date.setMonth(date.getMonth() + months);
    return this.resourceDateObject(date.getFullYear(), date.getMonth() + 1, date.getDate());
  },

  normalizeResourceDate(value) {
    const raw = String(value || '').trim();
    if (!raw || raw === '-' || /^\d{1,4}$/.test(raw)) return null;
    let match = raw.match(/(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})/);
    if (match) return this.resourceDateObject(Number(match[1]), Number(match[2]), Number(match[3]));
    match = raw.match(/令和\s*(\d+)\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?/);
    if (match) return this.resourceDateObject(2018 + Number(match[1]), Number(match[2]), Number(match[3]));
    match = raw.match(/R\s*(\d)(\d{2})(\d{2})/i);
    if (match) return this.resourceDateObject(2018 + Number(match[1]), Number(match[2]), Number(match[3]));
    match = raw.match(/20(\d{2})(\d{2})(\d{2})/);
    if (match) return this.resourceDateObject(2000 + Number(match[1]), Number(match[2]), Number(match[3]));
    return null;
  },

  resourceDateObject(year, month, day) {
    if (!year || month < 1 || month > 12 || day < 1 || day > 31) return null;
    const date = new Date(year, month - 1, day);
    if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null;
    return { iso: this.formatDate(date), text: `令和${year - 2018}年${month}月${day}日` };
  },

  resourceDaysUntil(dateText) {
    if (!dateText) return null;
    const target = new Date(`${dateText}T00:00:00`);
    if (Number.isNaN(target.getTime())) return null;
    const today = new Date();
    const base = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    return Math.ceil((target.getTime() - base.getTime()) / 86400000);
  },

  resourceDueText(days) {
    if (days < 0) return `已过期 ${Math.abs(days)} 天`;
    if (days === 0) return '今天到期';
    return `${days} 天后`;
  },

  addDays(dateText, days) {
    const normalized = this.normalizeResourceDate(dateText);
    if (!normalized) return '';
    const parts = normalized.iso.split('-').map((item) => Number(item));
    const date = new Date(parts[0], parts[1] - 1, parts[2]);
    date.setDate(date.getDate() + days);
    return this.formatDate(date);
  },

  resourceAlertSort(status) {
    const match = String(status || '').match(/-?\d+/);
    return match ? Number(match[0]) : 999;
  },

  buildVehicleTypeRows(vehicles, idleVehicles) {
    const groups = {};
    (vehicles || []).forEach((item) => {
      const label = this.vehicleTypeBucket(item);
      if (!groups[label]) groups[label] = { label, idle: 0, total: 0 };
      groups[label].total += 1;
    });
    (idleVehicles || []).forEach((item) => {
      const label = this.vehicleTypeBucket(item);
      if (!groups[label]) groups[label] = { label, idle: 0, total: 0 };
      groups[label].idle += 1;
    });
    return Object.keys(groups)
      .map((key) => groups[key])
      .filter((item) => item.total > 0)
      .sort((a, b) => {
        const order = { '10座': 1, Alphard: 2 };
        return (order[a.label] || 5) - (order[b.label] || 5) || b.total - a.total;
      });
  },

  vehicleTypeBucket(vehicle) {
    const text = [
      vehicle.vehicle_type,
      vehicle.vehicle_model,
      vehicle.model,
      vehicle.body_type,
      vehicle.seat_count,
      vehicle.capacity,
      vehicle.note,
      vehicle.remark
    ].filter(Boolean).join(' ').toLowerCase();
    if (text.indexOf('alphard') >= 0 || text.indexOf('アルファ') >= 0 || text.indexOf('阿尔法') >= 0 || text.indexOf('3代') >= 0 || text.indexOf('7座') >= 0) return 'Alphard';
    return '10座';
  },

  isRetiredStatus(status) {
    const text = String(status || '').toLowerCase();
    return text.indexOf('retired') >= 0 || text.indexOf('deleted') >= 0 || text.indexOf('removed') >= 0 || text.indexOf('减车') >= 0;
  },

  detectPhoneRegion(phone) {
    const raw = String(phone || '').trim();
    if (!raw) return '';
    const compact = raw.replace(/\s+/g, '');
    if (compact.indexOf('+81') === 0) return '日本';
    if (compact.indexOf('+86') === 0) return '中国';
    if (compact.indexOf('+852') === 0) return '香港';
    if (compact.indexOf('+853') === 0) return '澳门';
    if (compact.indexOf('+886') === 0) return '台湾';
    if (compact.indexOf('+82') === 0) return '韩国';
    if (compact.indexOf('+60') === 0) return '马来西亚';
    if (compact.indexOf('+65') === 0) return '新加坡';
    if (compact.indexOf('+66') === 0) return '泰国';
    if (compact.indexOf('+1') === 0) return '北美';
    if (compact.indexOf('+44') === 0) return '英国';
    if (compact.indexOf('+61') === 0) return '澳大利亚';
    if (compact.indexOf('+971') === 0) return '阿联酋';
    return '';
  },

  decorateUnassignedOrder(item) {
    const status = item.kind === 'draft' ? 'parsed' : (item.dispatch_status || 'unassigned');
    return Object.assign({}, item, {
      id: item.id,
      title: item.oid || item.order_id || `订单 ${item.id}`,
      meta: `${item.order_date || '-'} ${item.start_time || '--:--'} · ${this.statusText(status)}`,
      body: `${item.pickup_location || '-'} -> ${item.dropoff_location || '-'}`,
      action: 'dispatch',
      actionText: '委派'
    });
  },

  currentTenantId() {
    const session = this.data.session || api.getSession() || {};
    return Number(
      (session.user && session.user.tenant_id)
      || (session.dispatcher && session.dispatcher.tenant_id)
      || 0
    );
  },

  sortDispatchRows(rows) {
    return rows.slice().sort((a, b) => {
      const left = `${a.order_date || ''} ${a.start_time || ''} ${a.pickup_location || ''}`;
      const right = `${b.order_date || ''} ${b.start_time || ''} ${b.pickup_location || ''}`;
      return left.localeCompare(right, 'zh-Hans-CN');
    });
  },

  buildDueRows(driver) {
    if (!driver) return [];
    return [
      this.dueRow('健康体检即将到期', driver.health_check_due_date, 'health'),
      this.dueRow('驾照即将到期', driver.license_due_date, 'license')
    ].filter(Boolean);
  },

  dueRow(title, dateText, kind) {
    const days = this.daysUntil(dateText);
        if (days === null || days > RESOURCE_DRIVER_HEALTH_REMINDER_DAYS) return null;
    return {
      id: `due-${kind}`,
      title,
      meta: days < 0 ? `已过期 ${Math.abs(days)} 天` : `剩余 ${days} 天`,
      body: dateText || '-',
      priority: days < 0 ? 'high' : 'normal',
      action: 'profile',
      actionText: '查看'
    };
  },

  daysUntil(dateText) {
    if (!dateText) return null;
    const target = new Date(`${dateText}T00:00:00`);
    if (Number.isNaN(target.getTime())) return null;
    const today = new Date();
    const base = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    return Math.ceil((target.getTime() - base.getTime()) / 86400000);
  },

  isSuppressedDriverNotification(item) {
    const type = String(item.notification_type || item.type || '');
    const title = `${item.title || ''} ${item.body || ''}`;
    if (['delay_risk', 'upcoming_start', 'not_departed', 'unconfirmed_order'].indexOf(type) >= 0) return true;
    return title.indexOf('未出库') >= 0 || title.indexOf('订单未确认') >= 0 || title.indexOf('可能延误') >= 0 || title.indexOf('即将开始') >= 0;
  },

  decorateNotification(item) {
    return {
      id: item.id,
      notificationId: item.id,
      kind: 'notification',
      title: item.title || this.notificationTypeText(item.notification_type),
      meta: `${this.notificationTypeText(item.notification_type)} · ${this.priorityText(item.priority)}`,
      body: item.body || '',
      priority: item.priority || 'normal',
      rawStatus: item.status || 'unread',
      action: 'detail',
      actionText: '详情',
      raw: item
    };
  },

  buildPanel(mode, todayOrders, allOrders, pending, exceptions, unread) {
    const config = {
      orders: { title: '今日订单', hint: '今天的订单集中显示在这里，点击订单进入任务处理。', rows: todayOrders, unit: '条' },
      all: { title: '全部订单', hint: '已分配给你的订单全部显示在这里，点击订单进入任务处理。', rows: allOrders, unit: '条' },
      pending: { title: '待确认派单', hint: '确认后订单状态会变为已接单。', rows: pending, unit: '条' },
      exceptions: { title: '异常订单', hint: '只显示需要司机关注的异常。', rows: exceptions, unit: '条' },
      unread: { title: '新通知', hint: '只显示还未读的新通知。', rows: this.unreadNotificationRows(unread), unit: '条' }
    };
    return config[mode] || config.orders;
  },

  buildDispatchPanel(mode, unassignedRows, unread, allRows, driverStats, resourceRows) {
    const workloadRows = this.buildWorkloadPanelRows(driverStats || []);
    const config = {
      orders: { title: '待委派订单', hint: '未派车订单集中显示在这里，点击订单继续处理。', rows: unassignedRows, unit: '条' },
      all: { title: '全部订单', hint: '已派、待派和待确认的订单集中显示在这里。', rows: allRows || [], unit: '条' },
      pending: { title: '待委派订单', hint: '请尽快安排司机和车辆。', rows: unassignedRows, unit: '条' },
      exceptions: { title: '异常订单', hint: '异常订单请到通知或异常中心确认。', rows: [], unit: '条' },
      unread: { title: '新通知', hint: '只显示大厅成交、派车和运行提醒的新通知。', rows: this.unreadNotificationRows(unread), unit: '条' },
      workload: { title: '联勤司机排行', hint: '连续出勤超过 10 天的司机，按连续天数从多到少排列。', rows: workloadRows, unit: '人' },
      idle: { title: '今日空闲', hint: '左侧为空闲司机，右侧为空闲车辆。', rows: [{ id: 'idle-drivers' }, { id: 'idle-vehicles' }], unit: '组' },
      resources: { title: '车辆 / 人员资料总览', hint: '车辆档案、人员资料、PDF文件和到期提醒集中显示在这里。', rows: resourceRows || [], unit: '项' }
    };
    return config[mode] || config.orders;
  },

  toggleResourceSection(e) {
    const section = e.currentTarget.dataset.section || '';
    this.setData({
      resourceExpandedSection: this.data.resourceExpandedSection === section ? '' : section
    });
  },

  switchResourceFocus(e) {
    const section = e.currentTarget.dataset.section || 'alerts';
    this.setData({
      resourceFocus: this.data.resourceFocus === section ? 'alerts' : section,
      resourceExpandedSection: section,
      expandedHomeVehicleId: '',
      expandedHomeDriverId: ''
    });
  },

  filterResourceAlertRows(rows, filter) {
    const selected = String(filter || 'all');
    if (selected === 'all') return (rows || []).slice();
    return (rows || []).filter((item) => item && item.alertType === selected);
  },

  selectResourceAlertFilter(e) {
    const selected = String((e.currentTarget.dataset || {}).filter || 'all');
    const resourceAlertFilter = this.data.resourceAlertFilter === selected ? 'all' : selected;
    this.setData({
      resourceAlertFilter,
      visibleResourceAlertRows: this.filterResourceAlertRows(this.data.resourceAlertRows, resourceAlertFilter),
      expandedHomeVehicleId: '',
      expandedHomeDriverId: ''
    });
  },

  clearResourceAlertFilter() {
    if (this.data.resourceAlertFilter === 'all') return;
    this.setData({
      resourceAlertFilter: 'all',
      visibleResourceAlertRows: this.filterResourceAlertRows(this.data.resourceAlertRows, 'all'),
      expandedHomeVehicleId: '',
      expandedHomeDriverId: ''
    });
  },

  switchResourceOffice(e) {
    const resourceOfficeFilter = (e.currentTarget.dataset || {}).office || 'all';
    const filtered = this.filterResourceRowsByOffice(
      this.data.resourceAllVehicleRows || [],
      this.data.resourceAllDriverRows || [],
      resourceOfficeFilter
    );
    this.setData({
      resourceOfficeFilter,
      resourceVehicleRows: filtered.vehicles,
      resourceDriverRows: filtered.drivers,
      expandedHomeVehicleId: '',
      expandedHomeDriverId: ''
    });
  },

  toggleHomeResourceVehicle(e) {
    const id = String((e.currentTarget.dataset || {}).id || '');
    if (!id) return;
    this.setData({ expandedHomeVehicleId: this.data.expandedHomeVehicleId === id ? '' : id });
  },

  toggleHomeResourceDriver(e) {
    const id = String((e.currentTarget.dataset || {}).id || '');
    if (!id) return;
    this.setData({ expandedHomeDriverId: this.data.expandedHomeDriverId === id ? '' : id });
  },

  noopTap() {},

  isResourceNotFoundError(err) {
    const message = String((err && (err.error || err.detail || err.errMsg || err.message)) || '').toLowerCase();
    return Number(err && err.statusCode) === 404 || message.indexOf('not_found') >= 0 || message.indexOf('not found') >= 0;
  },

  updateHomeDriverStatus(e) {
    const dataset = e.currentTarget.dataset || {};
    const resourceId = dataset.resourceId || '';
    const driverKey = dataset.title || dataset.driverCode || dataset.phone || '';
    const status = this.data.driverStatusValues[Number(e.detail.value || 0)] || 'available';
    const label = this.driverStatusLabel(status);
    if (!resourceId && !driverKey) return;
    wx.showModal({
      title: '更新人员状态',
      content: `${dataset.title || '人员'}\n状态改为：${label}`,
      confirmText: '更新',
      success: (res) => {
        if (!res.confirm) return;
        wx.showLoading({ title: '更新中' });
        const fallback = () => api.updateResourceDriverStatus({
          driver_key: driverKey,
          driver_code: dataset.driverCode || '',
          phone: dataset.phone || '',
          name: dataset.title || '',
          status,
          driver_status: status
        });
        const task = resourceId
          ? api.updateResourceDriver(resourceId, { status, driver_status: status }).catch((err) => {
            if (driverKey && this.isResourceNotFoundError(err)) return fallback();
            return Promise.reject(err);
          })
          : fallback();
        task.then(() => {
          wx.hideLoading();
          wx.showToast({ title: '已更新', icon: 'success' });
          this.refreshResourceOverview();
        }).catch((err) => {
          wx.hideLoading();
          wx.showToast({ title: err && err.error ? err.error : '更新失败', icon: 'none' });
        });
      }
    });
  },

  updateHomeVehicleInspectionDate(e) {
    const dataset = e.currentTarget.dataset || {};
    const vehicleKey = dataset.key || dataset.title || '';
    const inspectionType = dataset.type || 'inspection';
    const inspectionDate = e.detail.value || '';
    if (!vehicleKey || !inspectionDate) return;
    const label = inspectionType === 'vehicle' ? '车检' : '3个月点检';
    wx.showModal({
      title: `更新${label}日期`,
      content: `${dataset.title || vehicleKey}\n${label}日期更新为 ${inspectionDate}？`,
      confirmText: '更新',
      success: (res) => {
        if (!res.confirm) return;
        wx.showLoading({ title: '更新中' });
        api.updateResourceVehicleInspection({
          vehicle_key: vehicleKey,
          inspection_type: inspectionType,
          inspection_date: inspectionDate
        }).then(() => {
          wx.hideLoading();
          wx.showToast({ title: '已更新', icon: 'success' });
          this.refreshResourceOverview();
        }).catch((err) => {
          wx.hideLoading();
          wx.showToast({ title: err && err.error ? err.error : '更新失败', icon: 'none' });
        });
      }
    });
  },

  uploadHomeVehicleInspectionDocument(e) {
    const dataset = e.currentTarget.dataset || {};
    const vehicleKey = dataset.key || dataset.title || '';
    const inspectionType = dataset.type || 'inspection';
    const inspectionDate = dataset.date || '';
    const label = inspectionType === 'vehicle' ? '车检' : '3个月点检';
    if (!vehicleKey) return;
    if (!inspectionDate) {
      wx.showToast({ title: `请先选择${label}日期`, icon: 'none' });
      return;
    }
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
            wx.showModal({
              title: `上传${label}资料`,
              content: `${dataset.title || vehicleKey}\n${label}日期 ${inspectionDate}\n${file.name || `${label}资料`}`,
              confirmText: '上传',
              success: (modalRes) => {
                if (!modalRes.confirm) return;
                wx.showLoading({ title: '上传中' });
                api.updateResourceVehicleInspection({
                  vehicle_key: vehicleKey,
                  inspection_type: inspectionType,
                  inspection_date: inspectionDate,
                  file_name: file.name || label,
                  content_type: this.contentTypeForFile(file.name || ''),
                  file_base64: readRes.data
                }).then(() => {
                  wx.hideLoading();
                  wx.showToast({ title: '已上传', icon: 'success' });
                  this.refreshResourceOverview();
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

  updateHomeDriverHealthDate(e) {
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
          this.updateHomeDriverHealthLocal(driverKey, healthCheckDate);
        }).catch((err) => {
          wx.hideLoading();
          wx.showToast({ title: err && err.error ? err.error : '更新失败', icon: 'none' });
        });
      }
    });
  },

  updateHomeDriverHealthLocal(driverKey, healthCheckDate) {
    const matchesDriver = (item) => {
      const key = String(driverKey || '');
      return key && (
        String(item.driverCode || '') === key ||
        String(item.title || '') === key ||
        String(item.id || '') === key ||
        String(item.driverId || '') === key
      );
    };
    const patchItem = (item) => {
      if (!matchesDriver(item)) return item;
      return Object.assign({}, item, {
        healthExamDate: healthCheckDate,
        healthText: healthCheckDate
      });
    };
    const resourceAllDriverRows = (this.data.resourceAllDriverRows || []).map(patchItem);
    const filtered = this.filterResourceRowsByOffice(
      this.data.resourceAllVehicleRows || [],
      resourceAllDriverRows,
      this.data.resourceOfficeFilter
    );
    this.setData({
      resourceAllDriverRows,
      resourceDriverRows: filtered.drivers,
      resourceHealthAlerts: (this.data.resourceHealthAlerts || []).map(patchItem)
    });
  },

  uploadHomeDriverHealthDocument(e) {
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
        wx.getFileSystemManager().readFile({
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
                  this.refreshResourceOverview();
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

  unreadNotificationRows(rows) {
    return (rows || []).filter((item) => String(item.rawStatus || item.status || 'unread') !== 'read');
  },

  buildWorkloadPanelRows(driverStats) {
    return (driverStats || []).map((item, index) => ({
      id: `workload-${item.driver_id || index}`,
      kind: 'workload',
      title: item.driver_name || '司机',
      meta: `连续 ${item.continuous_days || 0} 天 · 本月 ${item.month_orders || 0} 单`,
      body: `今日 ${item.today_orders || 0} 单 · 本月休息 ${item.rest_days || 0} 天`,
      priority: item.continuous_days > 13 ? 'critical' : 'high',
      actionText: `${item.continuous_days || 0}天`
    }));
  },

  buildOperationsNotificationDetail(notifications) {
    return {
      title: '通知',
      hint: '车辆、司机证件、异常和任务提醒集中显示在这里。',
      unit: '条',
      rows: (notifications || []).map((item) => ({
        id: item.id,
        title: item.title || '通知',
        meta: item.meta || '',
        body: item.body || ''
      }))
    };
  },

  computeDriverStatus(rows, workbench) {
    const vehicleStatus = String((workbench || {}).vehicle_status || '');
    const statuses = rows.map((item) => item.rawStatus);
    if (vehicleStatus.indexOf('已入库') >= 0 || statuses.indexOf('returned') >= 0) return { label: '已入库', hint: '今天工作已结束。' };
    if (statuses.indexOf('in_service') >= 0 || statuses.indexOf('arrived') >= 0) return { label: '行驶中', hint: '正在执行当前任务。' };
    if (vehicleStatus.indexOf('已出库') >= 0 || statuses.indexOf('departed') >= 0) return { label: '已经出库', hint: '车辆已出库，可以执行任务。' };
    return { label: '未出库', hint: '点击这里进入任务页，进行车辆出库操作。' };
  },

  statusText(status) {
    return { parsed: '待确认', unassigned: '未派车', assigned: '待确认', confirmed: '已接单', departed: '已出库', arrived: '已到达', in_service: '行驶中', completed: '已完成', returned: '已入库' }[status] || status || '-';
  },

  switchOperationsSection(e) {
    const section = e.currentTarget.dataset.section || 'tasks';
    const detail = section === 'notifications'
      ? this.buildOperationsNotificationDetail(this.data.notifications)
      : this.buildOperationsDetail(
        section,
        this.data.operationsTaskRows,
        this.data.operationsVehicleRows,
        this.data.operationsDriverRows,
        this.data.operationsAttendanceRows
      );
    this.setData({
      operationsSection: section,
      operationsDetailTitle: detail.title,
      operationsDetailHint: detail.hint,
      operationsDetailRows: detail.rows,
      operationsDetailUnit: detail.unit
    });
  },

  switchPanel(e) {
    const mode = e.currentTarget.dataset.mode || 'orders';
    const newNotifications = this.unreadNotificationRows(this.data.notifications || []);
    if (this.data.canDispatch) {
      const panel = this.buildDispatchPanel(
        mode,
        this.data.unassignedRows || [],
        newNotifications,
        this.data.dispatchAllRows || [],
        this.data.driverStats || [],
        this.data.resourceAlertRows || []
      );
      this.setData({ panelMode: mode, panelTitle: panel.title, panelHint: panel.hint, panelUnit: panel.unit || '条', panelRows: panel.rows });
      if (mode === 'resources') this.refreshResourceOverview();
      return;
    }
    const allOrders = this.data.driverAssignments || [];
    const today = this.formatDate(new Date());
    const todayOrders = allOrders.filter((item) => this.isAssignmentOnDate(item, today));
    const pending = allOrders.filter((item) => item.rawStatus === 'assigned');
    const exceptions = allOrders.filter((item) => ['incident', 'exception', 'delayed'].indexOf(String(item.order_status || item.status || '')) >= 0);
    const unread = newNotifications;
    const panel = this.buildPanel(mode, todayOrders, allOrders, pending, exceptions, unread);
    this.setData({ panelMode: mode, panelTitle: panel.title, panelHint: panel.hint, panelUnit: panel.unit || '条', panelRows: panel.rows });
    if (mode === 'resources') this.refreshResourceOverview();
  },

  showHintTip(e) {
    const tip = (e.currentTarget.dataset || {}).tip || '';
    if (!tip) return;
    wx.showModal({
      title: '说明',
      content: tip,
      showCancel: false,
      confirmText: '知道了'
    });
  },

  refreshResourceOverview() {
    console.info('[dispatch resource refresh start]', {
      baseUrl: api.getBaseUrl(),
      role: api.getRole(this.data.session || api.getSession())
    });
    api.resourceLibrary()
      .then((library) => {
        const summary = (library && library.summary) || {};
        console.info('[dispatch resource refresh loaded]', {
          vehicles: Array.isArray(library && library.vehicles) ? library.vehicles.length : 0,
          drivers: Array.isArray(library && library.drivers) ? library.drivers.length : 0,
          pdf: summary.pdf_files || summary.pdfTotal || 0
        });
        const resourceOverview = this.buildResourceOverview(library || {}, [], []);
        const visibleResourceAlertRows = this.filterResourceAlertRows(
          resourceOverview.alertRows,
          this.data.resourceAlertFilter
        );
        const filteredResourceRows = this.filterResourceRowsByOffice(
          resourceOverview.vehicleRows,
          resourceOverview.driverRows,
          this.data.resourceOfficeFilter
        );
        const nextData = {
          resourceSummary: resourceOverview.summary,
          resourceVehicleAlerts: resourceOverview.vehicleInspectionAlerts,
          resourceInspectionAlerts: resourceOverview.threeMonthAlerts,
          resourceHealthAlerts: resourceOverview.healthAlerts,
          resourceLicenseAlerts: resourceOverview.licenseAlerts,
          resourceResidenceAlerts: resourceOverview.residenceAlerts,
          resourceAlertRows: resourceOverview.alertRows,
          visibleResourceAlertRows,
          resourceAllVehicleRows: resourceOverview.vehicleRows,
          resourceAllDriverRows: resourceOverview.driverRows,
          resourceVehicleRows: filteredResourceRows.vehicles,
          resourceDriverRows: filteredResourceRows.drivers,
          resourcePdfRows: resourceOverview.pdfRows,
          resourceError: resourceOverview.error
        };
        if (this.data.panelMode === 'resources') {
          const panel = this.data.canDispatch
            ? this.buildDispatchPanel('resources', this.data.unassignedRows || [], this.unreadNotificationRows(this.data.notifications || []), this.data.dispatchAllRows || [], this.data.driverStats || [], resourceOverview.alertRows || [])
            : this.buildPanel('resources', [], this.data.driverAssignments || [], [], [], []);
          nextData.panelRows = panel.rows;
          nextData.panelUnit = panel.unit || this.data.panelUnit;
        }
        this.setData(nextData);
      })
      .catch((err) => {
        console.warn('[dispatch resource refresh failed]', err);
        this.setData({
          resourceError: err && (err.error || err.detail || err.errMsg) || 'resource_failed'
        });
      });
  },

  onBellTap() {
    console.info('[dispatch bell tap]');
    const newNotifications = this.unreadNotificationRows(this.data.notifications || []);
    const panel = this.data.canDispatch
      ? this.buildDispatchPanel('unread', this.data.unassignedRows || [], newNotifications, this.data.dispatchAllRows || [], this.data.driverStats || [], this.data.resourceAlertRows || [])
      : this.buildPanel('unread', [], this.data.driverAssignments || [], [], [], newNotifications);
    this.setData({
      panelMode: 'unread',
      panelTitle: panel.title,
      panelHint: panel.hint,
      panelUnit: panel.unit || '条',
      panelRows: panel.rows
    });
  },

  isAssignmentOnDate(item, date) {
    if (!date) return false;
    const start = item.order_date || item.start_date || date;
    const end = item.end_date || start;
    return start <= date && end >= date;
  },

  onPanelRowTap(e) {
    const index = Number(e.currentTarget.dataset.index || 0);
    const item = this.data.panelRows[index];
    if (!item) return;
    if (item.action === 'confirm') {
      this.confirmAssignment(item);
      return;
    }
    if (item.action === 'task') {
      this.goTask();
      return;
    }
    if (item.action === 'dispatch') {
      this.goDispatch();
      return;
    }
    if (item.action === 'profile') {
      wx.reLaunch({ url: '/package_dispatch/pages/profile/index' });
      return;
    }
    if (item.action === 'map') {
      this.goMap();
      return;
    }
    if (item.kind === 'notification') {
      this.markNotificationRead(item);
      return;
    }
    wx.showModal({
      title: item.title || '通知详情',
      content: [item.meta, item.body].filter(Boolean).join('\n'),
      showCancel: false,
      confirmText: '知道了'
    });
  },

  markNotificationRead(item) {
    wx.showModal({
      title: item.title || '通知详情',
      content: [item.meta, item.body].filter(Boolean).join('\n') || '无内容',
      showCancel: false,
      confirmText: item.rawStatus === 'read' ? '关闭' : '标为已读',
      success: () => {
        if (item.rawStatus === 'read' || !item.notificationId) return;
        const session = this.data.session || {};
        const driverId = session.user && session.user.profile_id ? session.user.profile_id : 0;
        if (!driverId) return;
        api.markDriverNotificationRead(driverId, item.notificationId)
          .then(() => this.loadDashboard())
          .catch((err) => {
            console.error('[driver notification read failed]', err);
            wx.showToast({ title: '已读同步失败', icon: 'none' });
          });
      }
    });
  },

  onOperationsRowTap(e) {
    const index = Number(e.currentTarget.dataset.index || 0);
    const item = this.data.operationsRows[index];
    if (!item) return;
    if (item.action === 'map') {
      this.goMap();
      return;
    }
    if (item.action === 'profile') {
      wx.reLaunch({ url: '/package_dispatch/pages/profile/index' });
      return;
    }
    wx.showModal({
      title: item.title || '运行监控',
      content: [item.meta, item.body].filter(Boolean).join('\n'),
      showCancel: false,
      confirmText: '知道了'
    });
  },

  confirmAssignment(item) {
    const session = this.data.session || {};
    const driverId = session.user && session.user.profile_id ? session.user.profile_id : 0;
    if (!driverId || !item.id) return;
    wx.showModal({
      title: '确认接单',
      content: [item.title, item.meta, item.body].filter(Boolean).join('\n'),
      confirmText: '确认',
      cancelText: '取消',
      success: (res) => {
        if (!res.confirm) return;
        api.submitDriverReport({
          driver_id: driverId,
          assignment_id: item.id,
          report_type: 'confirm_order',
          location_text: '司机首页确认接单',
          note: JSON.stringify({ action: 'confirm_order', source: 'driver_home' })
        }).then((result) => {
          if (result && result.success === false) {
            wx.showToast({ title: this.reportError(result), icon: 'none' });
            return;
          }
          wx.showToast({ title: '已确认接单', icon: 'success' });
          this.markRelatedAssignmentNotificationsRead(item).then(() => this.loadDashboard());
        }).catch(() => {
          wx.showToast({ title: '确认失败', icon: 'none' });
        });
      }
    });
  },

  onDispatchTaskTap(e) {
    const index = Number(e.currentTarget.dataset.index || 0);
    const item = (this.data.dispatchTaskRows || [])[index];
    if (!item) return;
    const content = [
      item.meta,
      item.body,
      item.guestLine ? `客人：${item.guestLine}` : '',
      item.resourceLine ? `执行：${item.resourceLine}` : '',
      item.remarkPreview ? `备注：${item.remarkPreview}` : ''
    ].filter(Boolean).join('\n');
    wx.showModal({
      title: item.title || '任务详情',
      content,
      showCancel: false,
      confirmText: '知道了'
    });
  },

  markRelatedAssignmentNotificationsRead(assignment) {
    const session = this.data.session || {};
    const driverId = session.user && session.user.profile_id ? session.user.profile_id : 0;
    if (!driverId || !assignment) return Promise.resolve();
    const assignmentId = String(assignment.id || assignment.assignment_id || '');
    const orderId = String(assignment.oid || assignment.order_id || assignment.title || '');
    const targets = (this.data.notifications || []).filter((item) => {
      if (item.rawStatus === 'read' || !item.notificationId) return false;
      const raw = item.raw || {};
      const haystack = [
        raw.source_id,
        raw.title,
        raw.body,
        item.title,
        item.body
      ].filter(Boolean).join(' ');
      return (assignmentId && haystack.indexOf(assignmentId) >= 0) || (orderId && haystack.indexOf(orderId) >= 0);
    });
    if (!targets.length) return Promise.resolve();
    return Promise.all(targets.map((item) => api.markDriverNotificationRead(driverId, item.notificationId))).catch((err) => {
      console.warn('[related notification read failed]', err);
    });
  },

  reportError(result) {
    return {
      execution_status_duplicate_or_regression_not_allowed: '订单已确认，请刷新',
      execution_status_skip_not_allowed: '请按流程顺序操作',
      assignment_not_found_for_driver: '未找到司机任务',
      invalid_report_request: '确认请求无效'
    }[result && result.error] || '确认失败';
  },

  goDispatch() {
    if (!api.canAccess('dispatch')) {
      wx.showToast({ title: '当前账号没有派车权限', icon: 'none' });
      return;
    }
    wx.reLaunch({ url: '/package_dispatch/pages/dispatch/index' });
  },

  goFinance() {
    if (!api.canAccess('finance')) {
      wx.showToast({ title: '当前账号没有财务权限', icon: 'none' });
      return;
    }
    wx.reLaunch({ url: '/package_dispatch/pages/finance/index' });
  },

  goMap() {
    wx.reLaunch({ url: '/package_dispatch/pages/map/index' });
  },

  goInfo(e) {
    const datasetSection = e && e.currentTarget && e.currentTarget.dataset ? e.currentTarget.dataset.section : '';
    const focusSection = this.data.resourceFocus === 'drivers' || this.data.resourceFocus === 'vehicles'
      ? this.data.resourceFocus
      : '';
    const section = datasetSection || focusSection || 'vehicles';
    wx.setStorageSync('operations_info_section', section);
    wx.reLaunch({ url: '/package_dispatch/pages/info/index' });
  },

  goTask() {
    wx.reLaunch({ url: '/package_dispatch/pages/task/index' });
  },

  notificationTypeText(type) {
    return { dispatch_assigned: '派车通知', driver_report: '司机报告', incident: '异常通知', resource_reminder: '到期提醒', workflow_reminder: '流程提醒', workflow_suggestion: '派车建议', system: '系统通知' }[type] || type || '系统通知';
  },

  priorityText(priority) {
    return { critical: '紧急', high: '高', normal: '普通', low: '低' }[priority] || '普通';
  },

  togglePressureList() {
    const pressureExpanded = !this.data.pressureExpanded;
    this.setData({ pressureExpanded, visibleDriverStats: this.visibleDriverStats(this.data.driverStats, pressureExpanded) });
  },

  visibleDriverStats(driverStats, expanded) {
    return expanded ? driverStats : driverStats.slice(0, 3);
  },

  buildDriverStats(assignments, drivers) {
    const now = new Date();
    const today = this.formatDate(now);
    const monthPrefix = today.slice(0, 7);
    const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
    const byDriver = {};
    drivers.forEach((driver) => {
      byDriver[driver.id] = {
        driver_id: driver.id,
        driver_name: driver.name,
        today_orders: 0,
        month_orders: 0,
        month_active_days: new Set(),
        active_days: new Set()
      };
    });
    assignments.forEach((item) => {
      const driverId = item.driver_id;
      if (!byDriver[driverId]) return;
      const day = String(item.order_date || '').slice(0, 10);
      if (!day) return;
      byDriver[driverId].active_days.add(day);
      if (day === today) byDriver[driverId].today_orders += 1;
      if (day.indexOf(monthPrefix) === 0) {
        byDriver[driverId].month_orders += 1;
        byDriver[driverId].month_active_days.add(day);
      }
    });
    return Object.keys(byDriver)
      .map((key) => byDriver[key])
      .map((item) => {
        const continuous = this.continuousWorkDays(item.active_days, today);
        return Object.assign({}, item, {
          rest_days: Math.max(0, daysInMonth - item.month_active_days.size),
          continuous_days: continuous,
          alert: continuous > 10
        });
      })
      .filter((item) => item.continuous_days > 10)
      .sort((a, b) => b.continuous_days - a.continuous_days || b.month_orders - a.month_orders || b.today_orders - a.today_orders);
  },

  continuousWorkDays(activeDays, today) {
    let count = 0;
    const cursor = new Date(`${today}T00:00:00`);
    while (count < 31) {
      const key = this.formatDate(cursor);
      if (!activeDays.has(key)) break;
      count += 1;
      cursor.setDate(cursor.getDate() - 1);
    }
    return count;
  },

  formatDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  }
});

