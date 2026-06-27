export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type UserRole = 0 | 1 | 2 | 3;
export type UserStatus = 0 | 1 | 2 | 3;

export type UserMe = {
  id: number;
  username: string;
  nickname: string;
  gender: number;
  role: UserRole;
  level: number;
  exp: number;
  city: string | null;
  birth: string | null;
  bio: string | null;
  is_verified: boolean;
  is_official: boolean;
  like_count: number;
  avatar_url: string | null;
  created_at: string | null;
  email: string | null;
  phone: string | null;
  status: UserStatus;
  safety_score: number;
  is_deleted: boolean;
  last_login_at: string | null;
  banned_at: string | null;
  ban_duration: string | null;
};

export type UserPublic = Omit<
  UserMe,
  "email" | "phone" | "status" | "safety_score" | "last_login_at" | "banned_at" | "ban_duration"
> & {
  is_followed_by_me?: boolean;
};

export type UserSearchItem = {
  id: number;
  username: string;
  nickname: string;
  avatar_url: string | null;
  level: number;
  is_verified: boolean;
  bio?: string;
  is_followed_by_me?: boolean;
};

export type PaginatedUserSearch = {
  items: UserSearchItem[];
  total: number;
};

export type UserTag = {
  tag_id: number;
  name: string;
  created_at: string;
};

export type UserEcho = {
  profile: string;
  emotion_tags: UserTag[];
  interest_tags: UserTag[];
  styles: UserTag[];
  languages: UserTag[];
  hourly_distribution: number[];
  total_play_count: number;
};

export type LoginInput = {
  username: string;
  password: string;
};

export type RegisterInput = {
  username: string;
  nickname: string;
  password: string;
  email?: string;
  phone?: string;
  gender?: number;
  birth?: string;
  bio?: string;
  city?: string;
  avatar?: File;
};

export type UpdateMeInput = {
  nickname?: string;
  email?: string;
  phone?: string;
  gender?: number;
  birth?: string;
  bio?: string;
  city?: string;
  avatar?: File;
};

export type UserAdminUpdate = {
  nickname?: string;
  email?: string;
  phone?: string;
  gender?: number;
  birth?: string;
  bio?: string;
  city?: string;
  role?: UserRole;
  status?: UserStatus;
  safety_score?: number;
  is_verified?: boolean;
  exp?: number;
  banned_at?: string | null;
  ban_duration?: string | null;
};

export type UserAdminCreateInput = {
  username: string;
  nickname: string;
  password: string;
  email?: string;
  phone?: string;
  gender?: number;
  birth?: string;
  bio?: string;
  city?: string;
  role?: UserRole;
  status?: UserStatus;
  safety_score?: number;
  is_verified?: boolean;
  exp?: number;
};

export type PaginatedUsers = {
  items: UserMe[];
  total: number;
};

/* ==================== Music ==================== */

export type Tag = { id: number; name: string };

export type Author = {
  id: number;
  username: string;
  nickname: string;
  avatar_url: string | null;
  ordinal: number;
};

export type Instrument = { id: number; name: string };

export type MusicListItem = {
  id: number;
  title: string;
  is_vip: boolean;
  hot: number;
  play_count: number;
  cover_icon_url: string | null;
  authors: Author[];
  style?: Tag;
  language?: Tag;
  emotion_tags: Tag[];
  interest_tags: Tag[];
  albums: { id: number; title: string }[];
  created_at: string;
  is_collected_by_me?: boolean;
};

export type PaginatedMusicList = {
  items: MusicListItem[];
  total: number;
};

export type AdminMusicListItem = MusicListItem & {
  is_published: boolean;
};

export type PaginatedAdminMusicList = {
  items: AdminMusicListItem[];
  total: number;
};

export type MusicDetail = {
  id: number;
  title: string;
  is_vip: boolean;
  source: string | null;
  style: Tag | null;
  language: Tag | null;
  collect_count: number;
  hot: number;
  comment_count: number;
  play_count: number;
  is_published: boolean;
  release_date: string | null;
  file_url: string | null;
  lyrics_url: string | null;
  cover_icon_url: string | null;
  cover_home_url: string | null;
  cover_play_url: string | null;
  authors: Author[];
  instruments: Instrument[];
  emotion_tags: Tag[];
  interest_tags: Tag[];
  created_at: string;
  updated_at: string;
  is_collected_by_me?: boolean;
};

export type MusicUpdateInput = {
  title?: string;
  is_vip?: boolean;
  source?: string;
  style_id?: number;
  language_id?: number;
  release_date?: string | null;
  author_ids?: number[];
  instrument_ids?: number[];
  emotion_tag_ids?: number[];
  interest_tag_ids?: number[];
  audio_file?: File;
  cover_icon?: File;
  cover_home?: File;
  cover_play?: File;
  lyrics_file?: File;
};

/* ==================== Recommendation ==================== */

export type RecommendChartItem = MusicListItem & {
  recommend_count: number;
};

export type RecommendChartList = {
  items: RecommendChartItem[];
};

/* ==================== Admin Album List ==================== */

export type AdminAlbumListItem = AlbumListItem & {
  authors: Author[];
  music_count: number;
  collect_count: number;
};

export type PaginatedAdminAlbumList = {
  items: AdminAlbumListItem[];
  total: number;
};

/* ==================== Album ==================== */

export type AlbumMusicItem = {
  id: number;
  title: string;
  is_vip: boolean;
  hot: number;
  play_count: number;
  cover_icon_url: string | null;
  ordinal: number;
  file_url?: string | null;
};

export type AlbumListItem = {
  id: number;
  title: string;
  hot: number;
  play_count: number;
  cover_icon_url: string | null;
  created_at: string;
};

export type PaginatedAlbumList = {
  items: AlbumListItem[];
  total: number;
};

export type AlbumDetail = {
  id: number;
  title: string;
  description: string | null;
  source: string | null;
  collect_count: number;
  play_count: number;
  hot: number;
  cover_icon_url: string | null;
  cover_url: string | null;
  authors: Author[];
  musics: AlbumMusicItem[];
  emotion_tags: Tag[];
  interest_tags: Tag[];
  created_at: string;
  updated_at: string;
  is_collected_by_me?: boolean;
};

export type AlbumCreateInput = {
  title: string;
  description?: string;
  source?: string;
  author_ids?: number[];
};

export type AlbumUpdateInput = {
  title?: string;
  description?: string;
  source?: string;
  author_ids?: number[];
};

/* ==================== Play History ==================== */

export type PlayHistoryMusicItem = {
  id: number;
  title: string;
  cover_icon_url: string | null;
  authors: Author[];
};

export type PlayHistoryItem = {
  id: number;
  played_at: string;
  play_count: number;
  music: PlayHistoryMusicItem;
};

export type PaginatedPlayHistoryList = {
  items: PlayHistoryItem[];
  total: number;
};

/* ==================== Playlist ==================== */

export type PlaylistUser = {
  id: number;
  username: string;
  nickname: string;
  avatar_url: string | null;
};

export type PlaylistMusic = {
  music: MusicListItem;
  ordinal: number;
};

export type PlaylistDetail = {
  id: number;
  title: string;
  description: string | null;
  is_private: boolean;
  cover_icon_url: string | null;
  collect_count: number;
  play_count: number;
  hot: number;
  comment_count: number;
  is_like: boolean;
  is_recommended: boolean;
  user: PlaylistUser;
  musics: PlaylistMusic[];
  emotion_tags: Tag[];
  interest_tags: Tag[];
  created_at: string;
  updated_at: string;
  is_collected_by_me?: boolean;
};

export type PlaylistListItem = {
  id: number;
  title: string;
  is_private: boolean;
  is_like: boolean;
  cover_icon_url: string | null;
  user: PlaylistUser;
  created_at: string;
};

export type PaginatedPlaylistList = {
  items: PlaylistListItem[];
  total: number;
};

export type PlaylistMembershipItem = {
  id: number;
  title: string;
  is_private: boolean;
  is_like: boolean;
  cover_icon_url: string | null;
  contains_music: boolean;
};

export type PaginatedPlaylistMembership = {
  items: PlaylistMembershipItem[];
  total: number;
};

export type PlaylistUpdateInput = {
  title?: string;
  description?: string;
  is_private?: boolean;
  cover_icon?: File;
};

/* ==================== Comment ==================== */

export type CommentTargetType = "music" | "playlist" | "space_post";

export type CommentUser = {
  id: number;
  username: string;
  nickname: string;
  avatar_url: string | null;
};

export type CommentItem = {
  id: number;
  content: string;
  user: CommentUser;
  like_count: number;
  dislike_count: number;
  reply_count: number;
  parent_id: number | null;
  root_id: number | null;
  is_nested_reply: boolean;
  parent_user?: CommentUser | null;
  created_at: string;
  liked_by_me?: boolean;
  disliked_by_me?: boolean;
  is_deleted?: boolean;
  deletion_reason?: string | null;
};

export type PaginatedCommentList = {
  items: CommentItem[];
  total: number;
};

export type CommentCreateInput = {
  target_type: CommentTargetType;
  target_id: number;
  content: string;
  parent_id?: number;
};

/* ==================== Collection ==================== */

export type MusicCollectionItem = {
  music: MusicListItem;
  created_at: string;
};

export type AlbumCollectionItem = {
  album: AlbumListItem;
  created_at: string;
};

export type PlaylistCollectionItem = {
  playlist: PlaylistListItem;
  created_at: string;
};

export type PaginatedMusicCollection = {
  items: MusicCollectionItem[];
  total: number;
};

export type PaginatedAlbumCollection = {
  items: AlbumCollectionItem[];
  total: number;
};

export type PaginatedPlaylistCollection = {
  items: PlaylistCollectionItem[];
  total: number;
};

/* ==================== Space Post ==================== */

export type SpacePostImage = {
  image_url: string;
  ordinal: number;
};

export type SpacePostDetail = {
  id: number;
  user_id: number;
  content: string | null;
  is_private: boolean;
  comment_count: number;
  like_count?: number;
  liked_by_me?: boolean;
  images: SpacePostImage[];
  created_at: string;
  updated_at: string;
  is_deleted?: boolean;
  deletion_reason?: string | null;
};

export type SpacePostListItem = {
  id: number;
  user_id: number;
  content: string | null;
  is_private: boolean;
  comment_count: number;
  like_count?: number;
  liked_by_me?: boolean;
  images: SpacePostImage[];
  created_at: string;
  is_deleted?: boolean;
  deletion_reason?: string | null;
};

export type PaginatedSpacePostList = {
  items: SpacePostListItem[];
  total: number;
};

/* ==================== Dictionary ==================== */

export type DictionaryType =
  | "styles"
  | "languages"
  | "instruments"
  | "emotion_tags"
  | "interest_tags";

export type DictionaryItem = {
  id: number;
  name: string;
};

export type PaginatedDictionaryItems = {
  items: DictionaryItem[];
  total: number;
};

/* ==================== Notification & Message ==================== */

export type NotificationType = 0 | 1 | 2 | 3 | 4 | 5;

export type NotificationActor = {
  id: number;
  username: string;
  nickname: string;
  avatar_url: string | null;
  is_official: boolean;
};

export type NotificationItem = {
  id: number;
  type: NotificationType;
  target_type: "user" | "comment" | "space_post";
  target_id: number;
  is_read: boolean;
  extra: Record<string, unknown>;
  created_at: string;
  actor: NotificationActor | null;
};

export type PaginatedNotificationList = {
  items: NotificationItem[];
  total: number;
};

export type UnreadSummary = {
  notification_unread: number;
  message_unread: number;
};

export type MessagePeer = {
  id: number;
  username: string;
  nickname: string;
  avatar_url: string | null;
  is_official: boolean;
};

export type DirectMessageItem = {
  id: number;
  conversation_id: number;
  sender_id: number;
  content: string;
  created_at: string;
};

export type ConversationItem = {
  id: number;
  peer: MessagePeer;
  last_message: DirectMessageItem | null;
  unread_count: number;
  is_blocked_by_me: boolean;
  is_blocking_me: boolean;
  updated_at: string;
};

export type PaginatedConversationList = {
  items: ConversationItem[];
  total: number;
};

export type PaginatedDirectMessageList = {
  items: DirectMessageItem[];
  total: number;
};

export type InboxEvent =
  | {
      type: "notification";
      id: number;
      notification_type: NotificationType;
      target_type: "user" | "comment" | "space_post";
      target_id: number;
    }
  | {
      type: "message";
      conversation_id: number;
      message_id: number;
      sender_id: number;
      content: string;
    };

/* ==================== System Log ==================== */

export type SystemLogLevel = "WARNING" | "ERROR" | "CRITICAL";

export type SystemLogItem = {
  id: number;
  created_at: string;
  level: SystemLogLevel;
  logger: string;
  message: string;
  request_method: string | null;
  request_path: string | null;
  has_stack_trace: boolean;
};

export type SystemLogDetail = {
  id: number;
  created_at: string;
  level: SystemLogLevel;
  logger: string;
  message: string;
  stack_trace: string | null;
  request_method: string | null;
  request_path: string | null;
  request_body: string | null;
  response_body: string | null;
  extra: string | null;
};

export type PaginatedSystemLogs = {
  items: SystemLogItem[];
  total: number;
};

export type AgentMonitorRunStatus =
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELLED";

export type AgentMonitorRun = {
  id: string;
  trace_id: string;
  parent_run_id: string | null;
  scenario: string;
  workflow_type: string;
  workflow_name: string;
  workflow_version: string | null;
  actor_user_id: number | null;
  actor_username: string | null;
  subject_type: string | null;
  subject_id: string | null;
  thread_id: string | null;
  status: AgentMonitorRunStatus;
  model: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  event_count: number;
  tool_call_count: number;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
};

export type AgentMonitorRunDetail = AgentMonitorRun & {
  input: unknown;
  output: unknown;
  error: unknown;
  metadata: Record<string, unknown> | null;
};

export type AgentMonitorEvent = {
  id: number;
  run_id: string;
  sequence: number;
  event_type: string;
  component_type: string;
  component_name: string | null;
  status: AgentMonitorRunStatus | null;
  payload: unknown;
  error: unknown;
  framework_run_id: string | null;
  framework_parent_run_id: string | null;
  occurred_at: string;
  ended_at: string | null;
  duration_ms: number | null;
};

export type AgentMonitorRunPage = {
  items: AgentMonitorRun[];
  total: number;
  next_cursor: string | null;
};

/* ==================== Content Moderation ==================== */

export type ModerationSafetyLevel = "SAFE" | "RISKY" | "DANGEROUS";
export type ModerationRecommendationLevel = "NORMAL" | "RECOMMENDED";
export type ContentModerationStatus =
  | "PENDING"
  | "PROCESSING"
  | "SUCCEEDED"
  | "FAILED"
  | "MANUAL";

export type AdminModeratedContent = {
  id: number;
  content_type: "comment" | "space_post";
  user_id: number;
  username: string;
  content: string | null;
  target_type: string | null;
  target_id: number | null;
  safety_score: number;
  recommendation_score: number;
  safety_level: ModerationSafetyLevel | null;
  recommendation_level: ModerationRecommendationLevel | null;
  moderation_status: ContentModerationStatus;
  moderation_reason: string | null;
  is_recommended: boolean;
  is_deleted: boolean;
  deletion_reason: string | null;
  moderated_at: string | null;
  created_at: string;
};

export type PaginatedModeratedContent = {
  items: AdminModeratedContent[];
  total: number;
};

export type ManualModerationInput = {
  safety_score: number;
  recommendation_score: number;
  reason: string;
};


/* ==================== AI Assistant ==================== */

export type AIConversationRole = "system" | "human" | "ai" | "tool";

export type AIMusicCardAttachment = {
  version: 1;
  type: "music_card";
  items: Array<{
    id: number;
    title: string;
    authors: string[];
    album: string | null;
    cover_url: string | null;
    is_vip: boolean;
  }>;
};

export type AIPlaylistCardAttachment = {
  version: 1;
  type: "playlist_card";
  items: Array<{
    id: number;
    title: string;
    creator: string;
    description: string | null;
    cover_url: string | null;
    music_count: number;
  }>;
};

export type AIAlbumCardAttachment = {
  version: 1;
  type: "album_card";
  items: Array<{
    id: number;
    title: string;
    authors: string[];
    description: string | null;
    cover_url: string | null;
    music_count: number;
  }>;
};

export type AIConfirmationCardAttachment = {
  version: 1;
  type: "confirmation_card";
  resource_type: "music" | "playlist" | "album";
  action: "collect" | "uncollect";
  resource: {
    id: number;
    title: string;
    cover_url: string | null;
  };
  confirmation_token: string;
  prompt: string;
};

export type AIConversationAttachment =
  | AIMusicCardAttachment
  | AIPlaylistCardAttachment
  | AIAlbumCardAttachment
  | AIConfirmationCardAttachment;

export type AIConversationMessage = {
  role: AIConversationRole;
  content: string | Record<string, unknown>[];
  reasoning_content?: string | null;
  tool_call_id?: string | null;
  name?: string | null;
  tool_calls?: Record<string, unknown>[] | null;
  attachments?: AIConversationAttachment[];
  artifact?: AIConversationAttachment | Record<string, unknown> | null;
  additional_kwargs?: Record<string, unknown> | null;
  created_at?: string | null;
};

export type AIConversation = {
  id: number;
  user_id: number;
  title: string;
  model: string;
  status: number;
  thread_id: string;
  updated_at: string;
  created_at: string;
};

export type PaginatedAIConversationList = {
  items: AIConversation[];
  total: number;
};

export type AIConversationMessages = {
  messages: AIConversationMessage[];
};

export type AIConversationCreateInput = {
  title?: string;
  model?: string;
  first_message?: string;
  stream?: boolean;
};

export type AIConversationWithFirstMessage = {
  conversation: AIConversation;
  ai_message: AIConversationMessage | null;
};

export type AIConversationMessageCreateInput = {
  content: string;
  stream?: boolean;
  confirmation_token?: string;
};

export type AIStreamChunk = {
  type: "content" | "reasoning" | "attachment" | "done" | "error";
  data: string;
  model: string | null;
  meta?: {
    conversation?: AIConversation;
    attachment?: AIConversationAttachment;
    [key: string]: unknown;
  } | null;
};

// ---------- Music Knowledge (admin) ----------

export type MusicKnowledgeIngestResult = {
  source: string;
  chunk_count: number;
};

export type MusicKnowledgeSourceList = {
  items: string[];
  total: number;
};

export type MusicKnowledgeDeleteResult = {
  deleted_chunks: number;
};

// ---------- Private Roam ----------

export type RoamState = {
  playlist: number[];
  position: number;
  current_song: MusicListItem;
  pref_pool_summary: Record<string, string>;
  dislike_pool_summary: Record<string, string>;
  recommend_reason: string | null;
};

export type RoamReport = {
  total_songs: number;
  favorited_count: number;
  disliked_count: number;
  favorited_songs: MusicListItem[];
  taste_summary: string;
  recommendation: string | null;
};

export type RoamGuideResponse = {
  parsed_intent: string;
  adjustments: Record<string, number>;
  new_state: RoamState;
};

// ---------- Content Appeal ----------

export type ContentAppeal = {
  id: number;
  content_type: string;
  content_id: number;
  user_id: number;
  moderation_version: number;
  status: "PENDING" | "APPROVED" | "DENIED";
  appeal_reason: string | null;
  admin_note: string | null;
  reviewer_user_id: number | null;
  resolved_at: string | null;
  created_at: string;
};

export type AppealCreateInput = {
  content_type: string;
  content_id: number;
  appeal_reason?: string | null;
};
