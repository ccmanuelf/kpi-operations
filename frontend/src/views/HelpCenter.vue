<template>
  <v-container fluid class="help-center pa-0">
    <v-row no-gutters>
      <!-- Sidebar: doc list + search -->
      <v-col cols="12" md="3" class="help-sidebar pa-4">
        <v-text-field
          v-model="search"
          :placeholder="t('help.searchPlaceholder')"
          prepend-inner-icon="mdi-magnify"
          variant="outlined"
          density="compact"
          clearable
          hide-details
          class="mb-4"
        />

        <v-list density="compact" nav>
          <v-list-subheader>{{ t('help.contents') }}</v-list-subheader>
          <v-list-item
            v-for="doc in filteredDocs"
            :key="doc.id"
            :active="doc.id === activeId"
            :title="doc.title"
            :subtitle="doc.id === 'README' ? t('help.tableOfContents') : doc.filename"
            @click="selectDoc(doc.id)"
            :prepend-icon="iconForDoc(doc)"
          />
          <v-list-item
            v-if="!filteredDocs.length"
            :title="t('help.noResults')"
            disabled
            prepend-icon="mdi-information-outline"
          />
        </v-list>

        <v-divider class="my-4" />
        <div class="text-caption text-medium-emphasis">
          {{ t('help.sourceLocation') }}
        </div>
      </v-col>

      <!-- Main content: rendered markdown -->
      <v-col cols="12" md="9" class="help-content pa-6">
        <div v-if="activeDoc" class="help-content-inner">
          <div class="d-flex align-center mb-4">
            <h1 class="text-h4">{{ activeDoc.title }}</h1>
            <v-spacer />
            <v-btn
              variant="text"
              size="small"
              prepend-icon="mdi-content-copy"
              @click="copyAnchor"
            >
              {{ t('help.copyLink') }}
            </v-btn>
          </div>
          <article class="markdown-body" v-html="renderedHtml" @click="onContentClick" />
        </div>
        <div v-else class="text-medium-emphasis pa-12 text-center">
          {{ t('help.selectDoc') }}
        </div>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useNotificationStore } from '@/stores/notificationStore'
import { marked } from 'marked'
import { getAllDocs, getDocById, getDefaultDocId } from '@/help'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const notify = useNotificationStore()

const docs = getAllDocs()
const activeId = ref(getDefaultDocId())
const search = ref('')

// Configure marked: GitHub-flavored markdown, breaks-as-newlines.
marked.use({
  gfm: true,
  breaks: false,
})

function iconForDoc(doc) {
  if (doc.id === 'README') return 'mdi-book-open-variant'
  if (doc.id === 'glossary') return 'mdi-format-list-bulleted-type'
  const map = {
    '01': 'mdi-rocket-launch',
    '02': 'mdi-view-dashboard',
    '03': 'mdi-keyboard',
    '04': 'mdi-calendar-clock',
    '05': 'mdi-clipboard-list',
    '06': 'mdi-bell-alert',
    '07': 'mdi-chart-timeline-variant',
    '08': 'mdi-file-chart',
    '09': 'mdi-shield-crown',
    '10': 'mdi-account-key',
  }
  return map[doc.order] || 'mdi-file-document-outline'
}

const filteredDocs = computed(() => {
  if (!search.value) return docs
  const q = search.value.toLowerCase()
  return docs.filter((d) =>
    d.title.toLowerCase().includes(q) ||
    d.body.toLowerCase().includes(q) ||
    d.id.toLowerCase().includes(q),
  )
})

const activeDoc = computed(() => getDocById(activeId.value))

const renderedHtml = computed(() => {
  if (!activeDoc.value) return ''
  // Rewrite relative .md links to Vue-Router paths so clicking them
  // stays inside the Help Center. e.g. `(02-dashboards.md)` →
  // `(/help/02-dashboards)`. The click handler below intercepts and
  // navigates without a full page load.
  const body = activeDoc.value.body.replace(
    /\]\(([^)]+\.md)(#[^)]+)?\)/g,
    (_match, file, anchor) => {
      const targetId = file.replace(/\.md$/, '')
      return `](/help/${targetId}${anchor || ''})`
    },
  )
  return marked.parse(body)
})

// Intercept clicks on rendered markdown links — keep Help-Center links
// SPA, let external links open normally.
function onContentClick(ev) {
  const a = ev.target.closest('a[href]')
  if (!a) return
  const href = a.getAttribute('href') || ''
  if (href.startsWith('/help/')) {
    ev.preventDefault()
    const id = href.replace(/^\/help\//, '').split('#')[0]
    selectDoc(id)
  }
  // External links + in-page anchors fall through to default behavior.
}

function selectDoc(id) {
  activeId.value = id
  // Update the URL hash (we use hash routing here so deep-links work
  // without configuring Vue Router for nested routes per doc).
  router.push({ name: 'help', params: { id } }).catch(() => {})
  // Scroll to top of content
  nextTick(() => {
    const el = document.querySelector('.help-content-inner')
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

function copyAnchor() {
  if (!activeDoc.value) return
  const url = window.location.origin + '/help/' + activeDoc.value.id
  navigator.clipboard.writeText(url).then(() => {
    notify.showSuccess(t('help.linkCopied'))
  }).catch(() => {
    notify.showError(t('help.linkCopyFailed'))
  })
}

// Sync URL → active doc on mount + on route change
function syncFromRoute() {
  const id = route.params.id
  if (id && getDocById(id)) {
    activeId.value = id
  } else {
    activeId.value = getDefaultDocId()
  }
}

onMounted(syncFromRoute)
watch(() => route.params.id, syncFromRoute)
</script>

<style scoped>
.help-center {
  min-height: calc(100vh - 64px);
}

.help-sidebar {
  border-right: 1px solid rgb(var(--v-theme-outline-variant));
  background-color: rgb(var(--v-theme-surface));
  position: sticky;
  top: 64px;
  align-self: flex-start;
  max-height: calc(100vh - 64px);
  overflow-y: auto;
}

.help-content {
  background-color: rgb(var(--v-theme-background));
}

.help-content-inner {
  max-width: 920px;
  margin: 0 auto;
}
</style>

<style>
/* Markdown body styling — applied globally so `v-html` rendered HTML
   gets the right look. Scoped <style> wouldn't pierce the v-html. */
.markdown-body {
  font-size: 15px;
  line-height: 1.7;
  color: rgb(var(--v-theme-on-surface));
}
.markdown-body h1 {
  font-size: 1.875rem;
  margin-top: 2rem;
  margin-bottom: 1rem;
  font-weight: 600;
}
.markdown-body h2 {
  font-size: 1.5rem;
  margin-top: 2rem;
  margin-bottom: 0.75rem;
  font-weight: 600;
  border-bottom: 1px solid rgb(var(--v-theme-outline-variant));
  padding-bottom: 0.3rem;
}
.markdown-body h3 {
  font-size: 1.25rem;
  margin-top: 1.5rem;
  margin-bottom: 0.5rem;
  font-weight: 600;
}
.markdown-body h4 {
  font-size: 1.05rem;
  margin-top: 1.25rem;
  margin-bottom: 0.5rem;
  font-weight: 600;
}
.markdown-body p {
  margin: 0.75rem 0;
}
.markdown-body ul,
.markdown-body ol {
  margin: 0.75rem 0;
  padding-left: 1.5rem;
}
.markdown-body li {
  margin: 0.25rem 0;
}
.markdown-body code {
  background-color: rgba(127, 127, 127, 0.15);
  border-radius: 3px;
  padding: 0.1rem 0.35rem;
  font-size: 0.9em;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
}
.markdown-body pre {
  background-color: rgba(127, 127, 127, 0.15);
  border-radius: 6px;
  padding: 1rem;
  overflow-x: auto;
  margin: 1rem 0;
}
.markdown-body pre code {
  background: none;
  padding: 0;
  font-size: 0.85rem;
}
.markdown-body blockquote {
  border-left: 4px solid rgb(var(--v-theme-primary));
  padding: 0.5rem 1rem;
  color: rgb(var(--v-theme-on-surface-variant));
  margin: 1rem 0;
}
.markdown-body table {
  border-collapse: collapse;
  margin: 1rem 0;
  font-size: 0.92em;
  width: 100%;
}
.markdown-body th,
.markdown-body td {
  border: 1px solid rgb(var(--v-theme-outline-variant));
  padding: 0.45rem 0.75rem;
  text-align: left;
  vertical-align: top;
}
.markdown-body th {
  background-color: rgba(127, 127, 127, 0.1);
  font-weight: 600;
}
.markdown-body a {
  color: rgb(var(--v-theme-primary));
  text-decoration: none;
}
.markdown-body a:hover {
  text-decoration: underline;
}
.markdown-body hr {
  border: 0;
  border-top: 1px solid rgb(var(--v-theme-outline-variant));
  margin: 1.5rem 0;
}
.markdown-body img {
  max-width: 100%;
  height: auto;
}
</style>
