/**
 * AstrBot 前端扩展机制
 */

const extensions = {
  branding: {
    title: null,
    appName: null,
    welcomeTitle: null,
    welcomeSubtitle: null
  },
  routes: [],
  sidebarItems: [],
  sidebarInsert: null,
  i18n: {}
};

export function registerExtension(extension) {
  if (extension.branding) {
    Object.assign(extensions.branding, extension.branding);
  }
  
  if (extension.routes && Array.isArray(extension.routes)) {
    extensions.routes.push(...extension.routes);
  }
  
  if (extension.sidebarItems && Array.isArray(extension.sidebarItems)) {
    extensions.sidebarItems.push(...extension.sidebarItems);
  }
  
  if (extension.sidebarInsert) {
    extensions.sidebarInsert = extension.sidebarInsert;
  }
  
  if (extension.i18n) {
    deepMerge(extensions.i18n, extension.i18n);
  }
}

export function getExtensions() {
  return extensions;
}

export function getBranding() {
  return extensions.branding;
}

export function getExtensionRoutes() {
  return extensions.routes;
}

export function getExtensionSidebarItems() {
  return extensions.sidebarItems;
}

export function getSidebarInsert() {
  return extensions.sidebarInsert;
}

export function getExtensionI18n() {
  return extensions.i18n;
}

function deepMerge(target, source) {
  for (const key in source) {
    if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
      if (!target[key]) {
        target[key] = {};
      }
      deepMerge(target[key], source[key]);
    } else {
      target[key] = source[key];
    }
  }
}

export default extensions;
