import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { apiFetch, getToken, setToken } from '../../api'
import {
  createOptimisticStudioArchiveItem,
  isOptimisticStudioArchiveId,
  mergeStudioArchiveItems,
  prependOptimisticStudioArchive,
  removeOptimisticStudioArchive,
  replaceOptimisticStudioArchiveId,
} from '../../studioArchive'
import { coerceJobGenerationId, waitForStudioJobResult } from '../../studioJobs'
import { apiJson, apiJsonOptional, isPlausibleTelegramBotToken, resolveDonationBalances } from './helpers'
import { refreshPendingArchiveImages, refreshPendingArchiveVideos } from './archivePoll'
import { mapGenModelsFromApi, normalizeStudioModelId, sameStudioModelId, waveModelParamsFromState } from './studioHelpers'
import * as actions from './actions'

function applyJobToOptimisticArchive(current, tempIds, accepted) {
  const realId = coerceJobGenerationId(accepted)
  let next = current
  if (realId && tempIds.length === 1) {
    return replaceOptimisticStudioArchiveId(next, tempIds[0], realId, {
      status: 'processing',
      job_id: accepted?.job_id ?? null,
    })
  }
  if (accepted?.job_id) {
    return next.map((g) =>
      tempIds.includes(g.id)
        ? { ...g, job_id: accepted.job_id, status: 'processing' }
        : g,
    )
  }
  for (const tid of tempIds) {
    next = removeOptimisticStudioArchive(next, tid)
  }
  return next
}

const CabinetCtx = createContext(null)

const PERM = {
  CHAT: 1,
  STUDIO_GENERATE: 2,
  STUDIO_MODELS: 4,
  INTEGRATIONS: 8,
  BILLING: 16,
  MANAGE_MEMBERS: 32,
}

function hasPerm(mask, bit) {
  return (Number(mask) & bit) === bit
}

function opRightsFromMe(me) {
  const mask = me?.permissions_mask ?? 0
  const owner = me?.is_workspace_owner
  return {
    chat: owner || hasPerm(mask, PERM.CHAT),
    studio: owner || hasPerm(mask, PERM.STUDIO_GENERATE),
    models: owner || hasPerm(mask, PERM.STUDIO_MODELS),
    keys: owner || hasPerm(mask, PERM.INTEGRATIONS),
    billing: owner || hasPerm(mask, PERM.BILLING),
  }
}

export function CabinetDataProvider({ children }) {
  const [ready, setReady] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [me, setMe] = useState(null)
  const [health, setHealth] = useState(null)
  const [conversations, setConversations] = useState([])
  const [messages, setMessages] = useState([])
  const [notes, setNotes] = useState([])
  const [models, setModels] = useState([])
  const [archiveImages, setArchiveImages] = useState([])
  const [archiveVideos, setArchiveVideos] = useState([])
  const [integrations, setIntegrations] = useState(null)
  const [donationOverview, setDonationOverview] = useState(null)
  const [donations, setDonations] = useState([])
  const [donationEvents, setDonationEvents] = useState([])
  const [billingPlans, setBillingPlans] = useState(null)
  const [creditHistory, setCreditHistory] = useState([])
  const [referral, setReferral] = useState(null)
  const [payoutSettings, setPayoutSettings] = useState(null)
  const [members, setMembers] = useState([])
  const [snippets, setSnippets] = useState([])
  const [chatterStats, setChatterStats] = useState(null)
  const [activeConvId, setActiveConvId] = useState(null)
  const [genModels, setGenModels] = useState([])
  const [selectedModelId, setSelectedModelId] = useState(null)
  const [selectedAspect, setSelectedAspect] = useState('9:16')
  const [uploadFiles, setUploadFiles] = useState({})
  const [uploadPreviewUrls, setUploadPreviewUrls] = useState({})
  const [cameraPresets, setCameraPresets] = useState([])
  const [slotArchivePicks, setSlotArchivePicks] = useState({})
  const [motionVideoFileId, setMotionVideoFileId] = useState(null)
  const [firstFrameGenId, setFirstFrameGenId] = useState(null)
  const [firstFrameUrl, setFirstFrameUrl] = useState(null)
  const [tributeEarnings, setTributeEarnings] = useState(null)
  const [donationsLoadError, setDonationsLoadError] = useState(null)
  const [creatorDonationAlert, setCreatorDonationAlert] = useState(null)
  const [donationEditId, setDonationEditId] = useState(null)
  const [modelsLoadError, setModelsLoadError] = useState(null)
  const wsRef = useRef(null)
  const refreshAllInFlightRef = useRef(false)
  const archiveImagesRef = useRef(archiveImages)
  const archiveVideosRef = useRef(archiveVideos)
  const donationOverviewRef = useRef(donationOverview)
  const donationEventsRef = useRef(donationEvents)

  useEffect(() => { archiveImagesRef.current = archiveImages }, [archiveImages])
  useEffect(() => { archiveVideosRef.current = archiveVideos }, [archiveVideos])
  useEffect(() => { donationOverviewRef.current = donationOverview }, [donationOverview])
  useEffect(() => { donationEventsRef.current = donationEvents }, [donationEvents])

  const run = useCallback(async (fn) => {
    setBusy(true)
    setError(null)
    try {
      const result = await fn()
      return result
    } catch (e) {
      const msg = e?.message || String(e)
      setError(msg)
    } finally {
      setBusy(false)
    }
  }, [])

  const loadConversations = useCallback(async () => {
    try {
      const rows = await apiJson('/api/conversations')
      setConversations(Array.isArray(rows) ? rows : [])
      return rows
    } catch (e) {
      if (String(e?.message || '').includes('403')) {
        setConversations([])
        return []
      }
      throw e
    }
  }, [])

  const loadMessages = useCallback(async (convId) => {
    if (!convId) return
    try {
      const [msgs, noteRows] = await Promise.all([
        apiJson(`/api/conversations/${convId}/messages?limit=50`),
        apiJsonOptional(`/api/conversations/${convId}/notes`, {}, []),
      ])
      setMessages(Array.isArray(msgs) ? msgs : [])
      setNotes(Array.isArray(noteRows) ? noteRows : [])
      setActiveConvId(convId)
      void apiFetch(`/api/conversations/${convId}/read`, { method: 'POST' })
      setConversations((prev) =>
        prev.map((c) => (c.id === convId ? { ...c, unread_count: 0 } : c)),
      )
    } catch (e) {
      setError(e.message || String(e))
    }
  }, [])

  const refreshArchiveFull = useCallback(async () => {
    const localImgPending = archiveImagesRef.current.filter(
      (g) => isOptimisticStudioArchiveId(g.id) || actions.isArchivePending(g),
    )
    const localVidPending = archiveVideosRef.current.filter(
      (g) => isOptimisticStudioArchiveId(g.id) || actions.isArchivePending(g),
    )
    const [imgs, vids] = await Promise.all([
      actions.refreshArchiveImages(),
      actions.refreshArchiveVideos(),
    ])
    setArchiveImages(mergeStudioArchiveItems(imgs, localImgPending))
    setArchiveVideos(mergeStudioArchiveItems(vids, localVidPending))
  }, [])

  const refreshArchivePending = useCallback(async () => {
    const [imgResult, vidResult] = await Promise.all([
      refreshPendingArchiveImages(archiveImagesRef.current),
      refreshPendingArchiveVideos(archiveVideosRef.current),
    ])
    if (imgResult.changed) setArchiveImages(imgResult.items)
    if (vidResult.changed) setArchiveVideos(vidResult.items)
    return imgResult.changed || vidResult.changed
  }, [])

  const refreshArchive = refreshArchiveFull

  const refreshAll = useCallback(async ({ busy: showBusy = false } = {}) => {
    if (!getToken()) {
      setReady(true)
      return
    }
    if (refreshAllInFlightRef.current) return
    refreshAllInFlightRef.current = true
    if (showBusy) setBusy(true)
    setError(null)
    try {
      const [
        meData,
        healthData,
        convs,
        modelsData,
        archiveImg,
        archiveVid,
        integrationsData,
        donationOv,
        dons,
        donEvents,
        plans,
        history,
        ref,
        payout,
        mems,
        snips,
        stats,
        modelOpts,
        camPresets,
        tributeSummary,
      ] = await Promise.all([
        apiJson('/api/auth/me'),
        apiJsonOptional('/api/health', {}, null),
        apiJsonOptional('/api/conversations', {}, []),
        apiJsonOptional('/api/studio/models', {}, null),
        actions.refreshArchiveImages().catch(() => []),
        actions.refreshArchiveVideos().catch(() => []),
        apiJsonOptional('/api/integrations', {}, null),
        apiJsonOptional('/api/creator-donations/overview', {}, null),
        apiJsonOptional('/api/creator-donations', {}, []),
        apiJsonOptional('/api/creator-donations/events?limit=50', {}, []),
        apiJsonOptional('/api/billing/plans', {}, null),
        apiJsonOptional('/api/workspace/credit-history?limit=40&skip=0', {}, []),
        apiJsonOptional('/api/referral/me', {}, null),
        apiJsonOptional('/api/creator-donations/payout-settings', {}, null),
        apiJsonOptional('/api/workspace/members', {}, []),
        apiJsonOptional('/api/workspace/snippets', {}, []),
        apiJsonOptional('/api/workspace/chatter-stats/summary', {}, null),
        apiJsonOptional('/api/studio/workflow/model-options', {}, null),
        apiJsonOptional('/api/studio/camera-presets', {}, []),
        apiJsonOptional('/api/tribute/earnings/summary', {}, null),
      ])

      setMe(meData)
      setHealth(healthData)
      setConversations(Array.isArray(convs) ? convs : [])
      if (meData?.workflow_demo_limited) {
        void actions.resolveDemoWorkflowWorkspaceId()
      }
      if (modelsData != null) {
        const modelRows = Array.isArray(modelsData) ? modelsData : []
        setModels(modelRows)
        setModelsLoadError(null)
        setSelectedModelId((prev) => {
          if (prev != null && modelRows.some((m) => sameStudioModelId(m.id, prev))) return prev
          return modelRows[0]?.id ?? null
        })
      } else {
        setModelsLoadError('Не удалось загрузить персонажей')
      }
      setArchiveImages(Array.isArray(archiveImg) ? archiveImg : [])
      setArchiveVideos(Array.isArray(archiveVid) ? archiveVid : [])
      setIntegrations(integrationsData)
      if (meData?.is_workspace_owner) {
        if (donationOv) {
          setDonationOverview(donationOv)
          setDonationsLoadError(null)
        } else {
          setDonationsLoadError('Не удалось загрузить донаты')
        }
      } else {
        setDonationOverview(donationOv)
        setDonationsLoadError(null)
      }
      setDonations(Array.isArray(dons) ? dons : [])
      setDonationEvents(Array.isArray(donEvents) ? donEvents : [])
      setBillingPlans(plans)
      setCreditHistory(Array.isArray(history?.items) ? history.items : Array.isArray(history) ? history : [])
      setReferral(ref)
      setPayoutSettings(payout)
      setMembers(Array.isArray(mems) ? mems : [])
      setSnippets(Array.isArray(snips) ? snips : [])
      setChatterStats(stats)
      setGenModels(mapGenModelsFromApi(modelOpts))
      setCameraPresets(Array.isArray(camPresets) ? camPresets : [])
      setTributeEarnings(tributeSummary)
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      refreshAllInFlightRef.current = false
      if (showBusy) setBusy(false)
      setReady(true)
    }
  }, [])

  const pickStudioModel = useCallback((id) => {
    setSelectedModelId(normalizeStudioModelId(id))
  }, [])

  const sendReply = useCallback(
    async (convId, text, replyToMessageId, imageFile) => {
      if (!convId || (!text?.trim() && !imageFile)) return
      const tempId = -Date.now()
      const previewUrl = imageFile ? URL.createObjectURL(imageFile) : null
      setMessages((prev) => [
        ...prev,
        {
          id: tempId,
          direction: 'outbound',
          text_original: text?.trim() || '',
          created_at: new Date().toISOString(),
          pending: true,
          attachments: previewUrl ? [{ url: previewUrl }] : [],
        },
      ])
      setError(null)
      try {
        if (imageFile) {
          await actions.sendReplyWithImage(convId, text, imageFile)
        } else {
          const body = { text: text.trim() }
          if (replyToMessageId) body.reply_to_message_id = replyToMessageId
          await apiJson(`/api/conversations/${convId}/reply`, {
            method: 'POST',
            body: JSON.stringify(body),
          })
        }
        await loadMessages(convId)
        await loadConversations()
      } catch (e) {
        setMessages((prev) => prev.filter((m) => Number(m.id) !== tempId))
        setError(e?.message || String(e))
      } finally {
        if (previewUrl) URL.revokeObjectURL(previewUrl)
      }
    },
    [loadConversations, loadMessages],
  )

  const saveNote = useCallback(
    async (convId, content, lang, tagLabel) => {
      if (!convId || !content?.trim()) throw new Error(lang === 'en' ? 'Enter note text' : 'Введите текст заметки')
      const text = content.trim()
      const payload = text.startsWith('[') ? text : `[${tagLabel}] ${text}`
      await run(async () => {
        await actions.saveConversationNote(convId, payload)
        const nr = await apiJson(`/api/conversations/${convId}/notes`)
        setNotes(Array.isArray(nr) ? nr : [])
      })
    },
    [run],
  )

  const analyzeNotes = useCallback(
    async (convId) => {
      await run(async () => {
        const data = await actions.analyzeConversationNotes(convId)
        setNotes(Array.isArray(data) ? data : [])
      })
    },
    [run],
  )

  const toggleReaction = useCallback(
    async (convId, messageId, emoji) => {
      await run(async () => {
        const data = await actions.toggleMessageReaction(convId, messageId, emoji)
        if (data?.id) {
          setMessages((prev) =>
            prev.map((m) => (Number(m.id) === Number(data.id) ? { ...m, ...data } : m)),
          )
        } else {
          await loadMessages(convId)
        }
      })
    },
    [run, loadMessages],
  )

  const disconnectIntegration = useCallback(
    async (type, connectionId) => {
      await run(async () => {
        if (type === 'tg') await actions.deleteTelegramConnection(connectionId)
        else if (type === 'fanvue') await actions.deleteFanvueConnection(connectionId)
        else if (type === 'tribute') await actions.deleteTributeConnection(connectionId)
        else throw new Error('Отключение недоступно для этой интеграции')
        await refreshAll()
      })
    },
    [run, refreshAll],
  )
  const saveIntegration = useCallback(
    async (type, fields) => {
      if (type === 'tg') {
        const token = (fields.token || '').trim()
        if (!token) {
          setError('Укажите токен Telegram-бота')
          return
        }
        if (!isPlausibleTelegramBotToken(token)) {
          setError(
            'Неверный формат токена BotFather. Скопируйте токен целиком (123456789:AAH…).',
          )
          return
        }
      }
      await run(async () => {
        if (type === 'wavespeed') await actions.saveWavespeedKey(fields.apiKey)
        else if (type === 'tg') await actions.addTelegramBot(fields.token, fields.modelId)
        else if (type === 'fanvue') {
          const data = await actions.startFanvueOAuth(fields.modelId)
          const url = data.authorize_url || data.url
          if (url) window.location.href = url
          else throw new Error('OAuth URL не получен')
          return
        } else if (type === 'tribute') {
          await actions.saveTributeKey(fields.apiKey, fields.label, fields.modelId)
        }
        await refreshAll()
      })
    },
    [run, refreshAll],
  )

  const saveDonation = useCallback(
    async (form, submit) => {
      const title = (form.title || '').trim()
      if (!title) {
        setError('Укажите заголовок доната')
        return
      }
      await run(async () => {
        const body = {
          title,
          description: form.description?.trim() || null,
          currency: 'RUB',
          min_amount_minor: form.minRub > 0 ? Math.round(form.minRub * 100) : null,
          studio_model_id: form.modelId ? Number(form.modelId) : null,
          submit: !!submit,
        }
        await actions.saveDonationLink(body, donationEditId)
        setDonationEditId(null)
        await refreshAll()
      })
    },
    [run, refreshAll, donationEditId],
  )

  const requestPayout = useCallback(async () => {
    await run(async () => {
      const { currency } = resolveDonationBalances(
        donationOverviewRef.current,
        donationEventsRef.current,
      )
      await actions.requestDonationPayout(currency)
      await refreshAll()
    })
  }, [run, refreshAll])

  const savePayoutSettings = useCallback(
    async (walletAddress, payoutAsset) => {
      await run(async () => {
        await actions.savePayoutSettings(walletAddress, payoutAsset)
        await refreshAll()
      })
    },
    [run, refreshAll],
  )

  const deleteConversation = useCallback(
    async (convId) => {
      await run(async () => {
        await actions.deleteConversation(convId)
        if (Number(activeConvId) === Number(convId)) setActiveConvId(null)
        await loadConversations()
      })
    },
    [run, activeConvId, loadConversations],
  )

  const updateSnippet = useCallback(
    async (snippetId, title, body) => {
      await run(async () => {
        await actions.updateSnippet(snippetId, title, body)
        await refreshAll()
      })
    },
    [run, refreshAll],
  )

  const deleteSnippet = useCallback(
    async (snippetId) => {
      await run(async () => {
        await actions.deleteSnippet(snippetId)
        await refreshAll()
      })
    },
    [run, refreshAll],
  )

  const payBilling = useCallback(
    async (method, product, creditsQuantity) => {
      await run(async () => {
        if (method === 'tribute') {
          const data = await actions.payTributeCheckout(product, creditsQuantity)
          if (data.payment_url) window.location.href = data.payment_url
          else if (data.telegram_deep_link) window.location.href = data.telegram_deep_link
          else throw new Error('Не получена ссылка Tribute')
        } else if (method === 'yookassa') {
          const data = await actions.payYookassa(product, creditsQuantity)
          if (data.confirmation_url) window.location.href = data.confirmation_url
          else throw new Error('Не получена ссылка на оплату')
        } else if (method === 'credits') {
          await actions.subscribeWithCredits(product)
          await refreshAll()
        }
      })
    },
    [run, refreshAll],
  )

  const createMember = useCallback(
    async (payload) => {
      await run(async () => {
        await actions.addWorkspaceMember(payload)
        await refreshAll()
      })
    },
    [run, refreshAll],
  )

  const updateMember = useCallback(
    async (memberId, payload) => {
      await run(async () => {
        await actions.updateWorkspaceMember(memberId, payload)
        await refreshAll()
      })
    },
    [run, refreshAll],
  )

  const deleteMember = useCallback(
    async (memberId) => {
      await run(async () => {
        await actions.deleteWorkspaceMember(memberId)
        await refreshAll()
      })
    },
    [run, refreshAll],
  )

  const createSnippet = useCallback(
    async (title, body) => {
      await run(async () => {
        await actions.addSnippet(title, body)
        await refreshAll()
      })
    },
    [run, refreshAll],
  )

  const generateImages = useCallback(
    async (appState, userPrompt) => {
      const mode = appState.imgMode || 'prompt'
      const model = models.find((m) => Number(m.id) === Number(selectedModelId))
      const promptExcerpt = (userPrompt || '').trim() || 'Генерация…'
      let tempIds = []
      let optimisticItems = []

      if (mode === 'carousel') {
        const count = Math.max(2, Math.min(8, Number(appState.carouselCount) || 4))
        for (let i = 0; i < count; i += 1) {
          const { item, tempId } = createOptimisticStudioArchiveItem({
            mediaKind: 'image',
            promptExcerpt: promptExcerpt || `Карусель ${i + 1}/${count}…`,
            studioModelId: selectedModelId,
            modelName: model?.name ?? null,
            outputAspect: selectedAspect,
          })
          tempIds.push(tempId)
          optimisticItems.push(item)
        }
      } else {
        const { item, tempId } = createOptimisticStudioArchiveItem({
          mediaKind: 'image',
          promptExcerpt,
          studioModelId: selectedModelId || null,
          modelName: model?.name ?? null,
          outputAspect: selectedAspect,
        })
        tempIds = [tempId]
        optimisticItems = [item]
      }

      setArchiveImages((prev) => {
        let next = prev
        for (const item of optimisticItems) {
          next = prependOptimisticStudioArchive(next, item)
        }
        return next
      })
      setError(null)

      try {
        const studioStore = {
          selectedModelId,
          selectedAspect,
          uploadFiles,
          slotArchivePicks,
          archiveImages,
          models,
        }
        let accepted
        if (mode === 'carousel') {
          if (!selectedModelId) throw new Error('Выберите персонажа')
          const src = actions.resolveSlotSource('carousel', 0, uploadFiles, slotArchivePicks)
          accepted = await actions.runCarouselGeneration({
            modelId: selectedModelId,
            count: Math.max(2, Math.min(8, Number(appState.carouselCount) || 4)),
            prompt: userPrompt,
            aspect: selectedAspect,
            nsfw: appState.contentMode === 'nsfw',
            ...waveModelParamsFromState(appState),
            existingGenerationId: src?.archiveId,
            imageFile: src?.file,
          })
        } else {
          accepted = await actions.runImageGeneration({
            appState,
            studioStore,
            userPrompt,
            workflowDemoLimited: Boolean(me?.workflow_demo_limited),
          })
        }
        setArchiveImages((prev) => applyJobToOptimisticArchive(prev, tempIds, accepted))
        void refreshArchivePending()
        void apiJson('/api/auth/me').then(setMe)
        if (accepted?.job_id) {
          const jobId = accepted.job_id
          const cleanupIds = [...tempIds]
          const maxWaitMs = mode === 'carousel'
            ? Math.max(8 * 60 * 1000, (Number(appState.carouselCount) || 4) * 4 * 60 * 1000)
            : 15 * 60 * 1000
          void waitForStudioJobResult(jobId, {
            maxWaitMs,
            onStatus: () => {
              void refreshArchivePending()
            },
          })
            .catch((e) => {
              setError(e?.message || String(e))
            })
            .finally(async () => {
              await refreshArchivePending()
              setArchiveImages((prev) => {
                let next = prev
                for (const tid of cleanupIds) {
                  next = removeOptimisticStudioArchive(next, tid)
                }
                return next
              })
              await refreshArchivePending()
              void refreshArchiveFull()
            })
        }
      } catch (e) {
        setArchiveImages((prev) => {
          let next = prev
          for (const tid of tempIds) {
            next = removeOptimisticStudioArchive(next, tid)
          }
          return next
        })
        setError(e?.message || String(e))
      }
    },
    [selectedModelId, selectedAspect, uploadFiles, slotArchivePicks, archiveImages, models, me?.workflow_demo_limited, refreshArchiveFull, refreshArchivePending],
  )

  const generateFirstFrame = useCallback(
    async (appState, description) => {
      setError(null)
      try {
        const { result } = await actions.runMotionFirstFrame({
          modelId: selectedModelId,
          aspect: selectedAspect,
          nsfw: appState.contentMode === 'nsfw',
          videoFile: uploadFiles['motion-video'],
          frameFile: uploadFiles['motion-frame'],
          existingGenerationId: appState.carouselPickId || firstFrameGenId,
          description,
        })
        if (result?.generation_id) setFirstFrameGenId(result.generation_id)
        const url = (result?.generated_image_url || result?.image_url || '').trim()
        if (url) setFirstFrameUrl(url)
        else if (result?.generation_id) {
          const hit = archiveImages.find((g) => Number(g.id) === Number(result.generation_id))
          const thumb = hit ? actions.archiveThumbUrl(hit) : ''
          if (thumb) setFirstFrameUrl(thumb)
        }
        await refreshArchiveFull()
        setMe(await apiJson('/api/auth/me'))
        return result
      } catch (e) {
        setError(e?.message || String(e))
        throw e
      }
    },
    [selectedModelId, selectedAspect, uploadFiles, firstFrameGenId, archiveImages, refreshArchiveFull],
  )

  const generateVideo = useCallback(
    async (appState, prompt) => {
      if (!selectedModelId) {
        setError('Выберите персонажа')
        return
      }
      if (!prompt?.trim()) {
        setError('Опишите движение')
        return
      }
      const model = models.find((m) => Number(m.id) === Number(selectedModelId))
      const { item, tempId } = createOptimisticStudioArchiveItem({
        mediaKind: 'video',
        promptExcerpt: prompt.trim(),
        studioModelId: selectedModelId,
        modelName: model?.name ?? null,
        outputAspect: appState.vidFormat || selectedAspect,
      })
      setArchiveVideos((prev) => prependOptimisticStudioArchive(prev, item))
      setError(null)
      try {
        const accepted = await actions.runMotionVideo({
          modelId: selectedModelId,
          prompt: prompt.trim(),
          aspect: appState.vidFormat || selectedAspect,
          resolution: appState.vidQuality || '1080',
          durationSeconds: Number(appState.vidTime) || 5,
          motionVideoFileId,
          frameFile: uploadFiles['motion-frame'],
          existingGenerationId: appState.carouselPickId || firstFrameGenId,
        })
        setArchiveVideos((prev) => applyJobToOptimisticArchive(prev, [tempId], accepted))
        void refreshArchivePending()
        setMe(await apiJson('/api/auth/me'))
      } catch (e) {
        setArchiveVideos((prev) => removeOptimisticStudioArchive(prev, tempId))
        setError(e?.message || String(e))
      }
    },
    [selectedModelId, selectedAspect, uploadFiles, motionVideoFileId, firstFrameGenId, models, refreshArchivePending],
  )

  const setUploadFile = useCallback((key, file) => {
    setUploadFiles((prev) => {
      const next = { ...prev }
      if (file) next[key] = file
      else delete next[key]
      return next
    })
    setUploadPreviewUrls((prev) => {
      const next = { ...prev }
      if (prev[key]) URL.revokeObjectURL(prev[key])
      if (file) next[key] = URL.createObjectURL(file)
      else delete next[key]
      return next
    })
    if (key === 'motion-video' && !file) setMotionVideoFileId(null)
  }, [])

  const uploadDrivingVideo = useCallback(
    async (file) => {
      await run(async () => {
        setUploadFile('motion-video', file)
        const id = await actions.uploadMotionDrivingVideo(file)
        setMotionVideoFileId(id)
        return id
      })
    },
    [run, setUploadFile],
  )

  const createCharacter = useCallback(
    async (name) => {
      await run(async () => {
        const data = await actions.createStudioModel(name)
        await refreshAll()
        return data
      })
    },
    [run, refreshAll],
  )

  const saveCharacterProfile = useCallback(
    async (charId, profileText) => {
      await run(async () => {
        await actions.patchStudioModel(charId, { profile_text: profileText })
        await refreshAll()
      })
    },
    [run, refreshAll],
  )

  const saveCharacterPersona = useCallback(
    async (charId, persona) => {
      await run(async () => {
        await actions.patchStudioModel(charId, { companion_persona: persona })
        await refreshAll()
      })
    },
    [run, refreshAll],
  )

  const uploadCharacterPhoto = useCallback(
    async (charId, file, kind) => {
      await run(async () => {
        await actions.uploadStudioModelImage(charId, file, kind)
        await refreshAll()
      })
    },
    [run, refreshAll],
  )

  const deleteCharacterPhoto = useCallback(
    async (charId, imageId) => {
      await run(async () => {
        await actions.deleteStudioModelImage(charId, imageId)
        await refreshAll()
      })
    },
    [run, refreshAll],
  )

  const updateCharacterPhotoKind = useCallback(
    async (charId, imageId, kind) => {
      await run(async () => {
        await actions.patchStudioModelImageKind(charId, imageId, kind)
        await refreshAll()
      })
    },
    [run, refreshAll],
  )

  const deleteCharacter = useCallback(
    async (charId) => {
      await run(async () => {
        await actions.deleteStudioModel(charId)
        await refreshAll()
      })
    },
    [run, refreshAll],
  )

  const uploadPhoneExif = useCallback(
    async (charId, role, file) => {
      await run(async () => {
        await actions.uploadPhoneExifReference(charId, role, file)
        await refreshAll()
      })
    },
    [run, refreshAll],
  )

  const deletePhoneExif = useCallback(
    async (charId, role) => {
      await run(async () => {
        await actions.deletePhoneExifReference(charId, role)
        await refreshAll()
      })
    },
    [run, refreshAll],
  )

  const saveCharacterExif = useCallback(
    async (charId, patch) => {
      await run(async () => {
        await actions.patchStudioModel(charId, patch)
        await refreshAll()
      })
    },
    [run, refreshAll],
  )

  const generateCharacterProfile = useCallback(
    async (images) => {
      return run(async () => actions.generateStudioModelProfile(images))
    },
    [run],
  )

  const logout = useCallback(() => {
    setToken(null)
    if (wsRef.current) {
      try {
        wsRef.current.close()
      } catch {
        /* ignore */
      }
      wsRef.current = null
    }
    window.location.assign('/login')
  }, [])

  useEffect(() => {
    if (!ready) return
    const pending =
      archiveImages.some(actions.isArchivePending) || archiveVideos.some(actions.isArchivePending)
    if (!pending) return
    const timer = window.setInterval(() => {
      void refreshArchivePending()
    }, 3_000)
    return () => window.clearInterval(timer)
  }, [ready, archiveImages, archiveVideos, refreshArchivePending])

  const refreshDonationOverview = useCallback(async (opts = {}) => {
    if (!me?.is_workspace_owner) return
    const overview = await apiJsonOptional('/api/creator-donations/overview', {}, null)
    if (!overview) {
      setDonationsLoadError('Не удалось загрузить донаты')
      return
    }
    setDonationsLoadError(null)
    const prevLatestId = donationOverviewRef.current?.latest_event_id ?? null
    const latestId = overview.latest_event_id
    const needsFullReload =
      !!opts.reloadPanels ||
      !Array.isArray(donationEventsRef.current) ||
      !donationEventsRef.current.length ||
      (latestId && latestId !== prevLatestId)

    setDonationOverview(overview)
    if (needsFullReload) {
      const [dons, donEvents] = await Promise.all([
        apiJsonOptional('/api/creator-donations', {}, []),
        apiJsonOptional('/api/creator-donations/events?limit=50', {}, []),
      ])
      setDonations(Array.isArray(dons) ? dons : [])
      setDonationEvents(Array.isArray(donEvents) ? donEvents : [])
    }

    if (latestId && overview.latest_event && latestId !== prevLatestId) {
      setCreatorDonationAlert(overview.latest_event)
    } else if (!latestId || latestId === prevLatestId) {
      setCreatorDonationAlert(null)
    }
  }, [me?.is_workspace_owner])

  useEffect(() => {
    if (!ready || !me?.is_workspace_owner) return
    void refreshDonationOverview({ reloadPanels: true })
    const timer = window.setInterval(() => {
      void refreshDonationOverview({ reloadPanels: false })
    }, 15_000)
    const onVis = () => {
      if (document.visibilityState === 'visible') {
        void refreshDonationOverview({ reloadPanels: true })
      }
    }
    document.addEventListener('visibilitychange', onVis)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVis)
    }
  }, [ready, me?.is_workspace_owner, refreshDonationOverview])

  useEffect(() => {
    void refreshAll({ busy: true })
  }, [refreshAll])

  useEffect(() => {
    const token = getToken()
    if (!token || !ready) return

    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    let closed = false
    let ws

    const connect = () => {
      if (closed) return
      ws = new WebSocket(`${proto}://${window.location.host}/api/ws?token=${encodeURIComponent(token)}`)
      wsRef.current = ws
      ws.addEventListener('message', (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          if (
            msg?.type === 'new_message' ||
            msg?.type === 'message_updated' ||
            msg?.type === 'conversation_updated' ||
            msg?.type === 'message_created'
          ) {
            if (msg?.type === 'new_message' && activeConvId) {
              setConversations((prev) =>
                prev.map((c) => (Number(c.id) === Number(activeConvId) ? { ...c, unread_count: 0 } : c)),
              )
            }
            void loadConversations()
            if (activeConvId && Number(msg.conversation_id) === Number(activeConvId)) {
              void loadMessages(activeConvId)
            }
          }
          if (
            msg?.type === 'credits_updated' ||
            msg?.type === 'studio_generation_updated' ||
            msg?.type === 'studio_job' ||
            msg?.type === 'studio_generation'
          ) {
            void apiJson('/api/auth/me').then(setMe)
            void refreshArchivePending()
          }
        } catch {
          /* ignore */
        }
      })
      ws.addEventListener('close', () => {
        if (!closed) setTimeout(connect, 3000)
      })
    }

    connect()
    return () => {
      closed = true
      try {
        ws?.close()
      } catch {
        /* ignore */
      }
    }
  }, [ready, activeConvId, loadConversations, loadMessages, refreshArchivePending])

  const value = useMemo(
    () => ({
      ready,
      busy,
      error,
      setError,
      me,
      health,
      conversations,
      messages,
      notes,
      models,
      archiveImages,
      archiveVideos,
      integrations,
      donationOverview,
      donations,
      donationEvents,
      billingPlans,
      creditHistory,
      referral,
      payoutSettings,
      members,
      snippets,
      chatterStats,
      activeConvId,
      setActiveConvId,
      genModels,
      selectedModelId,
      setSelectedModelId: pickStudioModel,
      modelsLoadError,
      selectedAspect,
      setSelectedAspect,
      uploadFiles,
      uploadPreviewUrls,
      setUploadFile,
      slotArchivePicks,
      setSlotArchivePicks,
      motionVideoFileId,
      setMotionVideoFileId,
      firstFrameGenId,
      firstFrameUrl,
      setFirstFrameUrl,
      tributeEarnings,
      donationsLoadError,
      creatorDonationAlert,
      setCreatorDonationAlert,
      donationEditId,
      setDonationEditId,
      opRights: opRightsFromMe(me),
      refreshAll,
      refreshArchive,
      refreshArchiveFull,
      refreshArchivePending,
      refreshDonationOverview,
      loadConversations,
      loadMessages,
      sendReply,
      saveNote,
      analyzeNotes,
      toggleReaction,
      cameraPresets,
      disconnectIntegration,
      saveDonation,
      requestPayout,
      savePayoutSettings,
      deleteConversation,
      payBilling,
      saveIntegration,
      createMember,
      updateMember,
      deleteMember,
      createSnippet,
      updateSnippet,
      deleteSnippet,
      generateImages,
      generateFirstFrame,
      generateVideo,
      uploadDrivingVideo,
      createCharacter,
      saveCharacterProfile,
      saveCharacterPersona,
      uploadCharacterPhoto,
      deleteCharacterPhoto,
      updateCharacterPhotoKind,
      deleteCharacter,
      uploadPhoneExif,
      deletePhoneExif,
      saveCharacterExif,
      generateCharacterProfile,
      logout,
    }),
    [
      ready,
      busy,
      error,
      me,
      health,
      conversations,
      messages,
      notes,
      models,
      archiveImages,
      archiveVideos,
      integrations,
      donationOverview,
      donations,
      donationEvents,
      billingPlans,
      creditHistory,
      referral,
      payoutSettings,
      members,
      snippets,
      chatterStats,
      activeConvId,
      genModels,
      selectedModelId,
      pickStudioModel,
      modelsLoadError,
      selectedAspect,
      uploadFiles,
      uploadPreviewUrls,
      setUploadFile,
      slotArchivePicks,
      motionVideoFileId,
      firstFrameGenId,
      firstFrameUrl,
      tributeEarnings,
      donationsLoadError,
      creatorDonationAlert,
      donationEditId,
      setDonationEditId,
      refreshAll,
      refreshArchive,
      refreshArchiveFull,
      refreshArchivePending,
      refreshDonationOverview,
      loadConversations,
      loadMessages,
      sendReply,
      saveNote,
      analyzeNotes,
      toggleReaction,
      cameraPresets,
      disconnectIntegration,
      saveDonation,
      requestPayout,
      savePayoutSettings,
      deleteConversation,
      payBilling,
      saveIntegration,
      createMember,
      updateMember,
      deleteMember,
      createSnippet,
      updateSnippet,
      deleteSnippet,
      generateImages,
      generateFirstFrame,
      generateVideo,
      uploadDrivingVideo,
      createCharacter,
      saveCharacterProfile,
      saveCharacterPersona,
      uploadCharacterPhoto,
      deleteCharacterPhoto,
      updateCharacterPhotoKind,
      deleteCharacter,
      uploadPhoneExif,
      deletePhoneExif,
      saveCharacterExif,
      generateCharacterProfile,
      logout,
    ],
  )

  return <CabinetCtx.Provider value={value}>{children}</CabinetCtx.Provider>
}

export function useCabinetData() {
  const ctx = useContext(CabinetCtx)
  if (!ctx) throw new Error('useCabinetData must be used inside CabinetDataProvider')
  return ctx
}
