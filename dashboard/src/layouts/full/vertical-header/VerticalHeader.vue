<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { useCustomizerStore } from '@/stores/customizer';
import axios from 'axios';
import Logo from '@/components/shared/Logo.vue';
import { md5 } from 'js-md5';
import { useAuthStore } from '@/stores/auth';
import { useCommonStore } from '@/stores/common';
import { useI18n } from '@/i18n/composables';
import { router } from '@/router';
import { useRoute } from 'vue-router';
import { useTheme } from 'vuetify';
import StyledMenu from '@/components/shared/StyledMenu.vue';
import { useLanguageSwitcher } from '@/i18n/composables';
import type { Locale } from '@/i18n/types';
const brandName = computed(() => {
  return { first: 'Nice', second: 'Bot' };
});

const customizer = useCustomizerStore();
const theme = useTheme();
const { t } = useI18n();
const route = useRoute();
const LAST_OVERVIEW_ROUTE_KEY = 'astrbot:last_overview_route';
const LAST_CHAT_ROUTE_KEY = 'astrbot:last_chat_route';
const LAST_WORK_ROUTE_KEY = 'astrbot:last_work_route';
const LAST_SETTING_ROUTE_KEY = 'astrbot:last_setting_route';
let dialog = ref(false);
let accountWarning = ref(false)
const username = localStorage.getItem('user');
let password = ref('');
let newPassword = ref('');
let confirmPassword = ref('');
let newUsername = ref('');
const isChatPath = computed(() =>
  route.path === '/chat' || route.path.startsWith('/chat/')
);
const isWorkPath = computed(() =>
  route.path === '/work' ||
  route.path.startsWith('/work/') ||
  route.path === '/meeting' ||
  route.path.startsWith('/meeting/') ||
  route.path === '/cron' ||
  route.path === '/generic-agent'
);
const isOverviewPath = computed(() =>
  route.path === '/' ||
  route.path === '/dashboard/default'
);
const isSettingPath = computed(() => !isOverviewPath.value && !isChatPath.value && !isWorkPath.value);
const isImmersivePath = computed(() => isChatPath.value || isWorkPath.value);

// Form validation
const formValid = ref(true);
const passwordRules = computed(() => [
  (v: string) => !!v || t('core.header.accountDialog.validation.passwordRequired'),
  (v: string) => v.length >= 8 || t('core.header.accountDialog.validation.passwordMinLength')
]);
const confirmPasswordRules = computed(() => [
  (v: string) => !newPassword.value || !!v || t('core.header.accountDialog.validation.passwordRequired'),
  (v: string) => !newPassword.value || v === newPassword.value || t('core.header.accountDialog.validation.passwordMatch')
]);
const usernameRules = computed(() => [
  (v: string) => !v || v.length >= 3 || t('core.header.accountDialog.validation.usernameMinLength')
]);

// 显示密码相关
const showPassword = ref(false);
const showNewPassword = ref(false);
const showConfirmPassword = ref(false);

// 账户修改状态
const accountEditStatus = ref({
  loading: false,
  success: false,
  error: false,
  message: ''
});

// 账户修改
function accountEdit() {
  accountEditStatus.value.loading = true;
  accountEditStatus.value.error = false;
  accountEditStatus.value.success = false;

  const passwordHash = password.value ? md5(password.value) : '';
  const newPasswordHash = newPassword.value ? md5(newPassword.value) : '';
  const confirmPasswordHash = confirmPassword.value ? md5(confirmPassword.value) : '';

  axios.post('/api/auth/account/edit', {
    password: passwordHash,
    new_password: newPasswordHash,
    confirm_password: confirmPasswordHash,
    new_username: newUsername.value ? newUsername.value : username
  })
    .then((res) => {
      if (res.data.status == 'error') {
        accountEditStatus.value.error = true;
        accountEditStatus.value.message = res.data.message;
        password.value = '';
        newPassword.value = '';
        confirmPassword.value = '';
        return;
      }
      accountEditStatus.value.success = true;
      accountEditStatus.value.message = res.data.message;
      setTimeout(() => {
        dialog.value = !dialog.value;
        const authStore = useAuthStore();
        authStore.logout();
      }, 2000);
    })
    .catch((err) => {
      console.log(err);
      accountEditStatus.value.error = true;
      accountEditStatus.value.message = typeof err === 'string' ? err : t('core.header.accountDialog.messages.updateFailed');
      password.value = '';
      newPassword.value = '';
      confirmPassword.value = '';
    })
    .finally(() => {
      accountEditStatus.value.loading = false;
    });
}

function getVersion() {
  axios.get('/api/stat/version')
    .then((res) => {
      let change_pwd_hint = res.data.data?.change_pwd_hint;
      if (change_pwd_hint) {
        dialog.value = true;
        accountWarning.value = true;
        localStorage.setItem('change_pwd_hint', 'true');
      } else {
        localStorage.removeItem('change_pwd_hint');
      }
    })
    .catch((err) => {
      console.log(err);
    });
}

function toggleDarkMode() {
  const newTheme = customizer.uiTheme === 'PurpleThemeDark' ? 'PurpleTheme' : 'PurpleThemeDark';
  customizer.SET_UI_THEME(newTheme);
  theme.global.name.value = newTheme;
}

function handleLogoClick() {
  if (isImmersivePath.value) {
    router.push('/dashboard/default');
  } else {
    router.push('/dashboard/default');
  }
}

getVersion();

const commonStore = useCommonStore();
commonStore.createEventSource(); // log
commonStore.getStartTime();

// 视图模式切换
onMounted(() => {
  // 初次加載時保存當前路由
  if (typeof window !== 'undefined') {
    if (isChatPath.value) {
      // 保存 chat ID
      const parts = route.fullPath.split('/');
      const sessionId = parts[2];
      if (sessionId) {
        sessionStorage.setItem(LAST_CHAT_ROUTE_KEY, sessionId);
        console.log('Initial save chat ID:', sessionId);
      }
    } else if (isWorkPath.value) {
      sessionStorage.setItem(LAST_WORK_ROUTE_KEY, route.fullPath);
    } else if (isSettingPath.value) {
      sessionStorage.setItem(LAST_SETTING_ROUTE_KEY, route.fullPath);
    } else {
      sessionStorage.setItem(LAST_OVERVIEW_ROUTE_KEY, route.fullPath);
      console.log('Initial save overview route:', route.fullPath);
    }
  }
});

// 监听 viewMode 变化，保存各一级入口的最后路由
watch(() => route.fullPath, (newPath) => {
  if (typeof window === 'undefined') return;
  console.log('Route changed:', {
    newPath,
    isChat: isChatPath.value,
    currentChatId: route.params.id
  });
  try {
    // 使用現有的 isChatPath 計算屬性來避免名稱衝突
    const isChat = isChatPath.value; // 這裡使用已經計算好的 isChatPath
    const isWork = isWorkPath.value;
    const isOverview = isOverviewPath.value;
    const isSetting = isSettingPath.value;

    if (isOverview) {
      sessionStorage.setItem(LAST_OVERVIEW_ROUTE_KEY, newPath);
    }

    // ✅ chat：只存 sessionId
    if (isChat) {
      const parts = newPath.split('/');
      const sessionId = parts[2];

      if (sessionId) {
        sessionStorage.setItem(LAST_CHAT_ROUTE_KEY, sessionId);
      }
    }

    if (isWork) {
      sessionStorage.setItem(LAST_WORK_ROUTE_KEY, newPath);
    }

    if (isSetting) {
      sessionStorage.setItem(LAST_SETTING_ROUTE_KEY, newPath);
    }

  } catch (e) {
    console.error('Failed to save route:', e);
  }
});

const currentMode = computed({
  get: () => (isSettingPath.value ? 'setting' : isWorkPath.value ? 'work' : isChatPath.value ? 'chat' : 'overview'),
  set: (val: 'overview' | 'chat' | 'work' | 'setting') => {
    try {
      // 檢查 window 和 sessionStorage 是否存在
      if (typeof window === 'undefined' || typeof sessionStorage === 'undefined') {
        // 如果在非瀏覽器環境中，不做任何 sessionStorage 操作
        console.warn('sessionStorage is not available in this environment');
        return;
      }

      if (val === 'chat') {
        const lastSessionId = sessionStorage.getItem(LAST_CHAT_ROUTE_KEY);
        router.push(lastSessionId ? `/chat/${lastSessionId}` : '/chat');
      } else if (val === 'work') {
        const lastWorkRoute = sessionStorage.getItem(LAST_WORK_ROUTE_KEY) || '/work';
        const validWorkRoute =
          lastWorkRoute.startsWith('/work') ||
          lastWorkRoute.startsWith('/meeting') ||
          lastWorkRoute === '/cron' ||
          lastWorkRoute === '/generic-agent';
        router.push(validWorkRoute ? lastWorkRoute : '/work');
      } else if (val === 'setting') {
        const lastSettingRoute = sessionStorage.getItem(LAST_SETTING_ROUTE_KEY) || '/settings';
        router.push(lastSettingRoute === '/' || lastSettingRoute.startsWith('/dashboard') ? '/settings' : lastSettingRoute);
      } else {
        let lastOverviewRoute = sessionStorage.getItem(LAST_OVERVIEW_ROUTE_KEY) || '/dashboard/default';
        if (!lastOverviewRoute.startsWith('/dashboard') && lastOverviewRoute !== '/') {
          lastOverviewRoute = '/dashboard/default';
        }
        router.push(lastOverviewRoute === '/' ? '/dashboard/default' : lastOverviewRoute);
      }
    } catch (e) {
      // 在受限隱私模式等環境中，sessionStorage 操作可能會拋出 SecurityError
      console.warn('Failed to access sessionStorage in currentMode setter:', e);
    }
  }
});

// Merry Christmas! 🎄
const isChristmas = computed(() => {
  const today = new Date();
  const month = today.getMonth() + 1; // getMonth() 返回 0-11
  const day = today.getDate();
  return month === 12 && day === 25;
});

// 语言切换相关
const mainMenuOpen = ref(false);
const { languageOptions, currentLanguage, switchLanguage, locale } = useLanguageSwitcher();
const languages = computed(() => 
  languageOptions.value.map(lang => ({
    code: lang.value,
    name: lang.label,
    flag: lang.flag
  }))
);
const currentLocale = computed(() => locale.value);
const changeLanguage = async (langCode: string) => {
  await switchLanguage(langCode as Locale);
  mainMenuOpen.value = false;
};

</script>

<template>
  <v-app-bar elevation="0" height="50" class="top-header">

    <!-- 桌面端 menu 按钮 - 仅在 bot 模式下显示 -->
<v-btn
  v-if="!isImmersivePath"
  style="margin-left: 16px;"
  class="hidden-md-and-down"
  icon
  rounded="sm"
  variant="flat"
  @click.stop="customizer.SET_MINI_SIDEBAR(!customizer.mini_sidebar)"
>
  <v-icon>mdi-menu</v-icon>
</v-btn>

<!-- 移动端 menu 按钮 -->
<v-btn
  v-if="!isImmersivePath"
  class="hidden-lg-and-up ms-3"
  icon
  rounded="sm"
  variant="flat"
  @click.stop="customizer.SET_SIDEBAR_DRAWER"
>
  <v-icon>mdi-menu</v-icon>
</v-btn>

<v-btn
  v-if="isChatPath"
  class="hidden-lg-and-up ms-1"
  icon
  rounded="sm"
  variant="flat"
  @click.stop="customizer.TOGGLE_CHAT_SIDEBAR()"
>
  <v-icon>mdi-menu</v-icon>
</v-btn>

    <div class="logo-container" :class="{ 'mobile-logo': $vuetify.display.xs, 'chat-mode-logo': isImmersivePath }" @click="handleLogoClick">
      <span class="logo-text Outfit">{{ brandName.first }}<span class="logo-text bot-text-wrapper">{{ brandName.second }}
        <img v-if="isChristmas" src="@/assets/images/xmas-hat.png" alt="Christmas hat" class="xmas-hat" />
      </span></span>
      <span class="logo-text logo-text-light Outfit" style="color: grey;" v-if="isChatPath">ChatUI</span>
      <span class="logo-text logo-text-light Outfit" style="color: grey;" v-else-if="isWorkPath">Work</span>
      <span class="logo-text logo-text-light Outfit" style="color: grey;" v-else-if="isSettingPath">Setting</span>
    </div>

  <v-spacer />

    <!-- 顶层入口切换按钮 - 手机端隐藏，移入 ... 菜单 -->
<v-btn-toggle
  v-model="currentMode"
  mandatory
  variant="outlined"
  density="compact"
  class="mr-4 hidden-xs"
  color="primary"
>
  <v-btn value="overview" size="small">
    <v-icon start>mdi-view-dashboard-outline</v-icon>
    总览
  </v-btn>
  <v-btn value="chat" size="small">
    <v-icon start>mdi-chat</v-icon>
    聊天
  </v-btn>
  <v-btn value="work" size="small">
    <v-icon start>mdi-briefcase-outline</v-icon>
    工作
  </v-btn>
  <v-btn value="setting" size="small">
    <v-icon start>mdi-cog-outline</v-icon>
    Setting
  </v-btn>
</v-btn-toggle>


    <!-- 功能菜单 -->
    <StyledMenu v-model="mainMenuOpen" offset="12" location="bottom end">
      <template v-slot:activator="{ props: activatorProps }">
        <v-btn
          v-bind="activatorProps"
          size="small"
          class="action-btn mr-4"
          color="var(--v-theme-surface)"
          variant="flat"
          rounded="sm"
          icon
        >
          <v-icon>mdi-dots-vertical</v-icon>
        </v-btn>
      </template>

      <!-- 顶层入口切换 - 仅在手机端显示 -->
      <template v-if="$vuetify.display.xs">
        <div class="mobile-mode-toggle-wrapper">
<v-btn-toggle
  v-model="currentMode"
  mandatory
  variant="outlined"
  density="compact"
  class="mobile-mode-toggle"
  color="primary"
>
            <v-btn value="overview" size="small">
              <v-icon start>mdi-view-dashboard-outline</v-icon>
              总览
            </v-btn>
            <v-btn value="chat" size="small">
              <v-icon start>mdi-chat</v-icon>
              聊天
            </v-btn>
            <v-btn value="work" size="small">
              <v-icon start>mdi-briefcase-outline</v-icon>
              工作
            </v-btn>
            <v-btn value="setting" size="small">
              <v-icon start>mdi-cog-outline</v-icon>
              Setting
            </v-btn>
          </v-btn-toggle>
        </div>
        <v-divider class="my-1" />
      </template>

      <!-- 语言切换分组 -->
      <v-menu
        open-on-click
        :open-on-hover="!$vuetify.display.xs"
        :open-delay="!$vuetify.display.xs ? 60 : 0"
        :close-delay="!$vuetify.display.xs ? 120 : 0"
        :location="$vuetify.display.xs ? 'bottom' : 'start center'"
        offset="8"
      >
        <template v-slot:activator="{ props: languageMenuProps }">
          <v-list-item
            v-bind="languageMenuProps"
            @click.stop
            class="styled-menu-item language-group-trigger"
            rounded="md"
          >
            <template v-slot:prepend>
              <v-icon>mdi-translate</v-icon>
            </template>
            <v-list-item-title>{{ t('core.common.language') }}</v-list-item-title>
            <template v-slot:append>
              <span class="language-group-current">{{ currentLanguage?.flag }}</span>
              <v-icon size="18" class="language-group-arrow">mdi-chevron-right</v-icon>
            </template>
          </v-list-item>
        </template>

        <v-card class="styled-menu-card" style="min-width: 180px;" elevation="8" rounded="lg">
          <v-list density="compact" class="styled-menu-list pa-1">
            <v-list-item
              v-for="lang in languages"
              :key="lang.code"
              :value="lang.code"
              @click="changeLanguage(lang.code)"
              :class="{ 'styled-menu-item-active': currentLocale === lang.code }"
              class="styled-menu-item"
              rounded="md"
            >
              <template v-slot:prepend>
                <span class="language-flag">{{ lang.flag }}</span>
              </template>
              <v-list-item-title>{{ lang.name }}</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-card>
      </v-menu>

      <!-- 主题切换 -->
      <v-list-item
        @click="toggleDarkMode()"
        class="styled-menu-item"
        rounded="md"
      >
        <template v-slot:prepend>
          <v-icon>
            {{ useCustomizerStore().uiTheme === 'PurpleThemeDark' ? 'mdi-weather-night' : 'mdi-white-balance-sunny' }}
          </v-icon>
        </template>
        <v-list-item-title>
          {{ useCustomizerStore().uiTheme === 'PurpleThemeDark' ? t('core.header.buttons.theme.light') : t('core.header.buttons.theme.dark') }}
        </v-list-item-title>
      </v-list-item>

      <!-- 账户按钮 -->
      <v-list-item
        @click="dialog = true"
        class="styled-menu-item"
        rounded="md"
      >
        <template v-slot:prepend>
          <v-icon>mdi-account</v-icon>
        </template>
        <v-list-item-title>{{ t('core.header.accountDialog.title') }}</v-list-item-title>
      </v-list-item>
    </StyledMenu>

    <!-- 账户对话框 -->
    <v-dialog v-model="dialog" persistent :max-width="$vuetify.display.xs ? '90%' : '500'">
      <v-card class="account-dialog">
        <v-card-text class="py-6">
          <div class="d-flex flex-column align-center mb-6">
            <logo :title="t('core.header.logoTitle')" :subtitle="t('core.header.accountDialog.title')"></logo>
          </div>
          <v-alert v-if="accountWarning" type="warning" variant="tonal" border="start" class="mb-4">
            <strong>{{ t('core.header.accountDialog.securityWarning') }}</strong>
          </v-alert>

          <v-alert v-if="accountEditStatus.success" type="success" variant="tonal" border="start" class="mb-4">
            {{ accountEditStatus.message }}
          </v-alert>

          <v-alert v-if="accountEditStatus.error" type="error" variant="tonal" border="start" class="mb-4">
            {{ accountEditStatus.message }}
          </v-alert>

          <v-form v-model="formValid" @submit.prevent="accountEdit">
            <v-text-field v-model="password" :append-inner-icon="showPassword ? 'mdi-eye-off' : 'mdi-eye'"
              :type="showPassword ? 'text' : 'password'" :label="t('core.header.accountDialog.form.currentPassword')"
              variant="outlined" required clearable @click:append-inner="showPassword = !showPassword"
              prepend-inner-icon="mdi-lock-outline" hide-details="auto" class="mb-4"></v-text-field>

            <v-text-field v-model="newPassword" :append-inner-icon="showNewPassword ? 'mdi-eye-off' : 'mdi-eye'"
              :type="showNewPassword ? 'text' : 'password'" :rules="passwordRules"
              :label="t('core.header.accountDialog.form.newPassword')" variant="outlined" clearable
              @click:append-inner="showNewPassword = !showNewPassword" prepend-inner-icon="mdi-lock-plus-outline"
              :hint="t('core.header.accountDialog.form.passwordHint')" persistent-hint class="mb-4"></v-text-field>

            <v-text-field v-model="confirmPassword" :append-inner-icon="showConfirmPassword ? 'mdi-eye-off' : 'mdi-eye'"
              :type="showConfirmPassword ? 'text' : 'password'" :rules="confirmPasswordRules"
              :label="t('core.header.accountDialog.form.confirmPassword')" variant="outlined" clearable
              @click:append-inner="showConfirmPassword = !showConfirmPassword" prepend-inner-icon="mdi-lock-check-outline"
              :hint="t('core.header.accountDialog.form.confirmPasswordHint')" persistent-hint class="mb-4"></v-text-field>

            <v-text-field v-model="newUsername" :rules="usernameRules"
              :label="t('core.header.accountDialog.form.newUsername')" variant="outlined" clearable
              prepend-inner-icon="mdi-account-edit-outline" :hint="t('core.header.accountDialog.form.usernameHint')"
              persistent-hint class="mb-3"></v-text-field>
          </v-form>

          <div class="text-caption text-medium-emphasis mt-2">
            {{ t('core.header.accountDialog.form.defaultCredentials') }}
          </div>
        </v-card-text>

        <v-divider></v-divider>

        <v-card-actions class="pa-4">
          <v-spacer></v-spacer>
          <v-btn v-if="!accountWarning" variant="tonal" color="secondary" @click="dialog = false"
            :disabled="accountEditStatus.loading">
            {{ t('core.header.accountDialog.actions.cancel') }}
          </v-btn>
          <v-btn color="primary" @click="accountEdit" :loading="accountEditStatus.loading" :disabled="!formValid"
            prepend-icon="mdi-content-save">
            {{ t('core.header.accountDialog.actions.save') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-app-bar>
</template>

<style>
.account-dialog .v-card-text {
  padding-top: 24px;
  padding-bottom: 24px;
}

.account-dialog .v-alert {
  margin-bottom: 20px;
}

.account-dialog .v-btn {
  text-transform: none;
  font-weight: 500;
  border-radius: 8px;
}

.account-dialog .v-avatar {
  transition: transform 0.3s ease;
}

.account-dialog .v-avatar:hover {
  transform: scale(1.05);
}

/* 响应式布局样式 */
.logo-container {
  margin-left: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.mobile-logo {
  margin-left: 8px;
  gap: 4px;
}

.chat-mode-logo {
  margin-left: 22px;
}

.mobile-logo.chat-mode-logo {
  margin-left: 4px;
}

.logo-text {
  font-size: 24px;
  font-weight: 1000;
}

.logo-text-light {
  font-weight: normal;
}

.bot-text-wrapper {
  position: relative;
  display: inline-block;
}

.xmas-hat {
  position: absolute;
  top: -3px;
  right: -14px;
  width: 24px;
  height: 24px;
  z-index: 1;
}

.action-btn {
  margin-right: 6px;
}

.language-flag {
  font-size: 16px;
  margin-right: 8px;
}

.language-group-trigger :deep(.v-list-item__append) {
  display: flex;
  align-items: center;
  gap: 6px;
}

.language-group-current {
  font-size: 16px;
  line-height: 1;
}

.language-group-arrow {
  opacity: 0.7;
}

.language-submenu-card {
  min-width: 180px;
}

.mobile-mode-toggle-wrapper {
  display: flex;
  justify-content: center;
  padding: 8px 12px 4px;
}

.mobile-mode-toggle {
  width: 100%;
}

.mobile-mode-toggle .v-btn {
  flex: 1;
}

/* 移动端对话框标题样式 */
.mobile-card-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 移动端样式优化 */
@media (max-width: 600px) {
  .logo-text {
    font-size: 20px;
  }

  .action-btn {
    margin-right: 4px;
    min-width: 32px !important;
    width: 32px;
  }

  .v-card-title {
    padding: 12px 16px;
  }

  .v-card-text {
    padding: 16px;
  }

  .v-tabs .v-tab {
    padding: 0 10px;
    font-size: 0.9rem;
  }

  /* 移动端模式切换按钮样式 */
  .v-btn-toggle {
    margin-right: 8px;
  }

  .v-btn-toggle .v-btn {
    font-size: 0.75rem;
    padding: 0 8px;
  }

  .v-btn-toggle .v-icon {
    font-size: 16px;
  }
}
</style>
