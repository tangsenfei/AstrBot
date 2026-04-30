import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import vuetify from './plugins/vuetify';
import confirmPlugin from './plugins/confirmPlugin';
import { setupI18n } from './i18n/composables';
import i18n, { loadI18nMessages } from './i18n';
import '@/scss/style.scss';
import VueApexCharts from 'vue3-apexcharts';

import print from 'vue3-print-nb';
import { loader } from '@guolao/vue-monaco-editor'
import * as monaco from 'monaco-editor';
import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker';
import jsonWorker from 'monaco-editor/esm/vs/language/json/json.worker?worker';
import cssWorker from 'monaco-editor/esm/vs/language/css/css.worker?worker';
import htmlWorker from 'monaco-editor/esm/vs/language/html/html.worker?worker';
import tsWorker from 'monaco-editor/esm/vs/language/typescript/ts.worker?worker';
import axios from 'axios';
import { waitForRouterReadyInBackground } from './utils/routerReadiness.mjs';

document.title = 'NiceBot - 智能助手平台';

import { router } from './router';

loadI18nMessages();

(self as any).MonacoEnvironment = {
  getWorker(_: string, label: string) {
    if (label === 'json') {
      return new jsonWorker();
    }
    if (label === 'css' || label === 'scss' || label === 'less') {
      return new cssWorker();
    }
    if (label === 'html' || label === 'handlebars' || label === 'razor') {
      return new htmlWorker();
    }
    if (label === 'typescript' || label === 'javascript') {
      return new tsWorker();
    }
    return new editorWorker();
  },
};

setupI18n().then(async () => {
  console.log('🌍 新i18n系统初始化完成');
  
  const app = createApp(App);
  const pinia = createPinia();
  app.use(pinia);
  app.use(router);
  app.use(print);
  app.use(VueApexCharts);
  app.use(vuetify);
  app.use(confirmPlugin);
  app.use(i18n);
  await router.isReady();
  app.mount('#app');
  
  import('./stores/customizer').then(({ useCustomizerStore }) => {
    const customizer = useCustomizerStore(pinia);
    vuetify.theme.global.name.value = customizer.uiTheme;
    const storedPrimary = localStorage.getItem('themePrimary');
    const storedSecondary = localStorage.getItem('themeSecondary');
    if (storedPrimary || storedSecondary) {
      const themes = vuetify.theme.themes.value;
      ['PurpleTheme', 'PurpleThemeDark'].forEach((name) => {
        const theme = themes[name];
        if (!theme?.colors) return;
        if (storedPrimary) theme.colors.primary = storedPrimary;
        if (storedSecondary) theme.colors.secondary = storedSecondary;
        if (storedPrimary && theme.colors.darkprimary) theme.colors.darkprimary = storedPrimary;
        if (storedSecondary && theme.colors.darksecondary) theme.colors.darksecondary = storedSecondary;
      });
    }
  });
}).catch(error => {
  console.error('❌ 新i18n系统初始化失败:', error);
  
  const app = createApp(App);
  const pinia = createPinia();
  app.use(pinia);
  app.use(router);
  app.use(print);
  app.use(VueApexCharts);
  app.use(vuetify);
  app.use(confirmPlugin);
  app.mount('#app');
  waitForRouterReadyInBackground(router);
  
  import('./stores/customizer').then(({ useCustomizerStore }) => {
    const customizer = useCustomizerStore(pinia);
    vuetify.theme.global.name.value = customizer.uiTheme;
    const storedPrimary = localStorage.getItem('themePrimary');
    const storedSecondary = localStorage.getItem('themeSecondary');
    if (storedPrimary || storedSecondary) {
      const themes = vuetify.theme.themes.value;
      ['PurpleTheme', 'PurpleThemeDark'].forEach((name) => {
        const theme = themes[name];
        if (!theme?.colors) return;
        if (storedPrimary) theme.colors.primary = storedPrimary;
        if (storedSecondary) theme.colors.secondary = storedSecondary;
        if (storedPrimary && theme.colors.darkprimary) theme.colors.darkprimary = storedPrimary;
        if (storedSecondary && theme.colors.darksecondary) theme.colors.darksecondary = storedSecondary;
      });
    }
  });
});


axios.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  const locale = localStorage.getItem('astrbot-locale');
  if (locale) {
    config.headers['Accept-Language'] = locale;
  }
  return config;
});

const _origFetch = window.fetch.bind(window);
window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
  const token = localStorage.getItem('token');
  if (!token) return _origFetch(input, init);

  const headers = new Headers(init?.headers || (typeof input !== 'string' && 'headers' in input ? (input as Request).headers : undefined));
  if (!headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  const locale = localStorage.getItem('astrbot-locale');
  if (locale && !headers.has('Accept-Language')) {
    headers.set('Accept-Language', locale);
  }
  return _origFetch(input, { ...init, headers });
};

loader.config({ monaco })
