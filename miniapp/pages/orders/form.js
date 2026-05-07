const api = require('../../utils/api');

const emptyForm = {
  order_date: '',
  start_time: '',
  end_time: '',
  pickup_location: '',
  dropoff_location: '',
  order_type: '',
  vehicle_type: '',
  passenger_count: '',
  luggage_count: '',
  guest_name: '',
  guest_contact: '',
  agency_name: '',
  price: '',
  remark: '',
  dispatch_status: 'unassigned',
  settlement_status: 'pending'
};

Page({
  data: {
    id: '',
    form: { ...emptyForm },
    saving: false
  },

  onLoad(options) {
    if (!options.id) {
      return;
    }
    this.setData({ id: options.id });
    api.getOrder(options.id).then((res) => {
      if (res.order) {
        this.setData({ form: { ...emptyForm, ...res.order } });
      } else {
        wx.showToast({ title: '订单加载失败', icon: 'none' });
      }
    });
  },

  onInput(event) {
    const key = event.currentTarget.dataset.key;
    this.setData({ [`form.${key}`]: event.detail.value });
  },

  onDateChange(event) {
    this.setData({ 'form.order_date': event.detail.value });
  },

  onStartTimeChange(event) {
    this.setData({ 'form.start_time': event.detail.value });
  },

  onEndTimeChange(event) {
    this.setData({ 'form.end_time': event.detail.value });
  },

  validate() {
    const form = this.data.form;
    if (!form.order_date || !form.pickup_location || !form.dropoff_location) {
      wx.showToast({ title: '请填写日期、起点、终点', icon: 'none' });
      return false;
    }
    return true;
  },

  onSave() {
    if (!this.validate()) {
      return;
    }
    this.setData({ saving: true });
    const action = this.data.id
      ? api.updateOrder(this.data.id, this.data.form)
      : api.createOrder(this.data.form);

    action.then((res) => {
      this.setData({ saving: false });
      if (res.error) {
        wx.showToast({ title: '保存失败', icon: 'none' });
        return;
      }
      wx.showToast({ title: '保存成功' });
      setTimeout(() => wx.navigateBack(), 500);
    }).catch(() => {
      this.setData({ saving: false });
      wx.showToast({ title: '保存失败', icon: 'none' });
    });
  }
});
