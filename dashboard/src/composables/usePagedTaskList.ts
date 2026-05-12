import { computed, ref, shallowRef } from 'vue';

type Pagination = {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

type PageResult<T> = {
  items: T[];
  pagination?: Pagination | null;
};

type LoadPage<T> = (page: number, pageSize: number) => Promise<PageResult<T>>;

export function usePagedTaskList<T extends { id: string }>(options: {
  pageSize?: number;
  loadPage: LoadPage<T>;
}) {
  const pageSize = options.pageSize || 30;
  const items = shallowRef<T[]>([]);
  const pagination = ref<Pagination | null>(null);
  const loading = ref(false);
  const loadingMore = ref(false);
  let requestId = 0;

  const hasMore = computed(() => {
    if (!pagination.value) return false;
    return pagination.value.page < pagination.value.total_pages;
  });

  const loadedIds = computed(() => items.value.map(item => item.id));

  async function loadFirstPage() {
    const currentRequest = ++requestId;
    loading.value = true;
    try {
      const result = await options.loadPage(1, pageSize);
      if (currentRequest !== requestId) return;
      items.value = result.items || [];
      pagination.value = result.pagination || {
        page: 1,
        page_size: pageSize,
        total: items.value.length,
        total_pages: items.value.length ? 1 : 0,
      };
    } finally {
      if (currentRequest === requestId) loading.value = false;
    }
  }

  async function loadMore() {
    if (loading.value || loadingMore.value || !hasMore.value || !pagination.value) return;
    const currentRequest = ++requestId;
    const nextPage = pagination.value.page + 1;
    loadingMore.value = true;
    try {
      const result = await options.loadPage(nextPage, pageSize);
      if (currentRequest !== requestId) return;
      mergeItems(result.items || []);
      pagination.value = result.pagination || {
        ...pagination.value,
        page: nextPage,
      };
    } finally {
      if (currentRequest === requestId) loadingMore.value = false;
    }
  }

  function mergeItems(nextItems: T[]) {
    const byId = new Map(items.value.map(item => [item.id, item]));
    const nextById = new Map(nextItems.map(item => [item.id, item]));
    items.value = [
      ...items.value.map(item => (nextById.has(item.id) ? { ...item, ...nextById.get(item.id)! } : item)),
      ...nextItems.filter(item => !byId.has(item.id)),
    ];
  }

  function mergeSummaries(summaries: Partial<T & { id: string }>[]) {
    if (!summaries.length) return;
    const byId = new Map(summaries.map(item => [item.id, item]));
    items.value = items.value.map(item => {
      const summary = byId.get(item.id);
      return summary ? { ...item, ...summary } : item;
    });
  }

  function replaceItem(item: T) {
    if (!item?.id) return;
    const exists = items.value.some(existing => existing.id === item.id);
    items.value = exists
      ? items.value.map(existing => (existing.id === item.id ? { ...existing, ...item } : existing))
      : [item, ...items.value];
  }

  function reset() {
    requestId += 1;
    items.value = [];
    pagination.value = null;
    loading.value = false;
    loadingMore.value = false;
  }

  return {
    items,
    pagination,
    loading,
    loadingMore,
    hasMore,
    loadedIds,
    loadFirstPage,
    loadMore,
    mergeItems,
    mergeSummaries,
    replaceItem,
    reset,
  };
}
