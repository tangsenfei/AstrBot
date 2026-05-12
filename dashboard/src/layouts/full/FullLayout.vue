<script setup lang="ts">
import { RouterView, useRoute, useRouter } from 'vue-router';
import { ref, onMounted, computed, watch } from 'vue';
import axios from 'axios';
import VerticalSidebarVue from './vertical-sidebar/VerticalSidebar.vue';
import VerticalHeaderVue from './vertical-header/VerticalHeader.vue';
import MigrationDialog from '@/components/shared/MigrationDialog.vue';
import ReadmeDialog from '@/components/shared/ReadmeDialog.vue';
import Chat from '@/components/chat/Chat.vue';
import { useCustomizerStore } from '@/stores/customizer';
import { useRouterLoadingStore } from '@/stores/routerLoading';
import { useI18n } from '@/i18n/composables';

const FIRST_NOTICE_SEEN_KEY = 'astrbot:first_notice_seen:v1';

const customizer = useCustomizerStore();
const { locale } = useI18n();
const route = useRoute();
const router = useRouter();
const routerLoadingStore = useRouterLoadingStore();
const isCurrentChatRoute = computed(() => route.path === '/chat' || route.path.startsWith('/chat/'));
const isCurrentWorkRoute = computed(() => route.path === '/work' || route.path.startsWith('/work/'));
const isCurrentMeetingRoute = computed(() => route.path === '/meeting' || route.path.startsWith('/meeting/'));
const isCurrentCronRoute = computed(() => route.path === '/cron');
const isCurrentGenericAgentRoute = computed(() => route.path === '/generic-agent');
const isCurrentOverviewRoute = computed(() => route.path === '/' || route.path === '/dashboard/default' || route.path === '/about');
const isWorkSectionRoute = computed(() => isCurrentWorkRoute.value || isCurrentMeetingRoute.value || isCurrentCronRoute.value || isCurrentGenericAgentRoute.value);
const isImmersiveRoute = computed(() => isCurrentChatRoute.value || isWorkSectionRoute.value);
const shouldMountChat = ref(isCurrentChatRoute.value);
const workDailyDirs = ref<any[]>([]);
const workProjects = ref<any[]>([]);
const workModuleItems = [
  { title: 'Meeting 会议', icon: 'mdi-table-chair', path: '/meeting' },
  { title: '定时任务', icon: 'mdi-clock-outline', path: '/cron' },
  { title: '智能RPA', icon: 'mdi-desktop-classic', path: '/generic-agent' },
];

const showSidebar = computed(() => !isImmersiveRoute.value && !isCurrentOverviewRoute.value)

function isActiveWorkModule(path: string) {
  return route.path === path;
}

function goWorkModule(path: string) {
  if (!isActiveWorkModule(path)) {
    router.push(path);
  }
}

function queryValue(value: unknown) {
  return typeof value === 'string' ? value : '';
}

function isActiveWorkScope(scope: 'daily' | 'project', id?: string) {
  if (!isCurrentWorkRoute.value) return false;
  const routeScope = queryValue(route.query.scope) || 'daily';
  if (routeScope !== scope) return false;
  const key = scope === 'daily' ? 'daily_dir_id' : 'project_id';
  return queryValue(route.query[key]) === (id || '');
}

function goWorkScope(scope: 'daily' | 'project', id?: string) {
  const query: Record<string, string> = { scope };
  if (scope === 'daily' && id) query.daily_dir_id = id;
  if (scope === 'project' && id) query.project_id = id;
  router.push({ path: '/work', query });
}

async function loadWorkNavigationData() {
  const [dailyRes, projectRes] = await Promise.allSettled([
    axios.get('/api/plug/work/daily-dirs'),
    axios.get('/api/plug/work/projects'),
  ]);
  if (dailyRes.status === 'fulfilled' && dailyRes.value.data?.status === 'ok') {
    workDailyDirs.value = dailyRes.value.data.data || [];
  }
  if (projectRes.status === 'fulfilled' && projectRes.value.data?.status === 'ok') {
    workProjects.value = projectRes.value.data.data || [];
  }
}

const migrationDialog = ref<InstanceType<typeof MigrationDialog> | null>(null);
const showFirstNoticeDialog = ref(false);

watch(isCurrentChatRoute, (isChatRoute) => {
  if (isChatRoute) {
    shouldMountChat.value = true;
  }
});

const checkMigration = async (): Promise<boolean> => {
  try {
    const response = await axios.get('/api/stat/version');
    if (response.data.status === 'ok' && response.data.data.need_migration) {
      if (migrationDialog.value && typeof migrationDialog.value.open === 'function') {
        const result = await migrationDialog.value.open();
        if (result.success) {
          console.log('Migration completed successfully:', result.message);
          window.location.reload();
        }
      }
      return true;
    }
  } catch (error) {
    console.error('Failed to check migration status:', error);
  }
  return false;
};

const maybeShowFirstNotice = async () => {
  if (localStorage.getItem(FIRST_NOTICE_SEEN_KEY) === '1') {
    return;
  }

  try {
    const response = await axios.get('/api/stat/first-notice', {
      params: { locale: locale.value },
    });
    if (response.data.status !== 'ok') {
      return;
    }

    const content = response.data?.data?.content;
    if (typeof content === 'string' && content.trim().length > 0) {
      showFirstNoticeDialog.value = true;
      return;
    }

    localStorage.setItem(FIRST_NOTICE_SEEN_KEY, '1');
  } catch (error) {
    console.error('Failed to load first notice:', error);
  }
};

const onFirstNoticeDialogUpdate = (visible: boolean) => {
  showFirstNoticeDialog.value = visible;
  if (!visible) {
    localStorage.setItem(FIRST_NOTICE_SEEN_KEY, '1');
  }
};

onMounted(() => {
  loadWorkNavigationData().catch(() => undefined);
  setTimeout(async () => {
    const migrationPending = await checkMigration();
    if (!migrationPending) {
      await maybeShowFirstNotice();
    }
  }, 1000);
});

watch(isWorkSectionRoute, (active) => {
  if (active) loadWorkNavigationData().catch(() => undefined);
});
</script>

<template>
  <v-locale-provider>
    <v-app :theme="useCustomizerStore().uiTheme"
      :class="[customizer.fontTheme, customizer.mini_sidebar ? 'mini-sidebar' : '', customizer.inputBg ? 'inputWithbg' : '']"
    >
      <v-progress-linear
        v-if="routerLoadingStore.isLoading"
        :model-value="routerLoadingStore.progress"
        color="primary"
        height="2"
        fixed
        top
        style="z-index: 9999; position: absolute; opacity: 0.3; "
      />
      <VerticalHeaderVue />
      <VerticalSidebarVue v-if="showSidebar" />
      <v-main :style="{
        height: isImmersiveRoute ? 'calc(100vh - 55px)' : undefined,
        overflow: isImmersiveRoute ? 'hidden' : undefined
      }">
        <v-container
          fluid
          class="page-wrapper"
          :class="{ 'chat-mode-container': isImmersiveRoute }"
          :style="{
            height: isImmersiveRoute ? '100%' : 'calc(100% - 8px)',
            padding: isImmersiveRoute ? '0' : undefined,
            minHeight: isImmersiveRoute ? 'unset' : undefined
          }">
          <div :style="{ height: '100%', width: '100%', overflow: isImmersiveRoute ? 'hidden' : undefined }">
            <div
              v-if="shouldMountChat"
              v-show="isCurrentChatRoute"
              style="height: 100%; width: 100%; overflow: hidden;"
            >
              <Chat :active="isCurrentChatRoute" />
            </div>
            <div v-if="isWorkSectionRoute" class="work-mode-layout">
              <aside class="work-module-sidebar">
                <div class="work-module-head">
                  <div class="work-module-title">Work</div>
                  <div class="work-module-subtitle">工作空间</div>
                </div>
                <div class="work-module-section">
                  <button
                    class="work-module-item"
                    :class="{ active: isActiveWorkScope('daily') }"
                    type="button"
                    @click="goWorkScope('daily')"
                  >
                    <v-icon size="18">mdi-calendar-check-outline</v-icon>
                    <span>日常任务</span>
                  </button>
                  <div class="work-module-children">
                    <button
                      v-for="dir in workDailyDirs"
                      :key="dir.id"
                      class="work-module-item child"
                      :class="{ active: isActiveWorkScope('daily', dir.id) }"
                      type="button"
                      @click="goWorkScope('daily', dir.id)"
                    >
                      <v-icon size="16">mdi-folder-clock-outline</v-icon>
                      <span>{{ dir.name }}</span>
                    </button>
                  </div>
                </div>
                <div class="work-module-section">
                  <button
                    class="work-module-item"
                    :class="{ active: isActiveWorkScope('project') }"
                    type="button"
                    @click="goWorkScope('project')"
                  >
                    <v-icon size="18">mdi-briefcase-outline</v-icon>
                    <span>项目</span>
                  </button>
                  <div class="work-module-children">
                    <button
                      v-for="project in workProjects"
                      :key="project.id"
                      class="work-module-item child"
                      :class="{ active: isActiveWorkScope('project', project.id) }"
                      type="button"
                      @click="goWorkScope('project', project.id)"
                    >
                      <v-icon size="16">mdi-folder-star-outline</v-icon>
                      <span>{{ project.name }}</span>
                    </button>
                  </div>
                </div>
                <button
                  v-for="item in workModuleItems"
                  :key="item.path"
                  class="work-module-item"
                  :class="{ active: isActiveWorkModule(item.path) }"
                  type="button"
                  @click="goWorkModule(item.path)"
                >
                  <v-icon size="18">{{ item.icon }}</v-icon>
                  <span>{{ item.title }}</span>
                </button>
              </aside>
              <div class="work-module-content">
                <RouterView />
              </div>
            </div>
            <RouterView v-if="!isCurrentChatRoute && !isWorkSectionRoute" />
          </div>
        </v-container>
      </v-main>

      <MigrationDialog ref="migrationDialog" />
      <ReadmeDialog
        :show="showFirstNoticeDialog"
        mode="first-notice"
        @update:show="onFirstNoticeDialogUpdate"
      />
    </v-app>
  </v-locale-provider>
</template>

<style scoped>
.chat-mode-container {
  min-height: unset !important;
  height: 100% !important;
  overflow: hidden !important;
}

.work-mode-layout {
  display: grid;
  grid-template-columns: 210px minmax(0, 1fr);
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.work-module-sidebar {
  min-height: 0;
  padding: 14px;
  overflow: auto;
  border-right: 1px solid rgba(var(--v-border-color), 0.18);
  background: rgb(var(--v-theme-surface));
}

.work-module-head {
  margin-bottom: 14px;
}

.work-module-title {
  font-size: 19px;
  font-weight: 800;
}

.work-module-subtitle {
  color: rgba(var(--v-theme-on-surface), 0.62);
}

.work-module-section {
  margin-bottom: 10px;
}

.work-module-children {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 4px 0 8px 18px;
}

.work-module-item {
  width: 100%;
  min-height: 38px;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding: 8px 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.work-module-item.child {
  min-height: 32px;
  margin-top: 0;
  font-size: 13px;
}

.work-module-item:hover,
.work-module-item.active {
  background: rgba(var(--v-theme-primary), 0.1);
}

.work-module-content {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

@media (max-width: 820px) {
  .work-mode-layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto minmax(0, 1fr);
  }

  .work-module-sidebar {
    display: flex;
    gap: 8px;
    align-items: center;
    overflow-x: auto;
    border-right: 0;
    border-bottom: 1px solid rgba(var(--v-border-color), 0.18);
  }

  .work-module-head {
    min-width: 92px;
    margin-bottom: 0;
  }

  .work-module-item {
    min-width: max-content;
    margin-top: 0;
  }
}
</style>
