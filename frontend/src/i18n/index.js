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

// Locale persistence: dedicated HiveMind key so stale language
// preferences from earlier builds are ignored. Default: English.
// Escape hatch: /?lang=en (or zh, fr, …) overrides everything.
const LOCALE_KEY = 'hivemind-locale'
const SUPPORTED = Object.keys(languages)
const urlLang = new URLSearchParams(window.location.search).get('lang')
const storedLang = localStorage.getItem(LOCALE_KEY)
const initialLocale =
  (urlLang && SUPPORTED.includes(urlLang) && urlLang) ||
  (storedLang && SUPPORTED.includes(storedLang) && storedLang) ||
  'en'

const i18n = createI18n({
  legacy: false,
  locale: initialLocale,
  fallbackLocale: 'en',
  messages
})

if (urlLang && SUPPORTED.includes(urlLang)) {
  localStorage.setItem(LOCALE_KEY, urlLang)
}

// keep the key exported for the switcher
export const LOCALE_STORAGE_KEY = LOCALE_KEY

export { availableLocales }
export default i18n
