<script setup>
import { ref, shallowRef, onMounted, onUnmounted, watch } from 'vue';
import { useCustomizerStore } from '../../../stores/customizer';
import { useI18n } from '@/i18n/composables';
import sidebarItems from './sidebarItem';
import NavItem from './NavItem.vue';
import { applySidebarCustomization } from '@/utils/sidebarCustomization';

const { t } = useI18n();

const customizer = useCustomizerStore();

function collectGroupValues(items, values = new Set()) {
  items.forEach((item) => {
    if (item?.children && item.title) {
      values.add(item.title);
      collectGroupValues(item.children, values);
    }
  });
  return values;
}

function sanitizeOpenedItems(items, menuItems) {
  if (!Array.isArray(items)) {
    return [];
  }

  const groupValues = collectGroupValues(menuItems);
  return items.filter((item) => typeof item === 'string' && groupValues.has(item));
}

function getInitialOpenedItems(menuItems) {
  try {
    const stored = JSON.parse(localStorage.getItem('sidebar_openedItems') || '[]');
    return sanitizeOpenedItems(stored, menuItems);
  } catch {
    return [];
  }
}

const sidebarMenu = shallowRef(applySidebarCustomization(sidebarItems));

const openedItems = ref(getInitialOpenedItems(sidebarMenu.value));
watch(openedItems, (val) => {
  localStorage.setItem('sidebar_openedItems', JSON.stringify(sanitizeOpenedItems(val, sidebarMenu.value)));
}, { deep: true });

function refreshSidebarMenu() {
  sidebarMenu.value = applySidebarCustomization(sidebarItems);
  openedItems.value = sanitizeOpenedItems(openedItems.value, sidebarMenu.value);
}

const handleStorageChange = (e) => {
  if (e.key === 'astrbot_sidebar_customization') {
    refreshSidebarMenu();
  }
};

const handleCustomEvent = () => {
  refreshSidebarMenu();
};

onMounted(() => {
  window.addEventListener('storage', handleStorageChange);
  window.addEventListener('sidebar-customization-changed', handleCustomEvent);
});

onUnmounted(() => {
  window.removeEventListener('storage', handleStorageChange);
  window.removeEventListener('sidebar-customization-changed', handleCustomEvent);
});

const sidebarWidth = ref(235);
const minSidebarWidth = 200;
const maxSidebarWidth = 300;
const isResizing = ref(false);

const isMobile = window.innerWidth < 768;
if (isMobile) {
  customizer.Sidebar_drawer = false;
}

function startSidebarResize(event) {
  isResizing.value = true;
  document.body.style.userSelect = 'none';
  document.body.style.cursor = 'ew-resize';
  
  const startX = event.clientX;
  const startWidth = sidebarWidth.value;
  
  function onMouseMoveResize(event) {
    if (!isResizing.value) return;
    
    const deltaX = event.clientX - startX;
    const newWidth = Math.max(minSidebarWidth, Math.min(maxSidebarWidth, startWidth + deltaX));
    sidebarWidth.value = newWidth;
  }
  
  function onMouseUpResize() {
    isResizing.value = false;
    document.body.style.userSelect = '';
    document.body.style.cursor = '';
    document.removeEventListener('mousemove', onMouseMoveResize);
    document.removeEventListener('mouseup', onMouseUpResize);
  }
  
  document.addEventListener('mousemove', onMouseMoveResize);
  document.addEventListener('mouseup', onMouseUpResize);
}

</script>

<template>
  <v-navigation-drawer
    left
    v-model="customizer.Sidebar_drawer"
    elevation="0"
    rail-width="80"
    app
    class="leftSidebar"
    :width="sidebarWidth"
    :rail="customizer.mini_sidebar"
  >
    <div class="sidebar-container">
      <v-list :class="['pa-4', 'listitem', 'flex-grow-1', { 'hidden-scrollbar': customizer.mini_sidebar }]" v-model:opened="openedItems" :open-strategy="'multiple'">
        <template v-for="(item, i) in sidebarMenu" :key="item.title || item.to || `sidebar-item-${i}`">
          <NavItem :item="item" class="leftPadding" />
        </template>
      </v-list>
    </div>
    
    <div 
      v-if="!customizer.mini_sidebar && customizer.Sidebar_drawer"
      class="sidebar-resize-handle"
      @mousedown="startSidebarResize"
      :class="{ 'resizing': isResizing }"
    >
    </div>
  </v-navigation-drawer>
</template>

<style scoped>
.sidebar-resize-handle {
  position: absolute;
  top: 0;
  right: 0;
  width: 4px;
  height: 100%;
  background: transparent;
  cursor: ew-resize;
  user-select: none;
  z-index: 1000;
  transition: background-color 0.2s ease;
}

.sidebar-resize-handle:hover,
.sidebar-resize-handle.resizing {
  background: rgba(var(--v-theme-primary), 0.3);
}

.sidebar-resize-handle::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 2px;
  height: 30px;
  background: rgba(var(--v-theme-on-surface), 0.3);
  border-radius: 1px;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.sidebar-resize-handle:hover::before,
.sidebar-resize-handle.resizing::before {
  opacity: 1;
}

.leftSidebar .v-navigation-drawer__content {
  position: relative;
}
</style>
