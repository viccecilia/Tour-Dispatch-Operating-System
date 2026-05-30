const api = require('../../utils/api');

Page({
  data: {
    username: '',
    password: '',
    session: null,
    roleLabel: '',
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
    panelRows: [],
    driverStats: [],
    visibleDriverStats: [],
    pressureExpanded: false,
    notifications: [],
    error: '',
    loading: false,
    autoLoginTried: false
  },

  onShow() {
    api.useCloudBaseUrl();
    api.setActiveTab('/pages/index/index');
    const session = api.getSession();
    this.setSessionState(session);
    this.refreshTabBar();
    if (this.data.session) this.loadDashboard();
    else this.tryWechatAutoLogin();
  },

  tryWechatAutoLogin() {
    if (this.data.autoLoginTried) return;
    this.setData({ autoLoginTried: true, loading: true, error: '' });
    this.getWechatLoginCode()
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
    this.setData({
      session,
      roleLabel: labels[role] || '账号',
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
    const isPhone = /^\+?[\d\s-]{6,}$/.test(account);
    this.getWechatLoginCode()
      .then((wxCode) => (isPhone ? api.loginPhone(account, password, wxCode) : api.login(account, password, wxCode)))
      .catch(() => (isPhone ? api.loginPhone(account, password, '') : api.login(account, password, '')))
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
    const canViewDriverWorkload = this.data.canViewDriverWorkload;
    const session = this.data.session || {};
    const role = api.getRole(session);
    const canViewOperations = role === 'operations_manager';
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
    const vehicleTask = canViewOperations
      ? api.vehicles().catch(() => ({ vehicles: [] }))
      : Promise.resolve({ vehicles: [] });

    return Promise.all([
      api.dashboard(),
      notificationTask,
      (canViewDriverWorkload || canViewOperations) ? api.assignments().catch(() => ({ assignments: [] })) : Promise.resolve({ assignments: [] }),
      (canViewDriverWorkload || canViewOperations) ? api.drivers().catch(() => ({ drivers: [] })) : Promise.resolve({ drivers: [] }),
      driverTask,
      workbenchTask,
      profileTask,
      vehicleTask
    ])
      .then(([dashboard, notifications, assignments, drivers, driverAssignments, workbench, profile, vehicles]) => {
        const allAssignments = assignments.assignments || [];
        const allDrivers = drivers.drivers || [];
        const allVehicles = vehicles.vehicles || [];
        const driverStats = canViewDriverWorkload ? this.buildDriverStats(allAssignments, allDrivers) : [];
        const driverRows = (driverAssignments.assignments || []).map((item) => this.decorateAssignment(item));
        const pendingRows = driverRows.filter((item) => item.rawStatus === 'assigned');
        const homeOrderRows = role === 'driver' ? pendingRows : driverRows;
        const exceptionRows = driverRows.filter((item) => ['incident', 'exception', 'delayed'].indexOf(String(item.order_status || item.status || '')) >= 0);
        const dueRows = this.buildDueRows(profile.driver);
        const unreadRows = [
          ...dueRows,
          ...(notifications.notifications || [])
            .filter((item) => item.status !== 'read')
            .filter((item) => !this.isSuppressedDriverNotification(item))
            .map((item) => this.decorateNotification(item))
        ];
        const nextDashboard = role === 'driver'
          ? {
            ...dashboard,
            counts: {
              ...(dashboard.counts || {}),
              today_orders: homeOrderRows.length,
              pending_confirmations: pendingRows.length,
              exception_orders: exceptionRows.length,
              notifications_unread: unreadRows.length
            }
          }
          : dashboard;
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
        const panel = this.buildPanel(this.data.panelMode, homeOrderRows, pendingRows, exceptionRows, unreadRows);
        const operationsDetail = role === 'operations_manager' && this.data.operationsSection === 'notifications'
          ? this.buildOperationsNotificationDetail(unreadRows)
          : operations.detail;
        this.setData({
          dashboard: nextDashboard,
          driverAssignments: driverRows,
          notifications: unreadRows,
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
          panelRows: panel.rows,
          driverStats,
          visibleDriverStats: this.visibleDriverStats(driverStats, this.data.pressureExpanded),
          loading: false
        });
      })
      .catch(() => this.setData({ loading: false, error: '无法加载移动首页。' }));
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
    const driverRows = (drivers || []).map((driver) => {
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
        driverTotal: drivers.length,
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
    return {
      ...item,
      rawStatus,
      id: item.assignment_id || item.id,
      title: item.oid || item.order_id || '订单',
      meta: `${item.order_date || '-'} ${item.start_time || '--:--'} · ${this.statusText(rawStatus)}`,
      body: `${item.pickup_location || '-'} -> ${item.dropoff_location || '-'}`,
      action: rawStatus === 'assigned' ? 'confirm' : 'task',
      actionText: rawStatus === 'assigned' ? '确认' : '查看'
    };
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
    if (days === null || days > 30) return null;
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
      title: item.title || this.notificationTypeText(item.notification_type),
      meta: `${this.notificationTypeText(item.notification_type)} · ${this.priorityText(item.priority)}`,
      body: item.body || '',
      priority: item.priority || 'normal',
      action: 'detail',
      actionText: '详情',
      raw: item
    };
  },

  buildPanel(mode, orders, pending, exceptions, unread) {
    const config = {
      orders: { title: '待确认派单', hint: '确认后首页不再显示，调度端会收到司机已接单回执。', rows: orders },
      pending: { title: '待确认派单', hint: '确认后订单状态会变为已接单。', rows: pending },
      exceptions: { title: '异常订单', hint: '只显示需要司机关注的异常。', rows: exceptions },
      unread: { title: '未读通知', hint: '体检、驾照和需要司机处理的通知显示在这里。', rows: unread }
    };
    return config[mode] || config.orders;
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
    return { label: '未出库', hint: '确认接单后进入任务页完成出库。' };
  },

  statusText(status) {
    return { assigned: '待确认', confirmed: '已接单', departed: '已出库', arrived: '已到达', in_service: '行驶中', completed: '已完成', returned: '已入库' }[status] || status || '-';
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
    const allOrders = this.data.driverAssignments || [];
    const pending = allOrders.filter((item) => item.rawStatus === 'assigned');
    const orders = this.data.canDriverTasks ? pending : allOrders;
    const exceptions = allOrders.filter((item) => ['incident', 'exception', 'delayed'].indexOf(String(item.order_status || item.status || '')) >= 0);
    const unread = this.data.notifications || [];
    const panel = this.buildPanel(mode, orders, pending, exceptions, unread);
    this.setData({ panelMode: mode, panelTitle: panel.title, panelHint: panel.hint, panelRows: panel.rows });
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
    if (item.action === 'profile') {
      wx.reLaunch({ url: '/pages/profile/index' });
      return;
    }
    if (item.action === 'map') {
      this.goMap();
      return;
    }
    wx.showModal({
      title: item.title || '通知详情',
      content: [item.meta, item.body].filter(Boolean).join('\n'),
      showCancel: false,
      confirmText: '知道了'
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
      wx.reLaunch({ url: '/pages/profile/index' });
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
          this.loadDashboard();
        }).catch(() => {
          wx.showToast({ title: '确认失败', icon: 'none' });
        });
      }
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
    wx.reLaunch({ url: '/pages/dispatch/index' });
  },

  goFinance() {
    if (!api.canAccess('finance')) {
      wx.showToast({ title: '当前账号没有财务权限', icon: 'none' });
      return;
    }
    wx.reLaunch({ url: '/pages/finance/index' });
  },

  goMap() {
    wx.reLaunch({ url: '/pages/map/index' });
  },

  goInfo(e) {
    const section = e && e.currentTarget && e.currentTarget.dataset ? e.currentTarget.dataset.section : '';
    if (section) wx.setStorageSync('operations_info_section', section);
    wx.reLaunch({ url: '/pages/info/index' });
  },

  goTask() {
    wx.reLaunch({ url: '/pages/task/index' });
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
      byDriver[driver.id] = { driver_id: driver.id, driver_name: driver.name, today_orders: 0, month_orders: 0, active_days: new Set() };
    });
    assignments.forEach((item) => {
      const driverId = item.driver_id;
      if (!byDriver[driverId]) return;
      const day = item.order_date || '';
      if (day === today) byDriver[driverId].today_orders += 1;
      if (day.indexOf(monthPrefix) === 0) {
        byDriver[driverId].month_orders += 1;
        byDriver[driverId].active_days.add(day);
      }
    });
    return Object.values(byDriver)
      .map((item) => {
        const continuous = this.continuousWorkDays(item.active_days, today);
        return { ...item, rest_days: Math.max(0, daysInMonth - item.active_days.size), continuous_days: continuous, alert: continuous > 13 };
      })
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
