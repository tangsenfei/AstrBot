/**
 * AstrBot 扩展初始化入口
 */

import { registerExtension, getBranding } from './extensions';

// 导入 NiceBot 扩展
import nicebotExtension from './extensions/nicebot';

// 注册扩展
registerExtension(nicebotExtension);

// 应用品牌定制
const branding = getBranding();
if (branding.title) {
  document.title = branding.title;
}

export { registerExtension, getBranding };
