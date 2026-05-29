export interface AdminLabelCount {
  label: string
  count: number
}

export interface AdminDayCount {
  date: string
  count: number
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
