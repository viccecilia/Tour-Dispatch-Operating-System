const api = require('../../utils/api');

function today() {
  return new Date().toISOString().slice(0, 10);
}

Page({
  data: {
    loading: false,
    view: 'day',
    date: today(),
    views: [
      { key: 'day', label: '24h' },
      { key: 'week', label: '7日' },
      { key: 'month', label: '本月' }
    ],
    vehicles: [],
    vehicleIndex: 0,
    selectedVehicleId: '',
    items: [],
    legend: [],
    monthSummary: [],
    detail: null,
    error: ''
  },

  onLoad() {
    this.loadCalendar();
  },

  loadCalendar() {
    this.setData({ loading: true, error: '' });
    api.dispatchCalendar({
      view: this.data.view,
      date: this.data.date,
      vehicle_id: this.data.selectedVehicleId
    }).then((res) => {
      if (!res.ok) {
        throw new Error(res.error || 'calendar_failed');
      }
      const vehicles = [{ id: '', plate_number: '全部车辆' }].concat(res.vehicles || []);
      this.setData({
        loading: false,
        items: res.items || [],
        vehicles,
        legend: res.legend || [],
        monthSummary: res.month_summary || []
      });
    }).catch(() => {
      this.setData({ loading: false, error: '日历加载失败' });
    });
  },

  onDateChange(event) {
    this.setData({ date: event.detail.value });
    this.loadCalendar();
  },

  onViewChange(event) {
    const view = event.currentTarget.dataset.view;
    this.setData({ view, detail: null });
    this.loadCalendar();
  },

  onVehicleChange(event) {
    const index = Number(event.detail.value);
    const vehicle = this.data.vehicles[index];
    this.setData({
      vehicleIndex: index,
      selectedVehicleId: vehicle ? vehicle.id : ''
    });
    this.loadCalendar();
  },

  onItemTap(event) {
    api.dispatchCalendarDetail(event.currentTarget.dataset.id).then((res) => {
      if (res.ok) {
        this.setData({ detail: res.detail });
      } else {
        wx.showToast({ title: '详情加载失败', icon: 'none' });
      }
    });
  },

  onMonthDayTap(event) {
    this.setData({
      view: 'day',
      date: event.currentTarget.dataset.date,
      detail: null
    });
    this.loadCalendar();
  },

  closeDetail() {
    this.setData({ detail: null });
  }
});
