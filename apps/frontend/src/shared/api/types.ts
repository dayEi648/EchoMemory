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
>;

export type UserSearchItem = {
  id: number;
  username: string;
  nickname: string;
  avatar_url: string | null;
  level: number;
  is_verified: boolean;
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

export type PaginatedUsers = {
  items: UserMe[];
  total: number;
};
