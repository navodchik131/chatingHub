export interface AdminLabelCount {
  label: string
  count: number
}

export interface AdminDayCount {
  date: string
  count: number
}

export interface AdminSegmentItem {
  user_id: number | null
  email: string | null
  user_created_at: string | null
  subscription_status: string | null
  billing_plan: string | null
  plan_tier: string | null
  detail: string | null
  occurred_at: string | null
  payment_id: string | null
}

export interface AdminSegmentResponse {
  segment: string
  title: string
  total: number
  items: AdminSegmentItem[]
}

export interface AdminFunnelStep {
  key: string
  label: string
  count: number
  pct_of_registered: number
}

export interface AdminActivationFunnel {
  days: number
  registered: number
  steps: AdminFunnelStep[]
  events_by_name: Record<string, number>
}

export interface AdminEngagementStats {
  active_owners_7d: number
  active_owners_30d: number
  active_owners_7d_pct: number
  active_owners_30d_pct: number
  paid_active_owners: number
  paid_active_pct: number
  trialing_owners: number
  past_due_owners: number
  paid_or_trialing_owners: number
  paid_or_trialing_pct: number
  zombie_owners: number
  zombie_pct: number
  engaged_owners_ever: number
  owners_yookassa_credits_buyers: number
  owners_with_studio: number
  owners_with_chat: number
  registered_owners_30d: number
  new_paid_active_owners_30d: number
  new_paid_active_30d_pct: number
}

export interface AdminStats {
  total_users: number
  workspace_owners: number
  workspace_members: number
  total_credits_balance: number
  studio_generations_total: number
  usage_by_kind: Record<string, number>
  studio_models_total: number
  studio_model_images_total: number
  studio_images_total: number
  studio_videos_total: number
  studio_motion_renders_total: number
  conversations_total: number
  referrals_total: number
  yookassa_payments_total: number
  subscriptions_by_status: AdminLabelCount[]
  subscriptions_by_plan: AdminLabelCount[]
  registrations_by_day: AdminDayCount[]
  generations_by_day: AdminDayCount[]
  chart_days: number
  engagement: AdminEngagementStats
  activation_funnel: AdminActivationFunnel
}

export interface AdminUserRow {
  id: number
  email: string
  created_at: string
  is_active: boolean
  is_platform_admin: boolean
  parent_user_id: number | null
  parent_email: string | null
  member_login: string | null
  subscription_status: string
  billing_plan: string
  plan_tier: string | null
  subscription_period_end: string | null
  credits_balance: number
  studio_models_count: number
  studio_generations_count: number
}

export interface AdminUserDetail extends AdminUserRow {
  studio_models_count: number
  studio_generations_count: number
  invited_users_count: number
  referred_by_email: string | null
  conversations_count: number
  workspace_members_count: number
}

export interface AdminEmailSegmentOption {
  id: string
  title: string
}

export interface AdminEmailConfig {
  smtp_configured: boolean
  from_email: string | null
  from_name: string | null
  segments: AdminEmailSegmentOption[]
}

export interface AdminEmailTemplate {
  id: string
  name: string
  subject: string
  body_html: string
  body_text: string
}

export interface AdminEmailSegmentPreview {
  segment: string
  title: string
  segment_total: number
  eligible: number
  opted_out: number
  inactive: number
}

export interface AdminEmailCampaign {
  id: number
  segment: string
  segment_title: string
  subject: string
  body_html: string
  body_text: string | null
  status: string
  recipient_count: number
  sent_count: number
  failed_count: number
  skipped_count: number
  error_message: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface AdminExifBotStats {
  total_users: number
  total_profiles: number
  total_processes: number
  processes_today: number
  active_users_7d: number
  active_users_30d: number
  users_with_profiles: number
  utc_day: string
}

export interface AdminExifBotUserRow {
  id: number
  telegram_id: number
  username: string | null
  display_name: string
  telegram_link: string | null
  language_code: string | null
  profiles_count: number
  total_process_count: number
  daily_process_count: number
  daily_process_day: string | null
  created_at: string
  updated_at: string
}

export interface AdminExifBotProfileRow {
  id: number
  title: string
  camera_preset_id: string | null
  has_selfie_ref: boolean
  has_main_ref: boolean
  has_gps: boolean
  is_ready: boolean
  created_at: string
  updated_at: string
}

export interface AdminExifBotUserDetail extends AdminExifBotUserRow {
  profiles: AdminExifBotProfileRow[]
}
