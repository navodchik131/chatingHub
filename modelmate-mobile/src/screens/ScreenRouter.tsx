import { LinearGradient } from 'expo-linear-gradient';
import { useEffect } from 'react';
import { ActivityIndicator, Image, Linking, Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { TextInput } from 'react-native-gesture-handler';
import {
  IcoBack,
  IcoBolt,
  IcoCard,
  IcoChat,
  IcoChevron,
  IcoCog,
  IcoFilm,
  IcoHeart,
  IcoImage,
  IcoPlug,
  IcoPlus,
  IcoSend,
  IcoShield,
  IcoStar,
  IcoUser,
  IcoUsers,
} from '@/src/components/Icons';
import {
  CheckRow,
  ChipPicker,
  ChipRowInteractive,
  DashedAddButton,
  DropSlot,
  DropSlotWide,
  FieldLabel,
  GenLoadingCard,
  GenResultCard,
  GhostButton,
  LimeButton,
  NumberChipPicker,
  SegmentedToggle,
  SelectChip,
  TabChip,
  TextAreaField,
  TextField,
} from '@/src/components/forms';
import {
  Avatar,
  Card,
  ChatRow,
  Kpi,
  MenuRow,
  Pill,
  ProgressBar,
  ScreenScroll,
  SectionLabel,
  StudioRow,
  StudioShortcut,
  TopBar,
} from '@/src/components/ui';
import { useAppData } from '@/src/context/AppDataProvider';
import { useAppSettings } from '@/src/context/AppSettingsContext';
import { useNav } from '@/src/context/NavigationContext';
import {
  modeDefs,
  rightsDefs,
  slotLabels,
} from '@/src/data/mock';
import { AuthScreen } from '@/src/screens/AuthScreen';
import {
  SettingsBiometricScreen,
  SettingsLanguageScreen,
  SettingsMainScreen,
  SettingsPushScreen,
} from '@/src/screens/SettingsScreens';
import {
  CAROUSEL_COUNTS,
  enginesForMode,
  IMG_FORMATS,
  VID_DURATIONS,
  VID_QUALITIES,
} from '@/src/navigation/types';
import { color, font, gradients } from '@/src/styles/tokens';
import { pickImage, pickVideo } from '@/src/utils/mediaPicker';
import { RemoteImage } from '@/src/components/RemoteImage';
import { SwipeableChatRow } from '@/src/components/SwipeableChatRow';
import { ThreadView } from '@/src/components/ThreadView';
import { resolveMediaUrl } from '@/src/api/config';
import { charFieldsFromModel, fmtDateShort, fmtMoney, fmtRub } from '@/src/api/helpers';
import { mapCharPhotoTags, mapIntegrationConnections } from '@/src/api/mappers';
import {
  computeCarouselModeCardCost,
  computeImageGenerationCost,
  computeVideoGenerationCost,
} from '@/src/studio/generationCost';

const adminPlanChips = ['Solo', 'Studio', 'Agency', 'Pro Solo', 'Pro Pro'];

function modeIcon(kind: string, rgb: string, size = 16) {
  const stroke = `rgb(${rgb})`;
  switch (kind) {
    case 'user': return <IcoUser size={size} stroke={stroke} />;
    case 'star': return <IcoStar size={size} stroke={stroke} />;
    case 'bolt': return <IcoBolt size={size} stroke={stroke} />;
    default: return <IcoImage size={size} stroke={stroke} />;
  }
}

function connIcon(kind: string, rgb: string) {
  const stroke = `rgb(${rgb})`;
  switch (kind) {
    case 'bolt': return <IcoBolt size={16} stroke={stroke} />;
    case 'heart': return <IcoHeart size={16} stroke={stroke} />;
    case 'card': return <IcoCard size={16} stroke={stroke} />;
    default: return <IcoChat size={16} stroke={stroke} />;
  }
}

export function ScreenRouter() {
  const nav = useNav();
  const app = useAppData();
  const { t, locale } = useAppSettings();
  const {
    userName,
    userEmail,
    me,
    conversations,
    conversationFolders,
    messages,
    models,
    rawModels,
    modelNames,
    archiveTiles,
    connectionsList,
    rawIntegrations,
    overviewKpis,
    billingPlans,
    creditPacks,
    creditHistory,
    donations,
    donationEvents,
    donationBalances,
    donationAvailableMinor,
    payoutWallet,
    members,
    chatterStats,
    adminStats,
    adminUsers,
    exifBotStats,
    igBotStats,
    exifBotUsers,
    igBotUsers,
    health,
    motionVideoFileId,
    setMotionVideoFileId,
    firstFrameUrl,
    generateFirstFrame,
    setUploadFile,
    uploadFiles,
    error: appError,
    busy: appBusy,
    startGeneration,
    loadThread,
    clearActiveThread,
    refreshConversations,
    sendThreadMessage,
    createConversationFolder,
    renameConversationFolder,
    deleteConversationFolder,
    setFolderMembers,
    addConversationToFolder,
    saveCharacterFields,
    createCharacter,
    generateCharacterProfile,
    savePayoutWallet,
    requestPayout,
    saveDonationDraft,
    addOperator,
    updateOperator,
    deleteOperator,
    saveConnection,
    disconnectConnection,
    openBillingCheckout,
    searchAdminUsers,
    saveAdminSubscription,
    adjustAdminCredits,
    sendBroadcast,
    genResults,
    refreshAll,
    refreshArchive,
  } = app;
  const { cur, pop, push, resetTo, openThread, startGen, regen, patch, chatIdx } = nav;
  const threadConvId = conversations[chatIdx]?.id ?? null;

  useEffect(() => {
    if (cur === 'thread' && threadConvId) {
      void loadThread(threadConvId);
      return;
    }
    clearActiveThread();
  }, [cur, threadConvId, loadThread, clearActiveThread]);

  useEffect(() => {
    if (cur === 'dialogs' || cur === 'overview') {
      void refreshConversations();
    }
  }, [cur, refreshConversations]);

  useEffect(() => {
    if (!cur.startsWith('character:')) return;
    const id = cur.slice(10);
    const raw = models.find((m) => m.id === id)?.raw;
    if (!raw) return;
    patch({ charFields: charFieldsFromModel(raw) });
  }, [cur, models, patch]);

  useEffect(() => {
    if (cur === 'archive' || cur === 'archive-item') void refreshArchive();
  }, [cur, refreshArchive]);

  const patchGenStatus = (key: string, status: 'loading' | 'done' | null) => {
    if (status === null) {
      const next = { ...nav.genStatus };
      delete next[key];
      patch({ genStatus: next });
      return;
    }
    patch({ genStatus: { ...nav.genStatus, [key]: status } });
  };

  const runGen = (key: string) => {
    startGen(key);
    void startGeneration(key, nav, patchGenStatus);
  };

  const slotFileKey = (modeId: string, label: string, index: number) => {
    if (modeId === 'outfit') return index === 0 ? 'ref' : 'outfit-cloth';
    if (modeId === 'loc') return index === 0 ? 'ref' : 'location-photo';
    if (modeId === 'carousel') return 'carousel';
    return 'ref';
  };

  if (cur === 'auth') {
    return <AuthScreen />;
  }

  if (cur === 'overview') {
    return (
      <ScreenScroll>
        <TopBar title={`Привет, ${userName} 👋`} />
        {appError ? <Text style={s.errorBanner}>{appError}</Text> : null}
        <View style={s.kpiRow}>
          <Kpi label="КРЕДИТЫ" value={overviewKpis.credits} accent={color.lime} sub={overviewKpis.creditsSub} />
          <Kpi label="ПОДПИСКА" value={overviewKpis.plan} accent={color.green} sub={overviewKpis.planSub} />
          <Kpi label="ДОНАТЫ" value={overviewKpis.donations} accent={color.pink} sub={overviewKpis.donationsSub} />
          <Kpi label="ДИАЛОГИ" value={overviewKpis.dialogs} sub={overviewKpis.dialogsSub} />
        </View>
        <SectionLabel>СТУДИЯ — ЧТО СДЕЛАТЬ?</SectionLabel>
        <Pressable onPress={() => push('images')}>
          <StudioShortcut icon={<IcoImage size={17} stroke={color.lime} />} iconBg="rgba(215,244,82,0.12)" iconColor={color.lime} title="Картинки" subtitle="6 режимов генерации" />
        </Pressable>
        <Pressable onPress={() => push('video')}>
          <StudioShortcut icon={<IcoFilm size={17} stroke={color.purple} />} iconBg="rgba(192,132,252,0.12)" iconColor={color.purple} title="Видео" subtitle="Оживить кадр" />
        </Pressable>
        <SectionLabel>НЕДАВНИЕ ДИАЛОГИ</SectionLabel>
        <Card style={s.recentList}>
          {conversations.slice(0, 2).map((d, i) => (
            <View key={d.id}>
              {i > 0 ? <View style={s.divider} /> : null}
              <ChatRow
                name={d.name}
                platform={d.plat}
                message={d.msg}
                gradIndex={d.gradIndex}
                vip={d.vip}
                unread={d.unread}
                onPress={() => openThread(i)}
              />
            </View>
          ))}
        </Card>
      </ScreenScroll>
    );
  }

  if (cur === 'dialogs') {
    const folderTabs = [
      { id: 'all' as const, label: 'Все' },
      ...conversationFolders.map((f) => ({ id: f.id as number, label: f.name })),
    ];
    const activeFolderId = nav.dialogFolderId;
    const activeFolder = conversationFolders.find((f) => f.id === activeFolderId);
    const folderSet = activeFolderId === 'all'
      ? null
      : new Set((activeFolder?.conversation_ids || []).map(Number));
    const shown = conversations
      .map((d, i) => ({ d, i }))
      .filter(({ d }) => !folderSet || (d.id != null && folderSet.has(Number(d.id))));
    const swipeEnabled = conversationFolders.length > 0;

    const openFolderEdit = (folderId: number) => {
      const folder = conversationFolders.find((f) => f.id === folderId);
      if (!folder) return;
      patch({
        folderEditId: folderId,
        folderEditName: folder.name,
        folderEditSelected: [...(folder.conversation_ids || [])],
        swipeOpenDialogId: null,
        stack: [...nav.stack, 'folder-edit'],
      });
    };

    return (
      <ScreenScroll contentStyle={s.dialogsScroll}>
        <View style={s.dialogsHeader}>
          <Text style={s.dialogsTitle}>Диалоги</Text>
          <Pressable
            onPress={() => push('newfolder')}
            style={s.folderAddBtn}
            hitSlop={8}
          >
            <IcoPlus size={20} stroke={color.lime} />
          </Pressable>
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.folderTabs}>
          {folderTabs.map((f) => {
            const active = activeFolderId === f.id;
            return (
              <Pressable
                key={String(f.id)}
                onPress={() => patch({ dialogFolderId: f.id, swipeOpenDialogId: null })}
                onLongPress={f.id !== 'all' ? () => openFolderEdit(f.id as number) : undefined}
                style={[s.folderTab, active && s.folderTabActive]}
              >
                <Text style={[s.folderTabText, active && s.folderTabTextActive]}>{f.label}</Text>
              </Pressable>
            );
          })}
        </ScrollView>
        {activeFolderId !== 'all' && activeFolder ? (
          <View style={s.folderActions}>
            <Pressable style={s.folderActionBtn} onPress={() => openFolderEdit(activeFolder.id)}>
              <Text style={s.folderActionText}>Изменить</Text>
            </Pressable>
          </View>
        ) : null}
        <View style={s.dialogList}>
          {shown.map(({ d, i }, idx) => (
            <View key={d.id ?? i} style={s.dialogRowWrap}>
              <SwipeableChatRow
                rowId={d.id ?? i}
                open={d.id != null && nav.swipeOpenDialogId === d.id}
                onOpenChange={(open) => patch({ swipeOpenDialogId: open && d.id != null ? d.id : null })}
                onPress={() => openThread(i)}
                onFolderPress={() => {
                  if (d.id == null) return;
                  patch({ folderPickerConvId: d.id, stack: [...nav.stack, 'folder-picker'] });
                }}
                enabled={swipeEnabled && d.id != null}
              >
                <ChatRow
                  name={d.name}
                  platform={d.plat}
                  message={d.msg}
                  gradIndex={d.gradIndex}
                  vip={d.vip}
                  unread={d.unread}
                />
              </SwipeableChatRow>
            </View>
          ))}
          {!shown.length ? <Text style={s.charSub}>Нет диалогов</Text> : null}
        </View>
      </ScreenScroll>
    );
  }

  if (cur === 'folder-edit') {
    const folderId = nav.folderEditId;
    const toggleConv = (convId: number) => {
      const selected = new Set(nav.folderEditSelected);
      if (selected.has(convId)) selected.delete(convId);
      else selected.add(convId);
      patch({ folderEditSelected: [...selected] });
    };
    if (!folderId) {
      return (
        <ScreenScroll>
          <TopBar title="Папка" onBack={pop} />
          <Text style={s.charSub}>Папка не найдена</Text>
        </ScreenScroll>
      );
    }
    return (
      <ScreenScroll>
        <TopBar title="Редактировать папку" onBack={pop} />
        <FieldLabel>НАЗВАНИЕ ПАПКИ</FieldLabel>
        <TextField
          value={nav.folderEditName}
          onChangeText={(t) => patch({ folderEditName: t })}
          placeholder="Название"
        />
        <SectionLabel>ЧАТЫ В ПАПКЕ</SectionLabel>
        <Card style={s.gap8}>
          {conversations.map((d) => (
            <CheckRow
              key={d.id}
              label={d.name}
              checked={d.id != null && nav.folderEditSelected.includes(d.id)}
              onToggle={() => d.id && toggleConv(d.id)}
            />
          ))}
        </Card>
        <LimeButton
          title="Сохранить"
          onPress={() => {
            const name = nav.folderEditName.trim();
            if (!name) return;
            void Promise.all([
              renameConversationFolder(folderId, name),
              setFolderMembers(folderId, nav.folderEditSelected),
            ]).then(() => pop());
          }}
        />
        <GhostButton
          title="Удалить папку"
          onPress={() => {
            void deleteConversationFolder(folderId).then(() => {
              patch({ dialogFolderId: 'all', folderEditId: null });
              pop();
            });
          }}
        />
      </ScreenScroll>
    );
  }

  if (cur === 'newfolder') {
    const toggleConv = (convId: number) => {
      const selected = new Set(nav.newFolderSelected);
      if (selected.has(convId)) selected.delete(convId);
      else selected.add(convId);
      patch({ newFolderSelected: [...selected] });
    };
    return (
      <ScreenScroll>
        <TopBar title="Новая папка" onBack={pop} />
        <FieldLabel>НАЗВАНИЕ ПАПКИ</FieldLabel>
        <TextField
          value={nav.newFolderName}
          onChangeText={(t) => patch({ newFolderName: t })}
          placeholder="Например: Постоянные"
        />
        <SectionLabel>ДОБАВИТЬ ЧАТЫ В ПАПКУ</SectionLabel>
        <Card style={s.gap8}>
          {conversations.map((d) => (
            <CheckRow
              key={d.id}
              label={d.name}
              checked={d.id != null && nav.newFolderSelected.includes(d.id)}
              onToggle={() => d.id && toggleConv(d.id)}
            />
          ))}
        </Card>
        <LimeButton
          title="Создать папку"
          onPress={() => {
            const name = nav.newFolderName.trim();
            if (!name) return;
            void createConversationFolder(name, nav.newFolderSelected).then(() => {
              patch({ newFolderName: '', newFolderSelected: [] });
              pop();
            });
          }}
        />
      </ScreenScroll>
    );
  }

  if (cur === 'folder-picker') {
    return (
      <ScreenScroll>
        <TopBar title="Добавить в папку" onBack={pop} />
        <Card style={s.gap8}>
          {conversationFolders.map((f) => (
            <Pressable
              key={f.id}
              style={s.menuPickRow}
              onPress={() => {
                if (nav.folderPickerConvId) {
                  void addConversationToFolder(f.id, nav.folderPickerConvId).then(() => {
                    patch({ folderPickerConvId: null });
                    pop();
                  });
                }
              }}
            >
              <Text style={s.menuPickText}>{f.name}</Text>
            </Pressable>
          ))}
          {!conversationFolders.length ? <Text style={s.charSub}>Сначала создайте папку</Text> : null}
        </Card>
      </ScreenScroll>
    );
  }

  if (cur === 'thread') {
    const d = conversations[chatIdx] ?? conversations[0];
    if (!d) {
      return (
        <ScreenScroll>
          <TopBar title="Диалог" onBack={pop} />
          <Text style={s.charSub}>Диалог не найден</Text>
        </ScreenScroll>
      );
    }
    return (
      <ThreadView
        name={d.name}
        platform={d.plat}
        vip={d.vip}
        gradIndex={d.gradIndex}
        messages={messages}
        draft={nav.threadDraft}
        onDraftChange={(value) => patch({ threadDraft: value })}
        onBack={pop}
        lang={locale}
        onSend={() => {
          if (d.id && nav.threadDraft.trim()) {
            const text = nav.threadDraft;
            patch({ threadDraft: '' });
            void sendThreadMessage(d.id, text);
          }
        }}
      />
    );
  }

  if (cur === 'studio') {
    return (
      <ScreenScroll>
        <TopBar title="Студия" onBack={nav.stack.length > 1 ? pop : undefined} />
        <StudioRow icon={<IcoImage size={16} stroke="rgb(215,244,82)" />} tintRgb="215,244,82" title="Картинки" desc="6 режимов генерации" onPress={() => push('images')} />
        <StudioRow icon={<IcoFilm size={16} stroke="rgb(192,132,252)" />} tintRgb="192,132,252" title="Видео" desc="Оживить кадр" onPress={() => push('video')} />
        <StudioRow icon={<IcoBolt size={16} stroke="rgb(74,222,128)" />} tintRgb="74,222,128" title="Архив" desc="Все сгенерированные кадры" onPress={() => push('archive')} />
      </ScreenScroll>
    );
  }

  if (cur === 'images') {
    return (
      <ScreenScroll>
        <TopBar title="Картинки" onBack={pop} />
        {modeDefs.map((m) => {
          const modeCost = m.id === 'carousel'
            ? computeCarouselModeCardCost(health, me)
            : computeImageGenerationCost({
                modeId: m.id,
                contentMode: nav.contentMode,
                aiEngine: nav.aiEngine,
                health,
                me,
              });
          return (
            <StudioRow
              key={m.id}
              icon={modeIcon(m.icon, m.color)}
              tintRgb={m.color}
              title={m.title}
              desc={`${m.desc} · ${modeCost}`}
              onPress={() => push(`mode:${m.id}`)}
            />
          );
        })}
      </ScreenScroll>
    );
  }

  if (cur.startsWith('mode:')) {
    const modeId = cur.slice(5);
    const m = modeDefs.find((x) => x.id === modeId) ?? modeDefs[0];
    const slots = slotLabels[modeId] ?? [];
    const key = `img:${modeId}`;
    const st = nav.genStatus[key];
    const engines = enginesForMode(nav.contentMode);
    const engineLabel = engines.includes(nav.aiEngine) ? nav.aiEngine : engines[0];
    const imgCost = computeImageGenerationCost({
      modeId,
      contentMode: nav.contentMode,
      aiEngine: engineLabel,
      carouselCount: nav.carouselCount,
      health,
      me,
    });
    return (
      <ScreenScroll>
        <TopBar title={m.title} onBack={pop} />
        <Card style={s.gap10}>
          <SegmentedToggle
            left="SFW"
            right="NSFW"
            activeLeft={nav.contentMode === 'sfw'}
            onLeft={() => patch({ contentMode: 'sfw', aiEngine: 'Nano Banana Pro' })}
            onRight={() => patch({ contentMode: 'nsfw', aiEngine: 'Seedream 5 Pro' })}
          />
          <SectionLabel>AI-ДВИЖОК</SectionLabel>
          <ChipPicker
            items={engines}
            value={engineLabel}
            onChange={(e) => patch({ aiEngine: e })}
          />
          {slots.length ? (
            <>
              <SectionLabel>{slots.length > 1 ? 'РЕФЕРЕНСЫ' : 'РЕФЕРЕНС'}</SectionLabel>
              <View style={s.slotRow}>
                {slots.map((l, idx) => (
                  <DropSlot
                    key={l}
                    label={l}
                    onPress={async () => {
                      try {
                        const file = await pickImage();
                        if (file) setUploadFile(slotFileKey(modeId, l, idx), file);
                      } catch (e) {
                        /* ignore cancel */
                      }
                    }}
                  />
                ))}
              </View>
            </>
          ) : null}
          {modeId === 'prompt' ? (
            <TextAreaField
              value={nav.imgPrompt}
              onChangeText={(t) => patch({ imgPrompt: t })}
            />
          ) : null}
          {modeId === 'carousel' ? (
            <>
              <SectionLabel>КОЛИЧЕСТВО КАДРОВ</SectionLabel>
              <NumberChipPicker
                items={[...CAROUSEL_COUNTS]}
                value={nav.carouselCount}
                onChange={(n) => patch({ carouselCount: n })}
              />
            </>
          ) : null}
          <SectionLabel>ПЕРСОНАЖ</SectionLabel>
          <ChipPicker items={modelNames} value={nav.imgChar} onChange={(c) => patch({ imgChar: c })} />
          <SectionLabel>ФОРМАТ</SectionLabel>
          <ChipPicker
            items={[...IMG_FORMATS]}
            value={nav.imgFormat}
            onChange={(f) => patch({ imgFormat: f })}
          />
        </Card>
        <LimeButton title="Сгенерировать" cost={imgCost} onPress={() => runGen(key)} />
        {st === 'loading' ? <GenLoadingCard title="Генерируем…" sub={`${engineLabel} · ~10 c`} /> : null}
        {st === 'done' ? (
          <Card>
            <GenResultCard
              imageUrl={genResults[key]?.imageUrl}
              gradIndex={modeDefs.findIndex((x) => x.id === modeId)}
              badge={`Результат · ${nav.imgFormat}`}
              onRegen={() => runGen(key)}
            />
          </Card>
        ) : null}
      </ScreenScroll>
    );
  }

  if (cur === 'archive') {
    return (
      <ScreenScroll>
        <TopBar title="Архив" onBack={pop} />
        <Card style={s.warnCard}><Text style={s.warnText}>⏳ хранится ~4 дня</Text></Card>
        <View style={s.grid2}>
          {archiveTiles.map((t, i) => (
            <Pressable key={t.id ?? i} style={s.archTile} onPress={() => { patch({ archiveIdx: i }); push('archive-item'); }}>
              <RemoteImage uri={t.imageUrl} style={s.archImg} gradIndex={t.gradIndex} pending={t.pending} />
              <Text style={s.archWho}>{t.who}</Text>
            </Pressable>
          ))}
        </View>
      </ScreenScroll>
    );
  }

  if (cur === 'archive-item') {
    const t = archiveTiles[nav.archiveIdx] ?? archiveTiles[0];
    return (
      <ScreenScroll>
        <TopBar title="Кадр" onBack={pop} />
        <View style={s.lightboxWrap}>
          <RemoteImage uri={t.imageUrl} style={s.lightbox} gradIndex={t.gradIndex} pending={t.pending} />
          <Text style={s.lightboxBadge}>{t.who}</Text>
        </View>
        <View style={s.rowGap8}>
          <Pressable style={s.limeHalf}><Text style={s.limeHalfText}>Скачать</Text></Pressable>
          <Pressable style={s.purpleHalf}><Text style={s.purpleHalfText}>В видео</Text></Pressable>
        </View>
      </ScreenScroll>
    );
  }

  if (cur === 'video') {
    const st = nav.genStatus.video;
    const motionControl = (nav.vidMode || 'motion-control') === 'motion-control';
    const engines = enginesForMode(nav.contentMode);
    const engineLabel = engines.includes(nav.aiEngine) ? nav.aiEngine : engines[0];
    const vidCost = computeVideoGenerationCost({
      duration: nav.vidDuration,
      quality: nav.vidQuality,
      hasReferenceVideo: Boolean(motionVideoFileId),
      health,
      me,
    });
    const ffPreviewUrl = firstFrameUrl || '';
    const patchFf = (ffState: typeof nav.ffState) => patch({ ffState });

    return (
      <ScreenScroll>
        <TopBar title="Видео" onBack={pop} />
        <View style={s.rowGap8}>
          <Pressable
            style={[s.vidModeCard, motionControl && s.vidModeCardOn]}
            onPress={() => patch({ vidMode: 'motion-control' })}
          >
            <Text style={[s.vidModeTitle, motionControl && s.vidModeTitleOn]}>Motion control</Text>
            <Text style={s.vidModeDesc}>Повтор движения из референс-ролика</Text>
          </Pressable>
          <Pressable style={[s.vidModeCard, s.vidModeCardDisabled]} disabled>
            <View style={s.vidModeHead}>
              <Text style={s.vidModeTitle}>По промпту</Text>
              <Text style={s.vidModeBadge}>В разработке</Text>
            </View>
            <Text style={s.vidModeDesc}>Видео из текстового описания</Text>
          </Pressable>
        </View>

        {motionControl ? (
          <>
            <SectionLabel>ПЕРСОНАЖ</SectionLabel>
            <ChipPicker items={modelNames} value={nav.vidChar} onChange={(c) => patch({ vidChar: c })} />
            <SectionLabel>ТИП КОНТЕНТА</SectionLabel>
            <SegmentedToggle
              left="SFW"
              right="NSFW"
              activeLeft={nav.contentMode === 'sfw'}
              onLeft={() => patch({ contentMode: 'sfw', aiEngine: 'Nano Banana Pro' })}
              onRight={() => patch({ contentMode: 'nsfw', aiEngine: 'Seedream 5 Pro' })}
            />
            <SectionLabel>AI-ДВИЖОК</SectionLabel>
            <ChipPicker
              items={engines}
              value={engineLabel}
              onChange={(e) => patch({ aiEngine: e })}
            />
            <SectionLabel>РЕФЕРЕНСНОЕ ВИДЕО</SectionLabel>
            <DropSlotWide
              label={uploadFiles['motion-video']?.name || (motionVideoFileId ? 'Видео загружено' : 'Загрузить видео')}
              onPress={async () => {
                try {
                  const file = await pickVideo();
                  if (file) {
                    setUploadFile('motion-video', file);
                    const { uploadMotionDrivingVideo } = await import('@/src/api/actions');
                    const id = await uploadMotionDrivingVideo(file);
                    setMotionVideoFileId(id);
                  }
                } catch {
                  /* ignore */
                }
              }}
            />
            <SectionLabel>ПЕРВЫЙ КАДР ЕСТЬ?</SectionLabel>
            <View style={s.rowGap8}>
              <Pressable
                style={[s.limeHalf, !nav.vidHasFirstFrame && s.ghostHalf]}
                onPress={() => patch({ vidHasFirstFrame: true, ffState: 'idle' })}
              >
                <Text style={[s.limeHalfText, !nav.vidHasFirstFrame && s.ghostHalfText]}>Да</Text>
              </Pressable>
              <Pressable
                style={[s.ghostHalf, !nav.vidHasFirstFrame && s.limeHalf]}
                onPress={() => patch({ vidHasFirstFrame: false, ffState: 'idle' })}
              >
                <Text style={[s.ghostHalfText, !nav.vidHasFirstFrame && s.limeHalfText]}>Нет — сгенерировать</Text>
              </Pressable>
            </View>
            {!nav.vidHasFirstFrame ? (
              nav.ffState === 'idle' ? (
                <Pressable
                  style={s.ffGenBtn}
                  onPress={() => {
                    void generateFirstFrame(nav, patchFf).catch(() => {});
                  }}
                >
                  <Text style={s.ffGenBtnText}>✦ Сгенерировать первый кадр · −10 кр.</Text>
                </Pressable>
              ) : nav.ffState === 'loading' ? (
                <GenLoadingCard title="Генерируем первый кадр…" sub={`${engineLabel} · ~15 c`} />
              ) : (
                <Card style={s.gap10}>
                  <Pressable onPress={() => ffPreviewUrl && patch({ ffPreviewOpen: true })}>
                    {ffPreviewUrl ? (
                      <Image source={{ uri: ffPreviewUrl }} style={s.ffThumb} resizeMode="cover" />
                    ) : (
                      <LinearGradient colors={[...gradients[2]]} style={s.ffThumb} />
                    )}
                  </Pressable>
                  <Text style={s.ffDoneText}>✓ Первый кадр готов</Text>
                  <Pressable onPress={() => void generateFirstFrame(nav, patchFf).catch(() => {})}>
                    <Text style={s.regenText}>↻ Перегенерировать</Text>
                  </Pressable>
                </Card>
              )
            ) : null}
            <SectionLabel>КАЧЕСТВО</SectionLabel>
            <ChipPicker
              items={[...VID_QUALITIES]}
              value={nav.vidQuality}
              onChange={(q) => patch({ vidQuality: q })}
            />
            <SectionLabel>ФОРМАТ</SectionLabel>
            <ChipPicker
              items={[...IMG_FORMATS]}
              value={nav.vidFormat}
              onChange={(f) => patch({ vidFormat: f })}
            />
            <SectionLabel>ДЛИТЕЛЬНОСТЬ</SectionLabel>
            <NumberChipPicker
              items={[...VID_DURATIONS]}
              value={nav.vidDuration}
              onChange={(d) => patch({ vidDuration: d })}
              suffix="с"
            />
            <LimeButton title="Создать видео" cost={vidCost} icon={<IcoFilm size={16} stroke={color.limeText} />} onPress={() => runGen('video')} />
            {st === 'loading' ? <GenLoadingCard title="Рендерим видео…" sub="~20 c" /> : null}
            {st === 'done' ? (
              <Card style={s.gap10}>
                <LinearGradient colors={[...gradients[1]]} style={s.videoPreview}>
                  <View style={s.playCircle}><IcoFilm size={13} stroke="#fff" /></View>
                </LinearGradient>
                <View style={s.rowGap7}>
                  <View style={s.limeFlex}><Text style={s.limeHalfText}>Скачать MP4</Text></View>
                  <Pressable style={s.regenFlex} onPress={() => runGen('video')}><Text style={s.regenText}>↻ Ещё раз</Text></Pressable>
                </View>
              </Card>
            ) : null}
          </>
        ) : (
          <Card style={s.vidSoonCard}>
            <Text style={s.vidSoonText}>В разработке</Text>
          </Card>
        )}

        <Modal visible={nav.ffPreviewOpen && Boolean(ffPreviewUrl)} transparent animationType="fade" onRequestClose={() => patch({ ffPreviewOpen: false })}>
          <Pressable style={s.ffModalBackdrop} onPress={() => patch({ ffPreviewOpen: false })}>
            <View style={s.ffModalBody}>
              <View style={s.ffModalHead}>
                <Text style={s.ffModalTitle}>{nav.vidChar} · {nav.vidFormat}</Text>
                <Pressable onPress={() => patch({ ffPreviewOpen: false })}>
                  <Text style={s.ffModalClose}>✕</Text>
                </Pressable>
              </View>
              {ffPreviewUrl ? (
                <Image source={{ uri: ffPreviewUrl }} style={s.ffModalImg} resizeMode="contain" />
              ) : null}
            </View>
          </Pressable>
        </Modal>
      </ScreenScroll>
    );
  }

  if (cur === 'characters') {
    return (
      <ScreenScroll>
        <TopBar title="Персонажи" onBack={nav.stack.length > 1 ? pop : undefined} />
        {models.map((c) => (
          <Card key={c.id} onPress={() => { patch({ charId: c.id, charTab: 'photos' }); push(`character:${c.id}`); }}>
            <View style={s.rowCenter}>
              <Avatar
                letter={c.name[0]}
                index={c.gradIndex}
                size={36}
                imageUrl={c.raw?.images?.[0]?.url ? resolveMediaUrl(c.raw.images[0].url) : undefined}
              />
              <View style={s.flex1}>
                <Text style={s.charName}>{c.name}</Text>
                <Text style={s.charSub}>{c.sub}</Text>
              </View>
              <IcoChevron size={14} stroke={color.dim} />
            </View>
          </Card>
        ))}
        <DashedAddButton title="+ Новый персонаж" onPress={() => push('new-character')} />
      </ScreenScroll>
    );
  }

  if (cur === 'new-character') {
    return (
      <ScreenScroll>
        <TopBar title="Новый персонаж" onBack={pop} />
        <Card style={s.gap9}>
          <FieldLabel>ИМЯ ПЕРСОНАЖА</FieldLabel>
          <TextField value={nav.newCharName} onChangeText={(t) => patch({ newCharName: t })} />
        </Card>
        <SectionLabel>ПЕРВОЕ ФОТО</SectionLabel>
        <DropSlot
          label="Загрузить фото"
          onPress={async () => {
            try {
              const file = await pickImage();
              if (file) setUploadFile('newCharPhoto', file);
            } catch { /* ignore */ }
          }}
        />
        <SectionLabel>ТЕГ ФОТО</SectionLabel>
        <ChipRowInteractive
          items={app.photoTags}
          activeIndex={nav.photoTagIdx}
          onSelect={(i) => patch({ photoTagIdx: i })}
        />
        <LimeButton
          title="Создать персонажа"
          onPress={async () => {
            try {
              const id = await createCharacter(nav.newCharName, nav.photoTagIdx, app.uploadFiles.newCharPhoto);
              patch({ charId: String(id), charTab: 'photos' });
              push(`character:${id}`);
            } catch { /* error in app */ }
          }}
        />
      </ScreenScroll>
    );
  }

  if (cur.startsWith('character:')) {
    const id = cur.slice(10);
    const model = models.find((m) => m.id === id);
    const raw = model?.raw;
    const name = model?.name ?? nav.newCharName;
    const ct = nav.charTab;
    const charIdNum = Number(id);
    const charArchive = archiveTiles.filter((t) => t.raw?.studio_model_id === charIdNum);
    const charPhotos = mapCharPhotoTags(raw?.images ?? []);
    return (
      <ScreenScroll>
        <View style={s.charHead}>
          <Pressable onPress={pop} hitSlop={8}><IcoBack size={18} stroke={color.muted} /></Pressable>
          <Avatar
            letter={name[0]}
            index={model?.gradIndex ?? 0}
            size={36}
            imageUrl={charPhotos[0]?.url || undefined}
          />
          <View>
            <Text style={s.charTitle}>{name}</Text>
            <Text style={s.charSub}>Telegram · Fanvue</Text>
          </View>
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.tabRow}>
          <TabChip label="Фото" active={ct === 'photos'} onPress={() => patch({ charTab: 'photos' })} />
          <TabChip label="Персона" active={ct === 'persona'} onPress={() => patch({ charTab: 'persona' })} />
          <TabChip label="EXIF" active={ct === 'exif'} onPress={() => patch({ charTab: 'exif' })} />
          <TabChip label="История" active={ct === 'history'} onPress={() => patch({ charTab: 'history' })} />
        </ScrollView>
        {ct === 'persona' ? (
          <Card style={s.gap9}>
            <FieldLabel>ВОЗРАСТ / ГОРОД</FieldLabel>
            <TextField
              value={nav.charFields.ageCity}
              onChangeText={(t) => patch({ charFields: { ...nav.charFields, ageCity: t } })}
            />
            <FieldLabel>ХАРАКТЕР</FieldLabel>
            <TextField
              value={nav.charFields.character}
              onChangeText={(t) => patch({ charFields: { ...nav.charFields, character: t } })}
            />
            <FieldLabel>СТИЛЬ ПЕРЕПИСКИ</FieldLabel>
            <TextField
              value={nav.charFields.chatStyle}
              onChangeText={(t) => patch({ charFields: { ...nav.charFields, chatStyle: t } })}
            />
          </Card>
        ) : null}
        {ct === 'exif' ? (
          <Card style={s.gap9}>
            <FieldLabel>ПРЕСЕТ КАМЕРЫ</FieldLabel>
            <TextField
              value={nav.charFields.camera}
              onChangeText={(t) => patch({ charFields: { ...nav.charFields, camera: t } })}
            />
            <FieldLabel>ГЕО (ШИРОТА/ДОЛГОТА)</FieldLabel>
            <TextField
              value={nav.charFields.geo}
              onChangeText={(t) => patch({ charFields: { ...nav.charFields, geo: t } })}
            />
          </Card>
        ) : null}
        {ct === 'history' ? (
          <Card style={s.gap9}>
            {charArchive.length ? charArchive.map((h) => (
              <View key={h.id} style={s.historyRow}>
                <Text style={s.historyLabel}>{h.who}</Text>
                <Text style={s.historyCost}>{h.raw?.prompt_excerpt || 'gen'}</Text>
              </View>
            )) : <Text style={s.charSub}>Пока нет генераций</Text>}
          </Card>
        ) : null}
        {ct === 'photos' || !ct ? (
          <>
            <SectionLabel>ФОТО-РЕФЕРЕНСЫ</SectionLabel>
            <View style={s.grid3}>
              {charPhotos.map((p) => (
                p.url ? (
                  <View key={p.id} style={s.photoTileWrap}>
                    <RemoteImage uri={p.url} style={StyleSheet.absoluteFill} gradIndex={p.gradIndex} />
                    <View style={s.photoTileOverlay}>
                      <Text style={s.photoTag}>{p.label}</Text>
                    </View>
                  </View>
                ) : (
                  <LinearGradient key={p.id} colors={[...gradients[p.gradIndex % gradients.length]]} style={s.photoTile}>
                    <Text style={s.photoTag}>{p.label}</Text>
                  </LinearGradient>
                )
              ))}
              <Pressable
                style={s.photoAdd}
                onPress={async () => {
                  try {
                    const file = await pickImage();
                    if (file) setUploadFile('charPhoto', file);
                    patch({ photoTagPick: true });
                  } catch {
                    patch({ photoTagPick: true });
                  }
                }}
              >
                <Text style={s.photoAddText}>+</Text>
              </Pressable>
            </View>
            {nav.photoTagPick ? (
              <Card style={[s.gap8, s.limeBorder]}>
                <Text style={s.pickTitle}>Загрузить фото и выбрать тег</Text>
                <ChipRowInteractive
                  items={app.photoTagsExtended}
                  activeIndex={nav.photoTagIdx}
                  onSelect={(i) => patch({ photoTagIdx: i })}
                />
                <Pressable
                  style={s.savePhoto}
                  onPress={async () => {
                    if (!charIdNum || !app.uploadFiles.charPhoto) {
                      patch({ photoTagPick: false });
                      return;
                    }
                    const kinds = ['face', 'turnaround', 'body', 'genitals', 'other'];
                    const { uploadStudioModelImage } = await import('@/src/api/actions');
                    await uploadStudioModelImage(charIdNum, app.uploadFiles.charPhoto, kinds[nav.photoTagIdx] || 'face');
                    patch({ photoTagPick: false });
                    await app.refreshAll();
                  }}
                >
                  <Text style={s.savePhotoText}>Сохранить фото</Text>
                </Pressable>
              </Card>
            ) : null}
            <SectionLabel>ОПИСАНИЕ ВНЕШНОСТИ</SectionLabel>
            <Card style={s.gap10}>
              <TextAreaField
                value={nav.charFields.appearance}
                onChangeText={(t) => patch({ charFields: { ...nav.charFields, appearance: t } })}
              />
              {nav.descGen === 'loading' ? (
                <View style={s.descLoading}><ActivityIndicator color={color.purple} size="small" /><Text style={s.descLoadingText}>Анализируем фото…</Text></View>
              ) : (
                <Pressable
                  onPress={async () => {
                    if (!charIdNum) return;
                    patch({ descGen: 'loading' });
                    try {
                      const text = await generateCharacterProfile(charIdNum);
                      patch({
                        descGen: 'done',
                        charFields: { ...nav.charFields, appearance: text || nav.charFields.appearance },
                      });
                    } catch {
                      patch({ descGen: 'idle' });
                    }
                  }}
                >
                  <Text style={s.genFromPhoto}>{nav.descGen === 'done' ? '✓ Описание обновлено из фото' : '✦ Сгенерировать из фото'}</Text>
                </Pressable>
              )}
              <Pressable
                style={s.savePhoto}
                onPress={() => {
                  if (charIdNum) void saveCharacterFields(charIdNum, nav.charFields);
                }}
              >
                <Text style={s.savePhotoText}>Сохранить</Text>
              </Pressable>
            </Card>
          </>
        ) : null}
      </ScreenScroll>
    );
  }

  if (cur === 'connections') {
    return (
      <ScreenScroll>
        <TopBar title="Подключения" onBack={pop} />
        {connectionsList.map((c) => (
          <Card key={c.id} onPress={() => push(`connection:${c.id}`)}>
            <View style={s.rowCenter}>
              <View style={[s.connIcon, { backgroundColor: `rgba(${c.color},0.12)` }]}>{connIcon(c.icon, c.color)}</View>
              <View style={s.flex1}>
                <Text style={s.connName}>{c.name}</Text>
                <Pill text={c.status} bg={`rgba(${c.color},0.12)`} fg={`rgb(${c.color})`} />
              </View>
            </View>
          </Card>
        ))}
      </ScreenScroll>
    );
  }

  if (cur.startsWith('connection:')) {
    const id = cur.slice(11);
    const c = connectionsList.find((x) => x.id === id) ?? connectionsList[0];
    const existing = mapIntegrationConnections(id, rawIntegrations, rawModels);
    const defaultChar = existing[0]?.studioModelId
      ? rawModels.find((m) => m.id === existing[0].studioModelId)?.name || modelNames[0]
      : modelNames[0];
    return (
      <ScreenScroll>
        <TopBar title={c.name} onBack={pop} />
        {existing.length ? (
          <>
            <SectionLabel>АКТИВНЫЕ ПОДКЛЮЧЕНИЯ</SectionLabel>
            <Card style={s.gap8}>
              {existing.map((row) => (
                <View key={row.id} style={s.connExistingRow}>
                  <View style={s.flex1}>
                    <Text style={s.opLabel}>{row.name}</Text>
                    <Text style={s.charSub}>{row.meta}</Text>
                  </View>
                  <Pressable
                    style={s.redOutlineSmall}
                    onPress={() => void disconnectConnection(id, row.id).then(pop)}
                  >
                    <Text style={s.redText}>Удалить</Text>
                  </Pressable>
                </View>
              ))}
            </Card>
          </>
        ) : (
          <Card><Text style={s.charSub}>Нет активных подключений</Text></Card>
        )}
        <SectionLabel>ДОБАВИТЬ / ОБНОВИТЬ</SectionLabel>
        <Card style={s.gap10}>
          <FieldLabel>API-КЛЮЧ / ТОКЕН</FieldLabel>
          <TextField
            value={nav.connToken}
            onChangeText={(t) => patch({ connToken: t })}
            secureTextEntry
          />
          <FieldLabel>ПЕРСОНАЖ</FieldLabel>
          <ChipPicker
            items={modelNames}
            value={nav.connChar || defaultChar}
            onChange={(v) => patch({ connChar: v })}
          />
        </Card>
        <View style={s.rowGap8}>
          <Pressable
            style={s.limeFlex}
            onPress={() => void saveConnection(id, nav.connToken, nav.connChar || defaultChar).then(() => patch({ connToken: '' }))}
          >
            <Text style={s.limeHalfText}>Сохранить</Text>
          </Pressable>
        </View>
      </ScreenScroll>
    );
  }

  if (cur === 'profile') {
    return (
      <ScreenScroll>
        <TopBar title={t.profileTitle} />
        <Card>
          <View style={s.rowCenter}>
            <Avatar letter={userName[0] || 'U'} index={2} size={48} />
            <View>
              <Text style={s.profileEmail}>{userEmail}</Text>
              <Text style={s.charSub}>{me?.is_workspace_owner ? t.owner : t.member} · {me?.plan_display_name || me?.billing_plan || '—'}</Text>
            </View>
          </View>
        </Card>
        <SectionLabel>{t.sectionWorkspace}</SectionLabel>
        <Card>
          <MenuRow icon={<IcoCard size={17} stroke={color.muted} />} label={t.navBilling} onPress={() => push('billing')} />
          <MenuRow icon={<IcoHeart size={17} stroke={color.muted} />} label={t.navDonations} onPress={() => push('donations')} />
          <MenuRow icon={<IcoPlug size={17} stroke={color.muted} />} label={t.navConnections} onPress={() => push('connections')} />
          <MenuRow icon={<IcoUsers size={17} stroke={color.muted} />} label={t.navTeam} onPress={() => push('team')} />
          <MenuRow icon={<IcoStar size={17} stroke={color.muted} />} label={t.navCharacters} onPress={() => push('characters')} />
        </Card>
        <SectionLabel>{t.sectionSystem}</SectionLabel>
        <Card>
          <MenuRow icon={<IcoShield size={17} stroke={color.orange} />} label={t.adminPanel} badge="ADMIN" onPress={() => resetTo('admin')} />
          <MenuRow icon={<IcoCog size={17} stroke={color.muted} />} label={t.settingsTitle} onPress={() => push('settings')} />
        </Card>
      </ScreenScroll>
    );
  }

  if (cur === 'billing') {
    const plans = nav.billTier === 'pro' ? billingPlans.pro : billingPlans.standard;
    return (
      <ScreenScroll>
        <TopBar title="Тариф и баланс" onBack={pop} />
        <Card style={s.gap6}>
          <View style={s.between}><Text style={s.planTitle}>{me?.plan_display_name || me?.billing_plan || '—'}</Text><Pill text={(me?.subscription_status || 'active').toUpperCase()} bg="rgba(74,222,128,0.12)" fg={color.green} /></View>
          <Text style={s.charSub}>{me?.credits_balance ?? 0} кредитов{me?.subscription_expires_at ? ` · до ${fmtDateShort(me.subscription_expires_at)}` : ''}</Text>
        </Card>
        <SectionLabel>СМЕНИТЬ ПЛАН</SectionLabel>
        <SegmentedToggle left="Standard" right="Pro" activeLeft={nav.billTier === 'standard'} onLeft={() => patch({ billTier: 'standard' })} onRight={() => patch({ billTier: 'pro' })} />
        {plans.map((p, i) => (
          <Card key={p[0]}>
            <View style={s.between}>
              <View><Text style={s.planName}>{p[0]}</Text><Text style={s.charSub}>{p[1]} ₽/мес</Text></View>
              <Pressable
                style={[s.payBtn, i === 1 && s.payBtnActive]}
                onPress={async () => {
                  const url = await openBillingCheckout(p[0].toLowerCase().replace(/\s+/g, '_'));
                  if (url) void Linking.openURL(url);
                }}
              >
                <Text style={[s.payBtnText, i === 1 && s.payBtnTextActive]}>Оплатить</Text>
              </Pressable>
            </View>
          </Card>
        ))}
        <SectionLabel>ПАКЕТЫ КРЕДИТОВ</SectionLabel>
        <View style={s.grid2}>
          {creditPacks.map(([amt, price]) => (
            <Card key={amt}>
              <Text style={s.creditAmt}>{amt}</Text>
              <Text style={s.charSub}>{price}</Text>
            </Card>
          ))}
        </View>
        <SectionLabel>ИСТОРИЯ ОПЕРАЦИЙ</SectionLabel>
        <Card style={s.gap8}>
          {creditHistory.length ? creditHistory.map((row) => (
            <View key={row.label} style={s.between}>
              <Text style={s.opLabel}>{row.label}</Text>
              <Text style={row.positive ? s.greenText : s.redText}>{row.amount}</Text>
            </View>
          )) : <Text style={s.charSub}>История пуста</Text>}
        </Card>
      </ScreenScroll>
    );
  }

  if (cur === 'donations') {
    return (
      <ScreenScroll>
        <TopBar title="Донаты и выплаты" onBack={pop} />
        <View style={s.kpiRow}>
          <Kpi label="ВСЕГО" value={fmtMoney(donationBalances.total, donationBalances.currency)} />
          <Kpi label="ДОСТУПНО" value={fmtMoney(donationBalances.available, donationBalances.currency)} accent={color.green} />
        </View>
        <SectionLabel>ВЫВОД СРЕДСТВ</SectionLabel>
        <Card style={s.gap9}>
          <FieldLabel>АДРЕС USDT (TRC20)</FieldLabel>
          <TextField
            value={nav.donationFields.usdt || payoutWallet}
            onChangeText={(t) => patch({ donationFields: { ...nav.donationFields, usdt: t } })}
            onBlur={() => {
              const wallet = (nav.donationFields.usdt || payoutWallet).trim();
              if (wallet) void savePayoutWallet(wallet);
            }}
          />
          <Pressable style={s.pinkBtn} onPress={() => void requestPayout()}>
            <Text style={s.pinkBtnTitle}>Заявка на выплату</Text>
            <Text style={s.pinkBtnCost}>{fmtMoney(Math.max(0, donationBalances.available - 20000), donationBalances.currency)}</Text>
          </Pressable>
        </Card>
        <SectionLabel>ССЫЛКИ НА ДОНАТ</SectionLabel>
        <Card style={s.gap8}>
          {donations.map((d) => (
            <View key={d.id} style={s.donationRow}>
              <View style={s.flex1}>
                <View style={s.between}>
                  <Text style={s.opLabel}>{d.title}</Text>
                  <Pill text={d.status} bg={d.status === 'ACTIVE' ? 'rgba(74,222,128,0.12)' : 'rgba(251,146,60,0.12)'} fg={d.status === 'ACTIVE' ? color.green : color.orange} />
                </View>
                {d.minAmount ? <Text style={s.charSub}>Мин. {d.minAmount}</Text> : null}
                {d.webLink ? (
                  <Pressable onPress={() => void Linking.openURL(d.webLink)}>
                    <Text style={s.linkText} numberOfLines={1}>{d.webLink}</Text>
                  </Pressable>
                ) : null}
                {d.telegramLink ? (
                  <Pressable onPress={() => void Linking.openURL(d.telegramLink)}>
                    <Text style={s.linkText} numberOfLines={1}>{d.telegramLink}</Text>
                  </Pressable>
                ) : null}
              </View>
            </View>
          ))}
          {!donations.length ? <Text style={s.charSub}>Нет донатов</Text> : null}
        </Card>
        <SectionLabel>ПОСЛЕДНИЕ ПОСТУПЛЕНИЯ</SectionLabel>
        <Card style={s.gap8}>
          {donationEvents.length ? donationEvents.slice(0, 10).map((ev) => (
            <View key={ev.id} style={s.between}>
              <View style={s.flex1}>
                <Text style={s.opLabel}>{ev.label}</Text>
                <Text style={s.charSub}>{ev.time}</Text>
              </View>
              <Text style={s.greenText}>{ev.amount}</Text>
            </View>
          )) : <Text style={s.charSub}>Пока нет поступлений</Text>}
        </Card>
        <DashedAddButton title="+ Новый донат" onPress={() => push('new-donation')} />
      </ScreenScroll>
    );
  }

  if (cur === 'new-donation') {
    return (
      <ScreenScroll>
        <TopBar title="Новый донат" onBack={pop} />
        <Card style={s.gap9}>
          <FieldLabel>ЗАГОЛОВОК</FieldLabel>
          <TextField
            value={nav.donationFields.title}
            onChangeText={(t) => patch({ donationFields: { ...nav.donationFields, title: t } })}
          />
          <FieldLabel>ОПИСАНИЕ</FieldLabel>
          <TextField
            value={nav.donationFields.desc}
            onChangeText={(t) => patch({ donationFields: { ...nav.donationFields, desc: t } })}
          />
          <FieldLabel>МИН. СУММА</FieldLabel>
          <TextField
            value={nav.donationFields.min}
            onChangeText={(t) => patch({ donationFields: { ...nav.donationFields, min: t } })}
          />
          <FieldLabel>ПЕРСОНАЖ</FieldLabel>
          <ChipRowInteractive
            items={modelNames}
            activeIndex={nav.donationCharIdx}
            onSelect={(i) => patch({ donationCharIdx: i })}
          />
        </Card>
        <View style={s.rowGap8}>
          <GhostButton title="Черновик" onPress={pop} />
          <Pressable
            style={s.limeFlex}
            onPress={async () => {
              await saveDonationDraft(nav.donationFields, modelNames[nav.donationCharIdx] || modelNames[0]);
              pop();
            }}
          >
            <Text style={s.limeHalfText}>На модерацию</Text>
          </Pressable>
        </View>
      </ScreenScroll>
    );
  }

  if (cur === 'team') {
    return (
      <ScreenScroll>
        <TopBar title="Команда" onBack={pop} />
        <View style={s.kpiRow}>
          <Kpi label="ОТВЕТЫ / МЕС" value={chatterStats?.replies ?? '—'} />
          <Kpi label="SLA" value={chatterStats?.sla ?? '—'} accent={color.green} />
        </View>
        <SectionLabel>УЧАСТНИКИ</SectionLabel>
        {members.map((m) => (
          <Card
            key={m.id}
            onPress={() => {
              patch({
                opEditId: m.id,
                opLogin: m.name,
                opPassword: '',
                opRights: m.rights,
              });
              push('newoperator');
            }}
          >
            <View style={s.rowCenter}>
              <Avatar letter={m.letter} index={m.gradIndex} size={32} />
              <View style={s.flex1}><Text style={s.opLabel}>{m.name}</Text><Text style={s.charSub}>{m.sub}</Text></View>
              <IcoChevron size={14} stroke={color.dim} />
            </View>
          </Card>
        ))}
        <DashedAddButton
          title="+ Добавить оператора"
          onPress={() => {
            patch({
              opEditId: null,
              opLogin: '',
              opPassword: '',
              opRights: { chat: true, studio: true, models: false, keys: false, billing: false },
            });
            push('newoperator');
          }}
        />
      </ScreenScroll>
    );
  }

  if (cur === 'newoperator') {
    const editing = nav.opEditId != null;
    return (
      <ScreenScroll>
        <TopBar title={editing ? 'Редактировать оператора' : 'Новый оператор'} onBack={pop} />
        <Card style={s.gap9}>
          <FieldLabel>ЛОГИН</FieldLabel>
          <TextField value={nav.opLogin} onChangeText={(t) => patch({ opLogin: t })} autoCapitalize="none" />
          <FieldLabel>{editing ? 'НОВЫЙ ПАРОЛЬ (необязательно)' : 'ПАРОЛЬ'}</FieldLabel>
          <TextField value={nav.opPassword} onChangeText={(t) => patch({ opPassword: t })} secureTextEntry />
        </Card>
        <SectionLabel>ПРАВА ДОСТУПА</SectionLabel>
        <Card style={s.gap8}>
          {rightsDefs.map((r) => (
            <CheckRow key={r.k} label={r.l} checked={!!nav.opRights[r.k]} onToggle={() => patch({ opRights: { ...nav.opRights, [r.k]: !nav.opRights[r.k] } })} />
          ))}
        </Card>
        <LimeButton
          title={editing ? 'Сохранить изменения' : 'Создать участника'}
          onPress={() => {
            const action = editing && nav.opEditId
              ? updateOperator(nav.opEditId, nav.opLogin, nav.opPassword, nav.opRights)
              : addOperator(nav.opLogin, nav.opPassword, nav.opRights);
            void action.then(() => {
              patch({ opEditId: null, opLogin: '', opPassword: '' });
              pop();
            });
          }}
        />
        {editing && nav.opEditId ? (
          <Pressable
            style={[s.redOutline, { marginTop: 12 }]}
            onPress={() => void deleteOperator(nav.opEditId!).then(() => {
              patch({ opEditId: null, opLogin: '', opPassword: '' });
              pop();
            })}
          >
            <Text style={s.redText}>Удалить участника</Text>
          </Pressable>
        ) : null}
      </ScreenScroll>
    );
  }

  if (cur === 'settings') {
    return (
      <SettingsMainScreen
        onBack={pop}
        onOpenLanguage={() => push('settings-language')}
        onOpenBiometric={() => push('settings-biometric')}
        onOpenPush={() => push('settings-push')}
      />
    );
  }

  if (cur === 'settings-language') {
    return <SettingsLanguageScreen onBack={pop} />;
  }

  if (cur === 'settings-biometric') {
    return <SettingsBiometricScreen onBack={pop} />;
  }

  if (cur === 'settings-push') {
    return <SettingsPushScreen onBack={pop} />;
  }

  if (cur === 'admin') {
    return (
      <ScreenScroll>
        <View style={s.adminHead}>
          <Pressable onPress={() => resetTo('profile')} hitSlop={8}><IcoBack size={17} stroke={color.muted} /></Pressable>
          <Text style={s.adminTitle}>Admin · Обзор</Text>
          <Pill text="LIVE" bg="rgba(74,222,128,0.12)" fg={color.green} />
        </View>
        <View style={s.kpiRow}>
          <Kpi label="ПОЛЬЗОВАТЕЛЕЙ" value={adminStats?.total_users != null ? adminStats.total_users.toLocaleString('ru-RU') : '—'} />
          <Kpi label="ОПЛАТ ВСЕГО" value={adminStats?.payments_total != null ? adminStats.payments_total.toLocaleString('ru-RU') : '—'} />
          <Kpi label="ВЫРУЧКА / МЕС" value={adminStats?.revenue_month_rub != null ? fmtRub(adminStats.revenue_month_rub) : '—'} accent={color.lime} />
          <Kpi label="АКТИВНЫХ ПОДПИСОК" value={adminStats?.engagement?.paid_active_owners != null ? String(adminStats.engagement.paid_active_owners) : '—'} accent={color.green} />
        </View>
        <SectionLabel>ТАРИФЫ ПО ПОПУЛЯРНОСТИ</SectionLabel>
        <Card style={s.gap10}>
          {(adminStats?.top_plans?.length ? adminStats.top_plans : [
            { label: 'Studio', pct: 46 },
            { label: 'Solo', pct: 26 },
            { label: 'Pro Pro', pct: 15 },
          ]).map((p, i) => {
            const barColors = [color.lime, color.blue, color.purple, color.green, color.orange];
            return (
              <ProgressBar key={p.label} label={p.label} pct={p.pct} barColor={barColors[i % barColors.length]} />
            );
          })}
        </Card>
        <SectionLabel>РАЗДЕЛЫ</SectionLabel>
        <Card>
          <MenuRow icon={<IcoUsers size={17} stroke={color.muted} />} label="Пользователи" onPress={() => push('admin-users')} />
          <MenuRow icon={<IcoChat size={17} stroke={color.muted} />} label="Рассылки" onPress={() => push('admin-broadcasts')} />
          <MenuRow icon={<IcoImage size={17} stroke={color.muted} />} label="EXIF-бот" onPress={() => push('admin-exif')} />
          <MenuRow icon={<IcoFilm size={17} stroke={color.muted} />} label="IG-бот" onPress={() => push('admin-ig')} />
          <MenuRow icon={<IcoHeart size={17} stroke={color.muted} />} label="Донаты креаторов" onPress={() => push('admin-donations')} />
        </Card>
      </ScreenScroll>
    );
  }

  if (cur === 'admin-users') {
    return (
      <ScreenScroll>
        <TopBar title="Пользователи" onBack={pop} />
        <Card>
          <TextField
            value={nav.adminSearch}
            onChangeText={(t) => {
              patch({ adminSearch: t });
              void searchAdminUsers(t);
            }}
            placeholder="Поиск по email…"
          />
        </Card>
        {adminUsers
          .filter((u) => !nav.adminSearch || u.email.toLowerCase().includes(nav.adminSearch.toLowerCase()))
          .map((u) => (
          <Card key={u.email} onPress={() => { patch({ adminUserIdx: adminUsers.indexOf(u) }); push(`admin-user:${u.id}`); }}>
            <Text style={s.opLabel}>{u.email}</Text>
            <Text style={s.charSub}>{u.role} · {u.plan} · {u.credits} кр. · подписка: {u.sub}</Text>
          </Card>
        ))}
      </ScreenScroll>
    );
  }

  if (cur.startsWith('admin-user:')) {
    const userId = Number(cur.slice(11));
    const u = adminUsers.find((x) => x.id === userId) ?? adminUsers[nav.adminUserIdx];
    if (!u) {
      return (
        <ScreenScroll>
          <TopBar title="Пользователь" onBack={pop} />
          <Text style={s.charSub}>Пользователь не найден</Text>
        </ScreenScroll>
      );
    }
    return (
      <ScreenScroll>
        <TopBar title={u.email.split('@')[0]} onBack={pop} />
        <Card style={s.gap8}>
          <View style={s.between}><Text style={s.opLabel}>Роль</Text><Text style={s.bold}>{u.role}</Text></View>
          <View style={s.between}><Text style={s.opLabel}>Тариф</Text><Text style={s.bold}>{u.plan}</Text></View>
          <View style={s.between}><Text style={s.opLabel}>Кредиты</Text><Text style={[s.bold, { color: color.lime }]}>{u.credits}</Text></View>
        </Card>
        <SectionLabel>ПОДПИСКА</SectionLabel>
        <Card style={s.gap9}>
          <Pressable style={s.between} onPress={() => patch({ adminSubActive: !nav.adminSubActive })}>
            <Text style={s.opLabel}>Статус</Text>
            <View style={s.rowCenter}>
              <View style={[s.dot, { backgroundColor: nav.adminSubActive ? color.green : color.dim }]} />
              <Text style={[s.bold, { color: nav.adminSubActive ? color.green : color.muted }]}>{nav.adminSubActive ? 'Активна' : 'Не активна'}</Text>
            </View>
          </Pressable>
          <FieldLabel>ПЛАН</FieldLabel>
          <ChipRowInteractive items={adminPlanChips} activeIndex={nav.adminPlanIdx} onSelect={(i) => patch({ adminPlanIdx: i })} />
          <FieldLabel>ДЕЙСТВУЕТ ДО</FieldLabel>
          <TextField
            value={nav.adminSubUntil}
            onChangeText={(t) => patch({ adminSubUntil: t })}
          />
        </Card>
        <Pressable
          style={s.savePhoto}
          onPress={() => void saveAdminSubscription(u.id, {
            plan: adminPlanChips[nav.adminPlanIdx],
            active: nav.adminSubActive,
            expires_at: nav.adminSubUntil,
          })}
        >
          <Text style={s.savePhotoText}>Сохранить подписку</Text>
        </Pressable>
        <SectionLabel>ДОСТУП И КРЕДИТЫ</SectionLabel>
        <Card style={s.rowGap8}>
          <View style={s.flex1}>
            <TextField
              value={nav.adminCreditsDelta}
              onChangeText={(t) => patch({ adminCreditsDelta: t })}
            />
          </View>
          <Pressable style={s.okBtn} onPress={() => void adjustAdminCredits(u.id, nav.adminCreditsDelta)}>
            <Text style={s.okText}>OK</Text>
          </Pressable>
        </Card>
      </ScreenScroll>
    );
  }

  if (cur === 'admin-broadcasts') {
    return (
      <ScreenScroll>
        <TopBar title="Рассылки" onBack={pop} />
        <SectionLabel>СЕГМЕНТ</SectionLabel>
        <Card style={s.gap8}>
          <View style={s.between}><Text style={[s.opLabel, { color: color.lime }]}>Без активности (зомби)</Text><Text style={s.opLabel}>114</Text></View>
          <View style={s.between}><Text style={s.charSub}>Регистрации за 30 дней</Text><Text style={s.charSub}>46</Text></View>
          <View style={s.between}><Text style={s.charSub}>Оплаченная подписка</Text><Text style={s.charSub}>5</Text></View>
        </Card>
        <Card>
          <FieldLabel>ТЕМА ПИСЬМА</FieldLabel>
          <TextField
            value={nav.broadcastSubject}
            onChangeText={(t) => patch({ broadcastSubject: t })}
          />
        </Card>
        <Pressable style={s.savePhoto} onPress={() => void sendBroadcast(nav.broadcastSubject)}>
          <Text style={s.savePhotoText}>Отправить кампанию</Text>
        </Pressable>
      </ScreenScroll>
    );
  }

  if (cur === 'admin-exif' || cur === 'admin-ig') {
    const isExif = cur === 'admin-exif';
    const stats = isExif ? exifBotStats : igBotStats;
    const users = isExif ? exifBotUsers : igBotUsers;
    return (
      <ScreenScroll>
        <TopBar title={isExif ? 'EXIF-бот' : 'IG-бот'} onBack={pop} />
        <View style={s.kpiRow}>
          <Kpi label="ПОЛЬЗОВАТЕЛЕЙ" value={stats?.users ?? '0'} />
          <Kpi label="СЕГОДНЯ" value={stats?.today ?? '0'} />
          <Kpi label="ОБРАБОТОК" value={stats?.processed ?? '0'} />
        </View>
        <SectionLabel>ПОЛЬЗОВАТЕЛИ БОТА</SectionLabel>
        <Card style={s.gap8}>
          {users.map((b) => (
            <View key={b.u} style={s.between}>
              <Text style={s.opLabel}><Text style={s.bold}>{b.name}</Text> @{b.u}</Text>
              <Text style={s.charSub}>{b.m}</Text>
            </View>
          ))}
          {!users.length ? <Text style={s.charSub}>Нет пользователей</Text> : null}
        </Card>
      </ScreenScroll>
    );
  }

  if (cur === 'admin-donations') {
    const dt = nav.adminDonTab;
    const tabs: [typeof dt, string][] = [['moderation', 'Модерация'], ['stats', 'Статистика'], ['all', 'Все донаты'], ['payouts', 'Выплаты']];
    return (
      <ScreenScroll>
        <TopBar title="Донаты креаторов" onBack={pop} />
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.adminDonTabs}>
          {tabs.map(([id, label]) => (
            <SelectChip key={id} label={label} active={dt === id} onPress={() => patch({ adminDonTab: id })} />
          ))}
        </ScrollView>
        {dt === 'stats' ? <View style={s.kpiRow}><Kpi label="ДОНАТОВ ВСЕГО" value="1" /><Kpi label="КОМИССИЯ" value="2%" accent={color.lime} /></View> : null}
        {dt === 'all' ? <Card><Text style={s.opLabel}>utochkinrenat@gmail.com — 100 ₽</Text><Text style={s.charSub}>12.07.2026 · К выплате</Text></Card> : null}
        {dt === 'payouts' ? <Text style={s.empty}>Заявок на вывод пока нет.</Text> : null}
        {dt === 'moderation' ? <Card><Text style={[s.opLabel, { color: color.pink, lineHeight: 18 }]}>У Tribute нет API для списка донатов — создавайте вручную в Dashboard по данным из вебхука.</Text></Card> : null}
      </ScreenScroll>
    );
  }

  return (
    <ScreenScroll>
      <TopBar title={`Привет, ${userName} 👋`} />
      <Text style={s.charSub}>Неизвестный экран: {cur}</Text>
    </ScreenScroll>
  );
}

const s = StyleSheet.create({
  flex1: { flex: 1 },
  errorBanner: { color: color.red, fontSize: 12, marginBottom: 8, paddingHorizontal: 4 },
  kpiRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 4 },
  listPad: { paddingVertical: 4 },
  recentList: { paddingVertical: 6, paddingHorizontal: 10 },
  dialogsScroll: { gap: 0, paddingTop: 0 },
  dialogsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingBottom: 10,
  },
  dialogsTitle: {
    fontFamily: font.display,
    fontSize: 26,
    fontWeight: '800',
    color: color.text,
  },
  dialogList: { paddingTop: 0 },
  dialogRowWrap: {
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.045)',
  },
  folderAddBtn: {
    width: 38,
    height: 38,
    borderRadius: 12,
    backgroundColor: 'rgba(215,244,82,0.1)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  folderTabs: { gap: 22, paddingHorizontal: 18, paddingBottom: 10, marginBottom: 0, borderBottomWidth: 1, borderBottomColor: 'rgba(255,255,255,0.07)' },
  folderTab: { paddingVertical: 12, paddingHorizontal: 2, borderBottomWidth: 2.5, borderBottomColor: 'transparent', marginBottom: -1 },
  folderTabActive: { borderBottomColor: color.lime },
  folderTabText: { fontSize: 17, fontWeight: '600', color: color.muted },
  folderTabTextActive: { fontWeight: '800', color: color.text },
  folderActions: { flexDirection: 'row', gap: 8, marginBottom: 8 },
  folderActionBtn: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.12)',
  },
  folderActionText: { fontSize: 11.5, fontWeight: '700', color: color.purple },
  menuPickRow: { paddingVertical: 12, paddingHorizontal: 4, borderBottomWidth: 1, borderBottomColor: 'rgba(255,255,255,0.06)' },
  menuPickText: { fontSize: 14.5, fontWeight: '700', color: color.text },
  divider: { height: 1, backgroundColor: 'rgba(255,255,255,0.05)' },
  threadHead: { flexDirection: 'row', alignItems: 'center', gap: 9, paddingHorizontal: 14, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: color.border },
  threadName: { fontFamily: font.bodyExtra, fontSize: 14, color: color.text },
  threadSub: { fontSize: 10, color: color.muted },
  threadMsgs: { paddingHorizontal: 14, paddingVertical: 12, gap: 9 },
  composer: { flexDirection: 'row', gap: 7, alignItems: 'center', paddingHorizontal: 12, paddingVertical: 8, borderTopWidth: 1, borderTopColor: color.border },
  attach: { width: 34, height: 34, borderRadius: 10, borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)', alignItems: 'center', justifyContent: 'center' },
  input: {
    flex: 1,
    backgroundColor: color.inputBg,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.09)',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 9,
    color: color.text,
    fontFamily: font.body,
    fontSize: 13,
  },
  inputPh: { fontSize: 12.5, color: color.dim },
  send: { width: 34, height: 34, borderRadius: 10, backgroundColor: color.lime, alignItems: 'center', justifyContent: 'center' },
  gap10: { gap: 10 },
  gap9: { gap: 9 },
  gap8: { gap: 8 },
  gap6: { gap: 6 },
  slotRow: { flexDirection: 'row', gap: 8 },
  promptBox: { backgroundColor: color.inputBg, borderWidth: 1, borderColor: 'rgba(255,255,255,0.09)', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10 },
  promptText: { fontSize: 11.5, color: color.dim },
  warnCard: { backgroundColor: 'rgba(251,146,60,0.06)', borderColor: 'rgba(251,146,60,0.25)' },
  warnText: { fontSize: 11, color: color.orange },
  grid2: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  archTile: { width: '48%', borderRadius: 10, overflow: 'hidden', backgroundColor: color.card, borderWidth: 1, borderColor: color.border },
  archImg: { width: '100%', aspectRatio: 9 / 16 },
  archWho: { paddingHorizontal: 8, paddingVertical: 6, fontSize: 10, fontWeight: '700', color: color.text },
  lightboxWrap: { position: 'relative', borderRadius: 14, overflow: 'hidden' },
  lightbox: { width: '100%', aspectRatio: 3 / 4, borderRadius: 14 },
  lightboxBadge: {
    position: 'absolute',
    left: 10,
    bottom: 10,
    fontFamily: font.mono,
    fontSize: 9,
    color: '#fff',
    backgroundColor: 'rgba(0,0,0,0.55)',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  rowGap8: { flexDirection: 'row', gap: 8 },
  rowGap7: { flexDirection: 'row', gap: 7 },
  limeHalf: { flex: 1, alignItems: 'center', paddingVertical: 11, borderRadius: 10, backgroundColor: color.lime },
  limeHalfText: { fontFamily: font.bodyExtra, fontSize: 12, color: color.limeText },
  purpleHalf: { flex: 1, alignItems: 'center', paddingVertical: 11, borderRadius: 10, borderWidth: 1, borderColor: 'rgba(192,132,252,0.35)' },
  purpleHalfText: { fontFamily: font.bodyBold, fontSize: 12, color: color.purple },
  ghostHalf: { flex: 1, alignItems: 'center', paddingVertical: 10, borderRadius: 10, borderWidth: 1, borderColor: 'rgba(255,255,255,0.12)' },
  ghostHalfText: { fontFamily: font.bodyBold, fontSize: 12, color: color.muted },
  videoPreview: { aspectRatio: 9 / 16, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  playCircle: { width: 34, height: 34, borderRadius: 17, backgroundColor: 'rgba(0,0,0,0.45)', alignItems: 'center', justifyContent: 'center' },
  limeFlex: { flex: 1, alignItems: 'center', paddingVertical: 11, borderRadius: 10, backgroundColor: color.lime },
  regenFlex: { flex: 1, alignItems: 'center', paddingVertical: 9, borderRadius: 9, borderWidth: 1, borderColor: 'rgba(255,255,255,0.12)' },
  regenText: { fontFamily: font.bodyBold, fontSize: 11.5, color: color.muted },
  rowCenter: { flexDirection: 'row', gap: 10, alignItems: 'center' },
  charName: { fontFamily: font.bodyExtra, fontSize: 13, color: color.text },
  charSub: { fontSize: 10.5, color: color.muted },
  charHead: { flexDirection: 'row', alignItems: 'center', gap: 9, paddingBottom: 12, paddingHorizontal: 4 },
  charTitle: { fontFamily: font.bodyExtra, fontSize: 15, color: color.text },
  tabRow: { flexDirection: 'row', gap: 6, paddingBottom: 2 },
  grid3: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  photoTile: { width: '31%', aspectRatio: 3 / 4, borderRadius: 10, justifyContent: 'flex-end', padding: 6 },
  photoTileWrap: { width: '31%', aspectRatio: 3 / 4, borderRadius: 10, overflow: 'hidden' },
  photoTileOverlay: { flex: 1, justifyContent: 'flex-end', padding: 6 },
  photoTag: { fontFamily: font.mono, fontSize: 7.5, color: '#fff', backgroundColor: 'rgba(0,0,0,0.6)', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, alignSelf: 'flex-start' },
  photoAdd: { width: '31%', aspectRatio: 3 / 4, borderWidth: 1.5, borderStyle: 'dashed', borderColor: 'rgba(255,255,255,0.18)', borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  photoAddText: { fontSize: 20, color: color.dim },
  limeBorder: { borderColor: 'rgba(215,244,82,0.3)' },
  pickTitle: { fontSize: 11, fontWeight: '700', color: color.text },
  savePhoto: { alignItems: 'center', paddingVertical: 9, borderRadius: 9, backgroundColor: color.lime },
  savePhotoText: { fontFamily: font.bodyExtra, fontSize: 12, color: color.limeText },
  appearance: { fontSize: 11.5, color: color.muted, lineHeight: 17 },
  descLoading: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  descLoadingText: { fontSize: 11.5, color: color.purple },
  genFromPhoto: { fontSize: 11.5, fontWeight: '700', color: color.purple },
  connIcon: { width: 34, height: 34, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  connName: { fontFamily: font.bodyExtra, fontSize: 13, color: color.text, marginBottom: 4 },
  profileEmail: { fontFamily: font.bodyExtra, fontSize: 15, color: color.text },
  between: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  planTitle: { fontFamily: font.bodyExtra, fontSize: 14, color: color.text },
  planName: { fontFamily: font.bodyExtra, fontSize: 13, color: color.text },
  payBtn: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 9, borderWidth: 1, borderColor: 'rgba(255,255,255,0.14)' },
  payBtnActive: { backgroundColor: color.lime, borderWidth: 0 },
  payBtnText: { fontFamily: font.bodyExtra, fontSize: 11.5, color: color.muted },
  payBtnTextActive: { color: color.limeText },
  creditAmt: { fontFamily: font.display, fontSize: 15, color: color.lime },
  opLabel: { fontSize: 11.5, color: color.text },
  greenText: { color: color.green, fontSize: 11.5 },
  redText: { color: color.red, fontSize: 11.5 },
  pinkBtn: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: color.pink, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10, marginTop: 4 },
  pinkBtnTitle: { flex: 1, fontFamily: font.bodyExtra, fontSize: 12.5, color: '#2A0A1C' },
  pinkBtnCost: { fontFamily: font.mono, fontSize: 10.5, color: '#5E2140' },
  donationRow: { paddingVertical: 4, borderBottomWidth: 1, borderBottomColor: 'rgba(255,255,255,0.06)' },
  linkText: { fontSize: 11, color: color.blue, marginTop: 4 },
  connExistingRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6 },
  redOutlineSmall: { paddingHorizontal: 10, paddingVertical: 7, borderRadius: 8, borderWidth: 1, borderColor: 'rgba(248,113,113,0.3)' },
  redOutline: { paddingHorizontal: 16, paddingVertical: 11, borderRadius: 10, borderWidth: 1, borderColor: 'rgba(248,113,113,0.3)' },
  adminHead: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingBottom: 12, paddingHorizontal: 4 },
  adminTitle: { flex: 1, fontFamily: font.display, fontSize: 17, color: color.text },
  bold: { fontWeight: '700' },
  dot: { width: 8, height: 8, borderRadius: 4, marginRight: 6 },
  okBtn: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 9, backgroundColor: color.lime },
  okText: { fontFamily: font.bodyExtra, fontSize: 11.5, color: color.limeText },
  adminDonTabs: { flexDirection: 'row', gap: 5, paddingBottom: 4 },
  empty: { textAlign: 'center', paddingVertical: 30, color: color.dim, fontSize: 12 },
  historyRow: { flexDirection: 'row', justifyContent: 'space-between' },
  historyLabel: { fontSize: 11.5, color: color.text },
  historyCost: { fontSize: 11.5, color: color.dim },
  vidModeCard: {
    flex: 1,
    backgroundColor: color.card,
    borderWidth: 1,
    borderColor: color.border,
    borderRadius: 12,
    padding: 12,
    gap: 4,
  },
  vidModeCardOn: { borderColor: 'rgba(215,244,82,0.35)', backgroundColor: 'rgba(215,244,82,0.06)' },
  vidModeCardDisabled: { opacity: 0.55 },
  vidModeHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8 },
  vidModeTitle: { fontFamily: font.bodyExtra, fontSize: 13, color: color.text },
  vidModeTitleOn: { color: color.lime },
  vidModeDesc: { fontSize: 10.5, color: color.muted, lineHeight: 15 },
  vidModeBadge: { fontFamily: font.mono, fontSize: 8, color: color.dim, backgroundColor: 'rgba(255,255,255,0.06)', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 5 },
  vidSoonCard: { paddingVertical: 28, alignItems: 'center' },
  vidSoonText: { fontSize: 12.5, color: color.muted },
  ffGenBtn: { backgroundColor: 'rgba(192,132,252,0.12)', borderWidth: 1, borderColor: 'rgba(192,132,252,0.35)', borderRadius: 12, paddingVertical: 14, paddingHorizontal: 16 },
  ffGenBtnText: { fontFamily: font.bodyExtra, fontSize: 13, color: color.purple, textAlign: 'center' },
  ffThumb: { width: '100%', aspectRatio: 9 / 16, borderRadius: 10 },
  ffDoneText: { fontFamily: font.bodyExtra, fontSize: 13, color: color.green },
  ffModalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.85)', justifyContent: 'center', padding: 16 },
  ffModalBody: { backgroundColor: color.card, borderRadius: 14, padding: 12, gap: 10, maxHeight: '90%' },
  ffModalHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  ffModalTitle: { fontFamily: font.bodyExtra, fontSize: 14, color: color.text },
  ffModalClose: { fontSize: 18, color: color.muted, paddingHorizontal: 8 },
  ffModalImg: { width: '100%', aspectRatio: 9 / 16, borderRadius: 10 },
});
