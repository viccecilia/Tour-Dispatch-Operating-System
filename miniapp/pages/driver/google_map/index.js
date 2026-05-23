Page({
  data: {
    src: ''
  },

  onLoad(options) {
    const src = options && options.url ? decodeURIComponent(options.url) : '';
    this.setData({ src });
  }
});
