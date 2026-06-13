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
  is_official?: boolean;
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
};

export type PlayHistoryItem = {
  id: number;
  played_at: string;
  music: PlayHistoryMusicItem;
};

export type PlayHistoryCreateInput = {
  music_id: number;
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
  created_at: string;
  liked_by_me?: boolean;
  disliked_by_me?: boolean;
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

export type NotificationType = 0 | 1 | 2 | 3 | 4;

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

