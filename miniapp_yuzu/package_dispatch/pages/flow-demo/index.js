const SCREENS = [
  { key: 'plan', label: '日配' },
  { key: 'publish', label: '发布' },
  { key: 'driver', label: '司机' },
  { key: 'change', label: '变更' }
];

Page({
  data: {
    screens: SCREENS,
    active: 'plan',
    published: false,
    editing: false,
    editingDriver: '',
    driverConfirmed: false,
    reportStep: 1,
    changeApplied: false,
    drivers: [
      { name: '田中', vehicle: '大阪 510 あ 1450', state: '已核对', tone: 'ok', orders: [
        { time: '08:10', route: '大阪市内 → KIX T1', type: '送机', flag: '17000 円' },
        { time: '15:15', route: 'KIX T1 → 大阪市内', type: '接机', flag: 'KE721' }
      ] },
      { name: '佐藤', vehicle: '大阪 500 す 0719', state: '待补地点', tone: 'warn', orders: [
        { time: '10:00', route: '京都 → 奈良 → 大阪', type: '包车', flag: '3代' },
        { time: '18:30', route: '大阪市内 → 关西机场', type: '送机', flag: '待确认' }
      ] }
    ]
  },

  switchScreen(event) {
    this.setData({ active: event.currentTarget.dataset.key });
  },

  publish() {
    this.setData({ published: true, editing: false, active: 'publish' });
  },

  startEditing() {
    this.setData({ editing: true, editingDriver: '' });
  },

  editDriver(event) {
    this.setData({ editingDriver: event.currentTarget.dataset.name });
  },

  finishEditing() {
    this.setData({ editing: false, editingDriver: '' });
  },

  confirmReceipt() {
    this.setData({ driverConfirmed: true });
  },

  nextReportStep() {
    this.setData({ reportStep: Math.min(this.data.reportStep + 1, 3) });
  },

  applyChange() {
    this.setData({ changeApplied: true });
  }
});
