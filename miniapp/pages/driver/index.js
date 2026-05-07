const api = require('../../utils/api');

const NEXT_ACTION = {
  assigned: { type: 'confirm_order', label: '确认订单' },
  confirmed: { type: 'depart_yard', label: '出库' },
  departed: { type: 'arrive_pickup', label: '到达' },
  arrived: { type: 'start_service', label: '开始服务' },
  in_service: { type: 'complete_order', label: '完成订单' },
  completed: { type: 'return_yard', label: '归库' }
};

Page({
  data: {
    driverId: 1,
    assignments: [],
    selected: null,
    note: '',
    locationText: '',
    latitude: '',
    longitude: ''
  },

  onLoad(options) {
    if (options.driver_id) {
      this.setData({ driverId: Number(options.driver_id) });
    }
    this.loadAssignments();
  },

  loadAssignments() {
    api.driverAssignments(this.data.driverId).then((res) => {
      this.setData({ assignments: res.assignments || [] });
    });
  },

  onDriverInput(event) {
    this.setData({ driverId: Number(event.detail.value || 0) });
  },

  onSwitchDriver() {
    this.setData({ selected: null });
    this.loadAssignments();
  },

  onSelect(event) {
    api.driverAssignmentDetail(this.data.driverId, event.currentTarget.dataset.id).then((res) => {
      if (res.assignment) {
        this.setSelected(res.assignment);
      } else {
        wx.showToast({ title: '无权查看该订单', icon: 'none' });
      }
    });
  },

  onInput(event) {
    this.setData({ [event.currentTarget.dataset.key]: event.detail.value });
  },

  onReport() {
    const assignment = this.data.selected;
    if (!assignment) {
      return;
    }
    const action = NEXT_ACTION[assignment.execution_status || 'assigned'];
    if (!action) {
      wx.showToast({ title: '当前无下一步动作', icon: 'none' });
      return;
    }
    api.submitDriverReport({
      driver_id: this.data.driverId,
      assignment_id: assignment.assignment_id,
      report_type: action.type,
      latitude: this.data.latitude,
      longitude: this.data.longitude,
      location_text: this.data.locationText,
      note: this.data.note
    }).then((res) => {
      if (!res.success) {
        wx.showToast({ title: '报备失败', icon: 'none' });
        return;
      }
      wx.showToast({ title: '报备成功' });
      this.loadAssignments();
      api.driverAssignmentDetail(this.data.driverId, assignment.assignment_id).then((detail) => {
        this.setSelected(detail.assignment);
      });
    });
  },

  setSelected(assignment) {
    const status = assignment ? assignment.execution_status || 'assigned' : 'assigned';
    this.setData({
      selected: assignment,
      nextActionLabel: (NEXT_ACTION[status] || {}).label || '流程已结束',
      note: '',
      locationText: '当前位置已确认',
      latitude: '',
      longitude: ''
    });
  }
});
