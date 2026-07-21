export type TokenOut = { access_token: string; token_type: string };

export type UserMeOut = {
  id: number;
  email: string;
  credits_balance: number;
  billing_plan: string;
  plan_tier: string;
  plan_display_name?: string;
  subscription_status?: string;
  subscription_expires_at?: string | null;
  is_workspace_owner: boolean;
  is_platform_admin: boolean;
  permissions_mask: number;
  chat_allowed: boolean;
  workflow_demo_limited?: boolean;
  demo_generations_remaining?: number;
  telegram_linked?: boolean;
  email_setup_required?: boolean;
  online_payment_available?: boolean;
  tribute_billing_available?: boolean;
  plan_usage?: {
    users?: number;
    models?: number;
    dialogs_this_month?: number;
    limits?: Record<string, number>;
  };
};

export type ConversationOut = {
  id: number;
  platform: string;
  user_display_name?: string;
  external_chat_id?: string;
  last_message_preview?: string;
  last_message_at?: string;
  unread_count?: number;
  is_no_response?: boolean;
  manual_category?: string;
  user_lang?: string;
  updated_at?: string;
  is_blocked?: boolean;
  peer_unavailable?: boolean;
};

export type ConversationFolderOut = {
  id: number;
  name: string;
  sort_order: number;
  conversation_ids: number[];
};

export type MessageOut = {
  id: number;
  direction: 'inbound' | 'outbound';
  text_original: string;
  text_translated?: string | null;
  created_at: string;
  attachments?: { id: number; url: string; kind?: string }[];
  reactions?: { emoji: string; actor: string }[];
  pending?: boolean;
};

export type CompanionPersonaOut = {
  age?: string | null;
  city?: string | null;
  country?: string | null;
  personality?: string | null;
  speaking_style?: string | null;
};

export type StudioModelOut = {
  id: number;
  name: string;
  profile_text?: string;
  companion_persona?: CompanionPersonaOut | string;
  images?: { id: number; kind: string; url: string }[];
  camera_preset_id?: string | number | null;
  export_lat?: number | null;
  export_lon?: number | null;
  phone_exif_selfie_ready?: boolean;
  phone_exif_main_ready?: boolean;
  phone_exif_selfie_summary?: string | null;
  phone_exif_main_summary?: string | null;
};

export type StudioGenerationOut = {
  id: number;
  created_at: string;
  status: string;
  media_kind: 'image' | 'video';
  image_url?: string;
  video_url?: string;
  prompt_excerpt?: string;
  output_aspect?: string;
  studio_model_id?: number;
  job_id?: number;
  error_message?: string;
};

export type HealthOut = {
  studio_carousel_credit_cost?: number;
  studio_motion_video_pricing?: Record<string, unknown>;
  studio_image_pricing?: Record<string, unknown>;
};

export type IntegrationStatusOut = {
  telegram_connections?: PlatformConnectionOut[];
  fanvue_connections?: PlatformConnectionOut[];
  tribute_connections?: PlatformConnectionOut[];
  instagram_connections?: PlatformConnectionOut[];
  wavespeed_configured?: boolean;
  wavespeed_managed_by_platform?: boolean;
};

export type PlatformConnectionOut = {
  id: number;
  label?: string;
  bot_username?: string;
  studio_model_id?: number;
  webhook_registered?: boolean;
  oauth_connected?: boolean;
  creator_uuid?: string;
};

export type CreatorDonationLinkOut = {
  id: number;
  title: string;
  description?: string;
  currency?: string;
  status: string;
  min_amount_minor?: number;
  studio_model_id?: number;
  web_link?: string;
  telegram_link?: string;
};

export type CreatorDonationOverviewOut = {
  totals_by_currency?: Record<string, number>;
  pending_payout_by_currency?: Record<string, number>;
  donations_count?: number;
  active_links?: number;
};

export type CreatorDonationEventOut = {
  id: number;
  amount_minor: number;
  currency?: string;
  donor_label?: string;
  occurred_at?: string;
  payout_status?: string;
  donation_link_title?: string;
};

export type ChatterStatsMemberOut = {
  user_id?: number;
  outbound_messages?: number;
  conversations_replied?: number;
  median_reply_seconds?: number | null;
};

export type ChatterStatsSummaryOut = {
  self?: ChatterStatsMemberOut;
  self_row?: ChatterStatsMemberOut;
  members?: ChatterStatsMemberOut[];
};

export type WorkspaceMemberOut = {
  id: number;
  member_login: string;
  permissions_mask: number;
  allowed_studio_model_ids?: number[];
  is_active?: boolean;
  tribute_share_percent?: number | null;
};

export type AdminUserRow = {
  id: number;
  email: string;
  role?: string;
  billing_plan?: string;
  credits_balance?: number;
  subscription_status?: string;
};

export type AdminPlanShare = {
  label: string;
  count: number;
  pct: number;
};

export type AdminEngagementStats = {
  paid_active_owners?: number;
  paid_active_pct?: number;
};

export type AdminStats = {
  total_users?: number;
  payments_total?: number;
  revenue_month_rub?: number;
  top_plans?: AdminPlanShare[];
  engagement?: AdminEngagementStats;
};

export type SupportTicketReplyOut = {
  id: number;
  is_staff: boolean;
  message: string;
  created_at: string;
};

export type SupportTicketListItemOut = {
  id: number;
  type: string;
  subject: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type SupportTicketOut = SupportTicketListItemOut & {
  message: string;
  replies: SupportTicketReplyOut[];
};

export type LocalFile = {
  uri: string;
  name: string;
  type: string;
};
