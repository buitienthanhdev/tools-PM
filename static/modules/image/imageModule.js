import { mountImageWorkspace, unmountImageWorkspace } from './imageWorkspace.js';

export const imageModule = {
  id: 'image',
  name: 'Image Workspace',
  route: '/Image',
  icon: '🖼️',
  category: 'Vision AI',
  description: 'Chỉnh sửa và nâng cấp ảnh bằng AI theo dự án: ảnh nguồn bên trái, kết quả bên phải.',
  status: 'active',

  render(containerEl) {
    mountImageWorkspace(containerEl, this);
  },

  unmount(containerEl) {
    unmountImageWorkspace(containerEl);
  },
};
