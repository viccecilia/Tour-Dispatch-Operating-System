const api = require('../../utils/api');

Page({
  data: {
    loading: false,
    loadError: '',
    drivers: [],
    vehicles: [],
    driverForm: {
      name: '',
      phone: '',
      status: 'available'
    },
    vehicleForm: {
      plate_number: '',
      vehicle_type: '',
      seat_count: '',
      status: 'available'
    },
    driverStatuses: [
      { label: '可用', value: 'available' },
      { label: '休息', value: 'resting' },
      { label: '停用', value: 'inactive' }
    ],
    vehicleStatuses: [
      { label: '可用', value: 'available' },
      { label: '保养', value: 'maintenance' },
      { label: '停用', value: 'inactive' }
    ]
  },

  onShow() {
    this.loadResources();
  },

  loadResources() {
    this.setData({ loading: true, loadError: '' });
    Promise.all([api.listDrivers(), api.listVehicles()])
      .then(([driverRes, vehicleRes]) => {
        this.setData({
          drivers: driverRes.drivers || [],
          vehicles: vehicleRes.vehicles || [],
          loading: false
        });
      })
      .catch(() => {
        this.setData({ loading: false, loadError: '车辆人员加载失败' });
      });
  },

  onDriverInput(event) {
    this.setData({ [`driverForm.${event.currentTarget.dataset.key}`]: event.detail.value });
  },

  onVehicleInput(event) {
    this.setData({ [`vehicleForm.${event.currentTarget.dataset.key}`]: event.detail.value });
  },

  onDriverStatusChange(event) {
    this.setData({ 'driverForm.status': this.data.driverStatuses[Number(event.detail.value)].value });
  },

  onVehicleStatusChange(event) {
    this.setData({ 'vehicleForm.status': this.data.vehicleStatuses[Number(event.detail.value)].value });
  },

  addDriver() {
    if (!this.data.driverForm.name) {
      wx.showToast({ title: '请填写司机姓名', icon: 'none' });
      return;
    }
    api.createDriver(this.data.driverForm).then((res) => {
      if (res.error) {
        wx.showToast({ title: '新增司机失败', icon: 'none' });
        return;
      }
      this.setData({ driverForm: { name: '', phone: '', status: 'available' } });
      this.loadResources();
    });
  },

  addVehicle() {
    if (!this.data.vehicleForm.plate_number) {
      wx.showToast({ title: '请填写车牌号', icon: 'none' });
      return;
    }
    api.createVehicle(this.data.vehicleForm).then((res) => {
      if (res.error) {
        wx.showToast({ title: '新增车辆失败', icon: 'none' });
        return;
      }
      this.setData({ vehicleForm: { plate_number: '', vehicle_type: '', seat_count: '', status: 'available' } });
      this.loadResources();
    });
  },

  setDriverStatus(event) {
    api.updateDriver(event.currentTarget.dataset.id, { status: event.currentTarget.dataset.status }).then(() => {
      this.loadResources();
    });
  },

  setVehicleStatus(event) {
    api.updateVehicle(event.currentTarget.dataset.id, { status: event.currentTarget.dataset.status }).then(() => {
      this.loadResources();
    });
  }
});
