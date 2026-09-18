import { ref, computed, onMounted, onUnmounted, isRef, watch } from 'vue';

export function useSticky(actionBarRef, offsetModifier = 24, customContainerRef = null, offsetScroll = 0) {
  const stickyTopNumber = ref(180);
  const actionBarHeight = ref(180);
  const scrollContainer = ref(null);
  let resizeObserver = null;

  const stickyConfig = computed(() => {
    if (!scrollContainer.value) return false;
    return {
      offsetHeader: stickyTopNumber.value,
      offsetScroll: typeof offsetScroll === 'number' ? offsetScroll : 0,
      getContainer: () => scrollContainer.value
    };
  });

  onMounted(() => {
    const getContainerEl = () => (customContainerRef ? (isRef(customContainerRef) ? customContainerRef.value : customContainerRef) : null);
    scrollContainer.value = getContainerEl() || document.querySelector('.ant-layout-content');
    const getTargetEl = () => (isRef(actionBarRef) ? actionBarRef.value : actionBarRef);

    const updateSticky = () => {
      const el = getTargetEl();
      if (el && typeof el.getBoundingClientRect === 'function') {
        const rect = el.getBoundingClientRect();
        if (rect.height > 0) {
          stickyTopNumber.value = rect.height;
          actionBarHeight.value = rect.height;
        }
      }
    };
    resizeObserver = new ResizeObserver(updateSticky);
    const targetEl = getTargetEl();
    if (targetEl) resizeObserver.observe(targetEl);
    updateSticky();

    if (isRef(actionBarRef)) {
      watch(
        () => actionBarRef.value,
        (newEl, oldEl) => {
          if (oldEl && resizeObserver) resizeObserver.unobserve(oldEl);
          if (newEl && resizeObserver) {
            resizeObserver.observe(newEl);
            updateSticky();
          }
        }
      );
    }
  });

  onUnmounted(() => {
    if (resizeObserver) resizeObserver.disconnect();
  });

  return {
    stickyConfig,
    actionBarHeight,
    stickyTopNumber,
    scrollContainer
  };
}
