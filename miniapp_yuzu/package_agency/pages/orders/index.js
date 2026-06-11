const api = require('../../utils/api');

const SAMPLE_TEXT = [
  '2026-06-10 09:30 关西机场T1 -> Osaka Namba Hotel 4人 5件 Hiace 客人Zhang 080-1111-2222 52000',
  '2026-06-10 14:00 Osaka Namba Hotel -> Kansai International Airport T1 3人 3件 Alphard 客人Li 080-2222-3333 68000',
  '6.02 09:00 京都往返天桥立美山 包车 3代 绿1900 Mico Yamamoto'
].join('\n');

Page({
  data: {
    rawText: SAMPLE_TEXT,
    parsedOrders: [],
    pickupRows: [],
    dropoffRows: [],
    charterRows: [],
    selectedParsedCount: 0,
    parseLoading: false,
    createLoading: false,
    message: ''
  },

  onShow() {
    const session = api.getSession();
    if (!session) {
      wx.redirectTo({ url: '/package_agency/pages/home/index' });
      return;
    }
    const role = session.account ? String(session.account.role || '').toLowerCase() : '';
    if (role.indexOf('guide') >= 0 || role.indexOf('导游') >= 0 || role.indexOf('service') >= 0 || role.indexOf('support') >= 0 || role.indexOf('customer') >= 0 || role.indexOf('客服') >= 0) {
      wx.showToast({ title: '当前角色不开放入单', icon: 'none' });
      wx.redirectTo({ url: '/package_agency/pages/home/index' });
      return;
    }
    const tabBar = typeof this.getTabBar === 'function' && this.getTabBar();
    if (tabBar) tabBar.setData({ selected: 1 });
    wx.setNavigationBarTitle({
      title: session.agency && session.agency.name ? session.agency.name : '订单录入'
    });
  },

  onTextInput(e) {
    this.setData({ rawText: e.detail.value });
  },

  fillSample() {
    this.setData({ rawText: SAMPLE_TEXT, parsedOrders: [], message: '' });
  },

  parseOrders() {
    if (!this.data.rawText.trim()) {
      wx.showToast({ title: '请输入订单文本', icon: 'none' });
      return;
    }
    this.setData({ parseLoading: true, message: '' });
    api.parseOrders(this.data.rawText, 'mixed_batch', true)
      .then((res) => {
        const parsedOrders = (res.orders || []).map((item, index) => this.decorateOrder(item, index));
        this.applyParsedOrders(parsedOrders, `已解析 ${parsedOrders.length} 单，已按接机、送机、包车分类。`);
      })
      .catch((err) => {
        this.setData({ parseLoading: false, message: `解析失败：${err.error || err.message || '请检查格式'}` });
      });
  },

  clearParsed() {
    this.applyParsedOrders([], '');
  },

  createParsedOrders() {
    this.createParsedOrdersWithMode(false);
  },

  createAndPublishOrders() {
    wx.showModal({
      title: '确认发布',
      content: '将保存选中订单，并按报价作为起拍价和一口价发布到订单大厅。',
      confirmText: '发布',
      success: (res) => {
        if (res.confirm) this.createParsedOrdersWithMode(true);
      }
    });
  },

  createParsedOrdersWithMode(publishAfterCreate) {
    const rows = this.selectedParsedRows();
    if (!rows.length) {
      wx.showToast({ title: '请选择订单', icon: 'none' });
      return;
    }
    this.setData({ createLoading: true, message: '' });
    let chain = Promise.resolve();
    rows.forEach((row) => {
      const payload = this.toCreatePayload(row);
      const pdfPayload = payload.pdfPayload;
      delete payload.pdfPayload;
      chain = chain.then(() => api.createOrder(payload));
      if (pdfPayload) {
        chain = chain.then((created) => {
          const orderId = created && created.order ? created.order.id : created.id;
          return orderId ? api.uploadItineraryPdf(orderId, pdfPayload).then(() => created) : created;
        });
      }
      if (publishAfterCreate) {
        chain = chain.then((created) => {
          const order = created && created.order ? created.order : created;
          const orderId = order && order.id;
          const price = Number(payload.price_jpy || payload.price || order.price_jpy || order.price || 0);
          if (!orderId || !price) throw new Error('missing_publish_price');
          return api.publishOrderToAuction(orderId, {
            start_price_jpy: price,
            buyout_price_jpy: price,
            auction_duration_hours: 2,
            note: '旅行社小程序发布'
          });
        });
      }
    });
    chain
      .then(() => {
        const remaining = this.data.parsedOrders.filter((item) => !item.selected);
        this.setData({ createLoading: false });
        this.applyParsedOrders(remaining, publishAfterCreate ? `已保存并发布 ${rows.length} 单。` : `已保存 ${rows.length} 单。`);
      })
      .catch((err) => {
        this.setData({ createLoading: false, message: `保存失败：${err.error || err.message || '请确认每单都有报价'}` });
      });
  },

  selectedParsedRows() {
    return this.data.parsedOrders.filter((item) => item.selected);
  },

  toggleParsedSelection(e) {
    const key = e.currentTarget.dataset.key;
    const parsedOrders = this.data.parsedOrders.map((item) => (
      item.key === key ? { ...item, selected: !item.selected } : item
    ));
    this.applyParsedOrders(parsedOrders);
  },

  onParsedFieldInput(e) {
    const key = e.currentTarget.dataset.key;
    const field = e.currentTarget.dataset.field;
    if (!key || !field) return;
    const numberFields = ['price', 'price_jpy', 'passenger_count', 'luggage_count'];
    const value = numberFields.indexOf(field) >= 0 ? (e.detail.value === '' ? '' : Number(e.detail.value)) : e.detail.value;
    const parsedOrders = this.data.parsedOrders.map((item, index) => {
      if (item.key !== key) return item;
      const next = { ...item, [field]: value };
      if (field === 'price') next.price_jpy = value;
      return this.decorateOrder(next, index);
    });
    this.applyParsedOrders(parsedOrders);
  },

  choosePdf(e) {
    const key = e.currentTarget.dataset.key;
    const row = this.data.parsedOrders.find((item) => item.key === key);
    if (!row) return;
    if (!row.needsPdf) {
      wx.showToast({ title: '机场接送无需PDF', icon: 'none' });
      return;
    }
    wx.chooseMessageFile({
      count: 1,
      type: 'file',
      success: (res) => {
        const file = res.tempFiles && res.tempFiles[0];
        if (!file) return;
        if (file.name && file.name.toLowerCase().slice(-4) !== '.pdf') {
          wx.showToast({ title: '只能上传 PDF', icon: 'none' });
          return;
        }
        api.fileToDataUrl(file.path, 'application/pdf')
          .then((fileBase64) => {
            const parsedOrders = this.data.parsedOrders.map((item) => (
              item.key === key
                ? { ...item, itinerary_pdf_name: file.name || 'itinerary.pdf', pdfPayload: { file_name: file.name || 'itinerary.pdf', file_base64: fileBase64 } }
                : item
            ));
            this.applyParsedOrders(parsedOrders, `已选择 PDF：${file.name || 'itinerary.pdf'}`);
          })
          .catch(() => wx.showToast({ title: 'PDF读取失败', icon: 'none' }));
      }
    });
  },

  applyParsedOrders(parsedOrders, message) {
    const pickupRows = parsedOrders.filter((item) => item.kind === 'pickup');
    const dropoffRows = parsedOrders.filter((item) => item.kind === 'dropoff');
    const charterRows = parsedOrders.filter((item) => item.kind === 'charter');
    this.setData({
      parsedOrders,
      pickupRows,
      dropoffRows,
      charterRows,
      selectedParsedCount: parsedOrders.filter((item) => item.selected).length,
      parseLoading: false,
      message: typeof message === 'string' ? message : this.data.message
    });
  },

  decorateOrder(item, index) {
    const kind = this.orderKind(item);
    const price = item.price_jpy || item.price || 0;
    const orderType = kind === 'charter' ? '包车' : kind === 'dropoff' ? '送机' : '接机';
    return {
      ...item,
      key: item.key || `parsed-${Date.now()}-${index}`,
      selected: item.selected !== false,
      kind,
      order_type: orderType,
      typeText: orderType,
      needsPdf: kind === 'charter',
      routeText: `${item.pickup_location || '-'} -> ${item.dropoff_location || '-'}`,
      timeText: `${item.order_date || '-'} ${item.start_time || ''}`,
      priceText: price ? `¥${Number(price).toLocaleString()}` : '-',
      oid: item.oid || `预览 ${index + 1}`
    };
  },

  orderKind(item) {
    const text = `${item.order_type || ''} ${item.pickup_location || ''} ${item.dropoff_location || ''} ${item.remark || ''}`.toLowerCase();
    if (text.indexOf('包车') >= 0 || text.indexOf('包車') >= 0 || text.indexOf('charter') >= 0 || text.indexOf('往返') >= 0) return 'charter';
    if (text.indexOf('送机') >= 0 || text.indexOf('送機') >= 0 || text.indexOf('dropoff') >= 0 || text.indexOf('departure') >= 0) return 'dropoff';
    if (text.indexOf('接机') >= 0 || text.indexOf('接機') >= 0 || text.indexOf('pickup') >= 0 || text.indexOf('arrival') >= 0) return 'pickup';
    const pickupAirport = this.isAirportPlace(item.pickup_location);
    const dropoffAirport = this.isAirportPlace(item.dropoff_location);
    if (dropoffAirport && !pickupAirport) return 'dropoff';
    return 'pickup';
  },

  isAirportPlace(value) {
    const text = String(value || '').toLowerCase();
    return /(机场|空港|airport|kix|関西|关西|haneda|羽田|narita|成田|itami|伊丹|kansai)/i.test(text);
  },

  toCreatePayload(row) {
    const payload = { ...row };
    [
      'key', 'kind', 'routeText', 'timeText', 'priceText', 'typeText', 'needsPdf',
      'selected', 'oid', 'itinerary_pdf_name'
    ].forEach((key) => delete payload[key]);
    Object.keys(payload).forEach((key) => {
      if (payload[key] === '') delete payload[key];
    });
    return payload;
  }
});

