<template>
  <span class="language-switcher">
    <label class="language-label" for="arl-interface-language">{{ t('language.select') }}</label>
    <a-select
      id="arl-interface-language"
      class="language-control"
      :value="locale"
      :options="SUPPORTED_LOCALES"
      :title="t('language.select')"
      @change="setLocale"
    />
  </span>
</template>

<script setup>
import { useI18n } from 'vue-i18n';
import { setLocale, SUPPORTED_LOCALES } from '@/i18n';

const { t, locale } = useI18n({ useScope: 'global' });
</script>

<style scoped>
.language-switcher {
  display: inline-flex;
  width: 124px;
  flex-shrink: 0;
}
.language-control {
  width: 100%;
}
.language-label {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
</style>
