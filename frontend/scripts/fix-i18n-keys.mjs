import fs from 'fs'

const file = 'src/App.tsx'
let s = fs.readFileSync(file, 'utf8')

const keyFixes = [
  ["t('integrationsExt.autoPerHour')", "t('integrationsExt.telegram.repliesPerHour')"],
  ["t('integrationsExt.refreshToken')", "t('integrationsExt.telegram.updateToken')"],
  ["t('integrationsExt.botToken')", "t('integrationsExt.telegram.botToken')"],
  ["t('integrationsExt.botTokenPh')", "t('integrationsExt.telegram.botTokenPlaceholder')"],
  ["tgEditConnectionId != null ? t('integrationsExt.saveToken') : t('integrationsExt.addBot')", "tgEditConnectionId != null ? t('integrationsExt.telegram.saveToken') : t('integrationsExt.telegram.addBot')"],
  ["t('integrationsExt.fanvueLead')", "t('integrationsExt.fanvue.body')"],
  ["t('integrationsExt.reconnect')", "t('integrationsExt.fanvue.reconnect')"],
  ["t('integrationsExt.modelNewConnection')", "t('integrationsExt.fanvue.newConnectionModel')"],
  ["t('integrationsExt.addFanvue')", "t('integrationsExt.fanvue.addOAuth')"],
  ["t('integrationsExt.inDevelopment')", "t('integrationsExt.instagram.inDevelopment')"],
  ["t('integrationsExt.igDevBanner')", "t('integrationsExt.instagram.inDevelopmentBanner')"],
  ["t('integrationsExt.igSteps')", "t('integrationsExt.instagram.step1')"],
  ["t('integrationsExt.igDmHint')", "t('integrationsExt.instagram.step2')"],
  ["t('integrationsExt.addInstagram')", "t('integrationsExt.instagram.addOAuth')"],
  ['i18nKey="integrationsExt.tributeLead"', 'i18nKey="integrationsExt.tribute.body"'],
  ['i18nKey="integrationsExt.tributeStep1"', 'i18nKey="integrationsExt.tribute.step1"'],
  ['i18nKey="integrationsExt.tributeStep2"', 'i18nKey="integrationsExt.tribute.step2"'],
  ['i18nKey="integrationsExt.tributeStep3"', 'i18nKey="integrationsExt.tribute.step3"'],
  ["t('integrationsExt.tributeStep4')", "t('integrationsExt.tribute.step4')"],
  ["t('integrationsExt.connectionN'", "t('integrationsExt.tribute.connectionFallback'"],
  ["t('integrationsExt.webhookUrl')", "t('integrationsExt.tribute.webhookLabel')"],
  ["t('integrationsExt.updateKey')", "t('integrationsExt.tribute.updateKey')"],
  ["t('integrationsExt.llmTitle')", "t('integrationsExt.llm.title')"],
  ["t('integrationsExt.llmOk')", "t('integrationsExt.llm.badgeConfigured')"],
  ["t('integrationsExt.llmBad')", "t('integrationsExt.llm.badgeNotConfigured')"],
  ["t('integrationsExt.llmBase')", "t('integrationsExt.llm.baseUrl')"],
  ["t('integrationsExt.companionFbTitle')", "t('integrationsExt.companionFeedback.title')"],
  ["t('integrationsExt.companionFbCount'", "t('integrationsExt.companionFeedback.reportsCount'"],
  ["t('integrationsExt.companionFbLead')", "t('integrationsExt.companionFeedback.body')"],
  ["t('integrationsExt.companionFbEmpty')", "t('integrationsExt.companionFeedback.empty')"],
  ["t('integrationsExt.pushTitle')", "t('notifications.title')"],
  ["t('integrationsExt.pushBody')", "t('notifications.body')"],
  ["t('integrationsExt.pushDenied')", "t('notifications.denied')"],
  ["t('integrationsExt.pushServerOff')", "t('notifications.serverDisabled')"],
  ["t('integrationsExt.noIntegrationsPerm')", "t('cabinet.integrations.lead')"], // fallback - need a key; use perm message
  ["t('modelsExt.uploadN'", "t('modelsExt.uploadPhotos'"],
  ["t('modelsExt.appearance')", "t('modelsExt.profileLabel')"],
  ["t('modelsExt.agePh')", "t('modelsExt.agePlaceholder')"],
  ["t('modelsExt.cityPh')", "t('modelsExt.cityPlaceholder')"],
  ["t('modelsExt.countryPh')", "t('modelsExt.countryPlaceholder')"],
  ["t('modelsExt.personalityPh')", "t('modelsExt.personalityPlaceholder')"],
  ["t('modelsExt.hobbiesPh')", "t('modelsExt.hobbiesPlaceholder')"],
  ["t('modelsExt.interestsPh')", "t('modelsExt.interestsPlaceholder')"],
  ["t('modelsExt.lifestylePh')", "t('modelsExt.lifestylePlaceholder')"],
  ["t('modelsExt.chatStyle')", "t('modelsExt.speakingStyle')"],
  ["t('modelsExt.chatStylePh')", "t('modelsExt.speakingStylePlaceholder')"],
  ["t('modelsExt.backstoryPh')", "t('modelsExt.backstoryPlaceholder')"],
  ["t('modelsExt.exportPhone')", "t('modelsExt.exportPhoneTitle')"],
  ["t('modelsExt.exportPhoneHint')", "t('modelsExt.exportPhoneLead')"],
  ["t('modelsExt.studioModels')", "t('modelsExt.teamStudioModels')"],
  ["t('modelsExt.membersEmpty')", "t('team.membersEmpty')"],
  ["t('health.tgUnreachable')", "t('health.telegramUnreachable')"],
  ["t('health.apiDown')", "t('health.telegramUnreachable')"],
  ["t('health.integrationsHint')", "t('health.webhookIntegrations')"],
  ["t('health.tgProxy')", "t('health.telegramProxy')"],
  ["t('health.studioLlmDown')", "t('health.studioTextUnavailable')"],
  ["events: tributeEarnings.event_count", "eventsPart: tributeEarnings.event_count"],
  ["tc('templates.", "t('modelsExt.snippets"],
  ["tc('notes.", "t('modelsExt."], // wrong - don't do this
]

// filter bad entries
const safe = keyFixes.filter(([a]) => !a.includes('notes.') && !a.includes('templates.'))

let n = 0
for (const [from, to] of safe) {
  if (s.includes(from)) {
    s = s.split(from).join(to)
    n++
  }
}
fs.writeFileSync(file, s)
console.log('fixed', n, 'key paths')
