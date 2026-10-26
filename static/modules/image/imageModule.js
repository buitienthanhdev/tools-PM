import { mountImageWorkspace, unmountImageWorkspace } from './imageWorkspace.js';

// CSS riêng của Image Workspace chỉ tải khi mở công cụ; chờ tải xong để không nháy giao diện thô
let cssReady = null;
function loadCss() {
  return (cssReady ||= new Promise((resolve) => {
    const l = document.createElement('link');
    l.id = 'is-css';
    l.rel = 'stylesheet';
    l.href = '/styles/image.css';
    l.onload = l.onerror = resolve;
    document.head.appendChild(l);
  }));
}

export const imageModule = {
  id: 'image',
  name: 'Image Workspace',
  route: '/Image',
  icon: '🖼️',
  category: 'Vision AI',
  description: 'Chỉnh sửa và nâng cấp ảnh bằng AI theo dự án: ảnh nguồn bên trái, kết quả bên phải.',
  status: 'active',

  async render(containerEl) {
    await loadCss();
    if (window.router?.currentModule?.id !== 'image') return; // đã chuyển trang trong lúc tải CSS
    mountImageWorkspace(containerEl, this);
  },

  unmount(containerEl) {
    unmountImageWorkspace(containerEl);
  },
};
