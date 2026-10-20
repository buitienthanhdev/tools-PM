import { mountImageWorkspace, unmountImageWorkspace } from './imageWorkspace.js';

export const imageModule = {
  id: 'image',
  name: 'Image Workspace',
  route: '/Image',
  icon: '🖼️',
  category: 'Vision AI',
  description: 'Chỉnh sửa ảnh cục bộ và nâng cấp ảnh bằng Real-ESRGAN khi bạn đồng ý.',
  status: 'active',

  render(containerEl) {
    mountImageWorkspace(containerEl, this);
  },

  unmount(containerEl) {
    unmountImageWorkspace(containerEl);
  },
};
