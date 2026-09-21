import { createI18n } from 'vue-i18n'
import languages from '../../../locales/languages.json'

const localeFiles = import.meta.glob('../../../locales/!(languages).json', { eager: true })

const messages = {}
const availableLocales = []

for (const path in localeFiles) {
  const key = path.match(/\/([^/]+)\.json$/)[1]
  if (languages[key]) {
    messages[key] = localeFiles[path].default
    availableLocales.push({ key, label: languages[key].label })
  }
}

// Locale persistence: dedicated HiveMind key (v2) so stale language
// preferences from earlier builds are ignored. Default: English.
const LOCALE_KEY = 'hivemind-locale'
const savedLocale = localStorage.getItem(LOCALE_KEY) || 'en'

const i18n = createI18n({
  legacy: false,
  locale: savedLocale,
  fallbackLocale: 'en',
  messages
})

// keep the key exported for the switcher
export const LOCALE_STORAGE_KEY = LOCALE_KEY

export { availableLocales }
export default i18n
