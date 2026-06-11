const api = require('../../utils/api');

const VIEW_TITLES = {
  today: '今日金额',
  pending: '待确认费用',
  advance: '司机垫付',
  collect: '司机代收',
  orders: '订单金额'
};

function money(value) {
  const amount = Number(value || 0);
  return `¥${amount.toLocaleString()}`;
}

function normalizeDate(value) {
  return String(value || '').slice(0, 10);
}

function routeText(item) {
  return [item.pickup_location, item.dropoff_location].filter(Boolean).join(' -> ') || '-';
}

function orderTitle(order) {
  return order.oid || order.order_id || '-';
}

function expenseKindLabel(kind) {
  return kind === 'collect' ? '司机代收' : '司机垫付';
}

function expenseStatusLabel(status) {
  const map = {
    unsubmitted: '未提交',
    submitted: '待确认',
    in_hand: '待确认',
    confirmed: '已确认',
    rejected: '已驳回'
  };
  return map[status] || status || '-';
}

Page({
  data: {
    activeView: 'pending',
    summary: {},
    cards: [],
    orders: [],
    expenses: [],
    visibleOrders: [],
    visibleExpenses: [],
    activeTitle: VIEW_TITLES.pending,
    activeHint: '司机提交的垫付和代收费用会在这里确认。',
    message: '',
    loading: false
  },

  onShow() {
    api.setActiveTab('/package_dispatch/pages/finance/index');
    this.refreshTabBar();
    if (!api.canAccess('finance')) {
      wx.showToast({ title: '当前账号无财务权限', icon: 'none' });
      wx.redirectTo({ url: '/package_dispatch/pages/home/index' });
      return;
    }
    this.loadFinance();
  },

  refreshTabBar() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().refresh();
    }
  },

  setView(event) {
    const view = event.currentTarget.dataset.view || 'pending';
    this.updateVisible(view);
  },

  loadFinance() {
    this.setData({ loading: true, message: '' });
    Promise.all([
      api.financeSummary().catch(() => ({})),
      api.financeLedger().catch(() => ({ orders: [] })),
      api.financeDriverExpenses().catch(() => ({ expenses: [], summary: {} }))
    ])
      .then(([summary, ledger, expenseResult]) => {
        const expenseSummary = {
          ...(summary.driver_expense_summary || {}),
          ...(expenseResult.summary || {})
        };
        const today = normalizeDate(summary.date || new Date().toISOString());
        const orders = (ledger.orders || summary.orders || []).map((item) => ({
          ...item,
          displayId: orderTitle(item),
          displayDate: `${item.order_date || '-'} ${item.start_time || ''}`.trim(),
          displayRoute: routeText(item),
          displayAgency: item.agency_name || '未填旅行社',
          displayDriver: item.driver_name || '未派司机',
          displayAmount: money(item.price || item.total_amount || 0),
          isToday: normalizeDate(item.order_date) === today
        }));
        const expenses = (expenseResult.expenses || []).map((item) => ({
          ...item,
          displayId: item.oid || item.order_id || item.assignment_id || `费用 #${item.id}`,
          displayKind: expenseKindLabel(item.expense_kind),
          displayStatus: expenseStatusLabel(item.submit_status),
          displayDate: `${item.order_date || item.created_at || '-'} ${item.start_time || ''}`.trim(),
          displayRoute: routeText(item),
          displayDriver: item.driver_name || item.driver_code || '未填司机',
          displayAmount: money(item.amount || 0),
          isPending: item.submit_status === 'submitted' || item.submit_status === 'in_hand'
        }));
        const enrichedSummary = {
          ...summary,
          ...expenseSummary,
          today_amount_label: money(summary.today_amount || 0),
          pending_expense_amount_label: money(expenseSummary.driver_expense_pending_amount || 0),
          advance_amount_label: money(expenseSummary.driver_advance_pending_amount || 0),
          collect_amount_label: money(expenseSummary.driver_collect_pending_amount || 0),
          total_amount_label: money(summary.total_amount || 0),
          order_count: summary.order_count || orders.length
        };
        this.setData({
          summary: enrichedSummary,
          orders,
          expenses,
          cards: this.buildCards(enrichedSummary),
          loading: false,
          message: ''
        });
        this.updateVisible(this.data.activeView);
      })
      .catch(() => {
        this.setData({ loading: false, message: '无法加载财务数据，请稍后重试。' });
      });
  },

  buildCards(summary) {
    return [
      { view: 'today', label: '今日金额', value: summary.today_amount_label, tone: 'normal' },
      { view: 'pending', label: '待确认费用', value: summary.pending_expense_amount_label, tone: 'warning' },
      { view: 'advance', label: '司机垫付', value: summary.advance_amount_label, tone: 'normal' },
      { view: 'collect', label: '司机代收', value: summary.collect_amount_label, tone: 'success' }
    ];
  },

  updateVisible(view) {
    const expenses = this.data.expenses || [];
    const orders = this.data.orders || [];
    let visibleExpenses = [];
    let visibleOrders = [];
    let hint = '';

    if (view === 'today') {
      visibleOrders = orders.filter((item) => item.isToday).slice(0, 50);
      hint = '今天开始的订单金额汇总。';
    } else if (view === 'advance') {
      visibleExpenses = expenses.filter((item) => item.expense_kind === 'advance').slice(0, 50);
      hint = '司机垫付后提交的报销费用。';
    } else if (view === 'collect') {
      visibleExpenses = expenses.filter((item) => item.expense_kind === 'collect').slice(0, 50);
      hint = '司机代收后需要上交给公司的款项。';
    } else if (view === 'orders') {
      visibleOrders = orders.slice(0, 50);
      hint = '所有订单金额流水。';
    } else {
      visibleExpenses = expenses.filter((item) => item.isPending).slice(0, 50);
      hint = '司机提交后等待财务确认的费用。';
    }

    this.setData({
      activeView: view,
      activeTitle: VIEW_TITLES[view] || VIEW_TITLES.pending,
      activeHint: hint,
      visibleOrders,
      visibleExpenses
    });
  }
});

