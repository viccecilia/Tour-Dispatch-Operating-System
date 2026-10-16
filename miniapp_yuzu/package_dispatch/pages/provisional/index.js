const api = require('../../utils/api');

const LOCAL_DRAFT_KEY = 'driver_provisional_unsynced_v1';

function requestId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function today() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function emptyForm() {
  return {
    business_date: today(),
    service_kind: 'airport_transfer',
    service_source: 'carrier_instruction',
    authorization_source: 'carrier_admin_phone',
    authorization_evidence: '',
    actual_pickup_location: '',
    actual_pickup_at: '',
    actual_dropoff_location: '',
    actual_dropoff_at: '',
    pickup_odometer_km: '',
    dropoff_odometer_km: '',
    note: ''
  };
}

Page({
  data: {
    role: '',
    isDriver: false,
    isCarrierAdmin: false,
    loading: false,
    saving: false,
    tasks: [],
    selectedTask: null,
    form: emptyForm(),
    editorOpen: false,
    localUnsynced: false,
    message: '',
    reviewReason: '',
    linkedOrderId: '',
    priceForm: { price_jpy: '', driver_salary_jpy: '', driver_settlement_amount: '', driver_settlement_status: 'pending' },
    formalOrder: null,
    financeSummary: null,
    settlementLabels: ['待处理', '未结算', '已结算', '已支付'],
    settlementStatusIndex: 0
  },

  onShow() {
    const session = api.getSession();
    const role = api.getRole(session);
    const user = (session && session.user) || {};
    const scope = user.account_scope || (role === 'driver' ? 'driver' : 'carrier');
    const isDriver = role === 'driver';
    const isCarrierAdmin = role === 'admin' && scope === 'carrier';
    if (!isDriver && !isCarrierAdmin) {
      wx.showModal({ title: '无权访问', content: '只有司机本人或所属车公司管理员可使用此页面。', showCancel: false, success: () => wx.navigateBack() });
      return;
    }
    this.setData({ role, isDriver, isCarrierAdmin });
    if (isDriver) this.restoreLocalDraft();
    this.loadTasks();
  },

  onPullDownRefresh() {
    this.loadTasks().finally(() => wx.stopPullDownRefresh());
  },

  restoreLocalDraft() {
    const local = wx.getStorageSync(LOCAL_DRAFT_KEY);
    if (local && local.form) this.setData({ form: local.form, editorOpen: true, localUnsynced: true, message: '发现本机未同步内容，请确认后重试保存。' });
  },

  loadTasks() {
    this.setData({ loading: true, message: '' });
    const loader = this.data.isDriver ? api.driverProvisionalTasks() : api.companyProvisionalTasks();
    const finance = this.data.isCarrierAdmin ? api.companyProvisionalFinanceSummary().catch(() => null) : Promise.resolve(null);
    return Promise.all([loader, finance])
      .then(([result, financeResult]) => this.setData({
        tasks: (result.tasks || []).map((item) => this.decorateTask(item)),
        financeSummary: financeResult,
        loading: false
      }))
      .catch((err) => this.setData({ loading: false, message: api.errorMessage(err) }));
  },

  decorateTask(item) {
    const labels = {
      draft: '草稿', pending_company_confirmation: '待公司确认', needs_information: '需补充',
      approved_new_order: '已转正式', approved_linked_order: '已关联正式单', rejected: '已驳回'
    };
    return Object.assign({}, item, {
      statusLabel: labels[item.status] || item.status,
      routeText: `${item.actual_pickup_location || '未填上车点'} → ${item.actual_dropoff_location || '未填下车点'}`,
      canEdit: ['draft', 'needs_information'].indexOf(item.status) >= 0,
      pending: item.status === 'pending_company_confirmation',
      approved: ['approved_new_order', 'approved_linked_order'].indexOf(item.status) >= 0
    });
  },

  newTask() {
    this.setData({ selectedTask: null, form: emptyForm(), editorOpen: true, localUnsynced: false, message: '' });
  },

  closeEditor() {
    this.setData({ editorOpen: false, selectedTask: null, formalOrder: null, message: '' });
  },

  onFormInput(e) {
    const key = e.currentTarget.dataset.key;
    this.setData({ [`form.${key}`]: e.detail.value });
  },

  onDateChange(e) {
    this.setData({ 'form.business_date': e.detail.value });
  },

  openTask(e) {
    const taskId = e.currentTarget.dataset.id;
    const loader = this.data.isDriver ? api.driverProvisionalTask(taskId) : api.companyProvisionalTask(taskId);
    this.setData({ loading: true, message: '' });
    loader.then((result) => {
      const task = this.decorateTask(result.task);
      this.setData({
        selectedTask: task,
        form: Object.assign(emptyForm(), {
          business_date: task.business_date,
          service_kind: task.service_kind || 'other',
          service_source: task.service_source || '',
          authorization_source: task.authorization_source || '',
          authorization_evidence: task.authorization_evidence || '',
          actual_pickup_location: task.actual_pickup_location || '',
          actual_pickup_at: task.actual_pickup_at || '',
          actual_dropoff_location: task.actual_dropoff_location || '',
          actual_dropoff_at: task.actual_dropoff_at || '',
          pickup_odometer_km: task.pickup_odometer_km === null || task.pickup_odometer_km === undefined ? '' : String(task.pickup_odometer_km),
          dropoff_odometer_km: task.dropoff_odometer_km === null || task.dropoff_odometer_km === undefined
            ? (task.odometer_km === null || task.odometer_km === undefined ? '' : String(task.odometer_km))
            : String(task.dropoff_odometer_km),
          note: task.note || ''
        }),
        editorOpen: true,
        formalOrder: result.formal_order || null,
        priceForm: {
          price_jpy: result.formal_order && result.formal_order.price_jpy !== null ? String(result.formal_order.price_jpy) : '',
          driver_salary_jpy: result.formal_order && result.formal_order.driver_salary_jpy !== null ? String(result.formal_order.driver_salary_jpy) : '',
          driver_settlement_amount: result.formal_order && result.formal_order.driver_settlement_amount !== null ? String(result.formal_order.driver_settlement_amount) : '',
          driver_settlement_status: result.formal_order && result.formal_order.driver_settlement_status || 'pending'
        },
        settlementStatusIndex: Math.max(0, ['pending', 'unsettled', 'settled', 'paid'].indexOf(result.formal_order && result.formal_order.driver_settlement_status || 'pending')),
        loading: false
      });
    }).catch((err) => this.setData({ loading: false, message: api.errorMessage(err) }));
  },

  payloadFromForm() {
    const form = this.data.form;
    return Object.assign({}, form, {
      pickup_odometer_km: form.pickup_odometer_km === '' ? null : Number(form.pickup_odometer_km),
      dropoff_odometer_km: form.dropoff_odometer_km === '' ? null : Number(form.dropoff_odometer_km)
    });
  },

  saveDraft() {
    if (!this.data.isDriver || this.data.saving) return Promise.resolve(null);
    const task = this.data.selectedTask;
    const payload = Object.assign(this.payloadFromForm(), {
      client_request_id: requestId(task ? 'provisional-update' : 'provisional-create')
    });
    if (task) payload.expected_revision = task.revision;
    this.setData({ saving: true, message: '' });
    const action = task
      ? api.updateDriverProvisionalTask(task.provisional_task_id, payload)
      : api.createDriverProvisionalTask(payload);
    return action.then((result) => {
      wx.removeStorageSync(LOCAL_DRAFT_KEY);
      const saved = this.decorateTask(result.task);
      this.setData({ selectedTask: saved, localUnsynced: false, saving: false, message: '草稿已同步保存。' });
      return this.loadTasks().then(() => saved);
    }).catch((err) => {
      wx.setStorageSync(LOCAL_DRAFT_KEY, { form: this.data.form, saved_at: new Date().toISOString() });
      this.setData({ saving: false, localUnsynced: true, message: `${api.errorMessage(err)}；内容仅保存在本机，尚未同步。` });
      return null;
    });
  },

  submitTask() {
    const submitSaved = (task) => {
      if (!task) return;
      this.setData({ saving: true, message: '' });
      api.submitDriverProvisionalTask(task.provisional_task_id, {
        client_request_id: requestId('provisional-submit'), expected_revision: task.revision
      }).then((result) => {
        this.setData({ selectedTask: this.decorateTask(result.task), saving: false, message: '已提交所属车公司确认。' });
        this.loadTasks();
      }).catch((err) => this.setData({ saving: false, message: api.errorMessage(err) }));
    };
    this.saveDraft().then(submitSaved);
  },

  onReviewReason(e) { this.setData({ reviewReason: e.detail.value }); },
  onLinkedOrder(e) { this.setData({ linkedOrderId: e.detail.value }); },

  reviewTask(e) {
    const action = e.currentTarget.dataset.action;
    const task = this.data.selectedTask;
    if (!task || !this.data.isCarrierAdmin || this.data.saving) return;
    const payload = {
      client_request_id: requestId(`provisional-${action}`),
      expected_revision: task.revision,
      reason: this.data.reviewReason
    };
    if (action === 'approve-link') payload.linked_order_id = this.data.linkedOrderId;
    this.setData({ saving: true, message: '' });
    api.reviewCompanyProvisionalTask(task.provisional_task_id, action, payload)
      .then((result) => {
        this.setData({ saving: false, selectedTask: this.decorateTask(result.task), formalOrder: result.formal_order || null, message: '审核结果已保存。' });
        return this.loadTasks();
      })
      .catch((err) => this.setData({ saving: false, message: api.errorMessage(err) }));
  },

  onPriceInput(e) { this.setData({ [`priceForm.${e.currentTarget.dataset.key}`]: e.detail.value }); },
  onSettlementStatus(e) {
    const index = Number(e.detail.value || 0);
    this.setData({ settlementStatusIndex: index, 'priceForm.driver_settlement_status': ['pending', 'unsettled', 'settled', 'paid'][index] || 'pending' });
  },

  savePricing() {
    const task = this.data.selectedTask;
    if (!task || !this.data.isCarrierAdmin || this.data.saving) return;
    const source = this.data.priceForm;
    const nullableNumber = (value) => value === '' ? null : Number(value);
    this.setData({ saving: true, message: '' });
    const pricingPayload = {
      client_request_id: requestId('provisional-pricing'),
      expected_revision: task.revision,
      price_jpy: nullableNumber(source.price_jpy),
      driver_salary_jpy: nullableNumber(source.driver_salary_jpy),
      driver_settlement_status: source.driver_settlement_status,
      reason: this.data.reviewReason || 'carrier admin pricing update'
    };
    if (source.driver_settlement_amount !== '') pricingPayload.driver_settlement_amount = Number(source.driver_settlement_amount);
    api.priceCompanyProvisionalTask(task.provisional_task_id, pricingPayload).then((result) => {
      const suffix = result.settlement_adjustment_required ? ` 已结算差额 ${result.settled_delta_jpy} 円需另行处理。` : '';
      this.setData({ saving: false, selectedTask: this.decorateTask(result.task), formalOrder: result.formal_order, message: `定价与司机应得金额已保存。${suffix}` });
      this.loadTasks();
    }).catch((err) => this.setData({ saving: false, message: api.errorMessage(err) }));
  }
});
