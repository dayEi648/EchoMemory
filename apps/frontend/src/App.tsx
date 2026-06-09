import {
  BadgeCheck,
  Ban,
  CircleUserRound,
  LayoutDashboard,
  LogOut,
  Music2,
  Search,
  Settings,
  ShieldCheck,
  UserRoundCog,
  UsersRound,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { createMemoryTokenStore, type TokenStore } from "./shared/auth/tokenStore";
import { ApiError, createUserApi } from "./shared/api/userApi";
import type { UserMe, UserRole, UserSearchItem, UserStatus } from "./shared/api/types";

type RouteName = "home" | "profile" | "admin" | "music";

type AppProps = {
  tokenStore?: TokenStore;
  initialRoute?: RouteName;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

const roleLabel: Record<UserRole, string> = {
  0: "普通用户",
  1: "VIP",
  2: "管理员",
  3: "超级管理员",
};

const statusLabel: Record<UserStatus, string> = {
  0: "正常",
  1: "临时封禁",
  2: "限制中",
  3: "已封禁",
};

const cityOptions = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "西安", "重庆"];

const isAdmin = (user: UserMe) => user.role === 2 || user.role === 3;

const Avatar = ({ user }: { user: Pick<UserMe, "avatar_url" | "nickname" | "username"> }) => {
  if (user.avatar_url) {
    return <img className="avatar" src={user.avatar_url} alt={`${user.nickname}的头像`} />;
  }
  return (
    <div className="avatar avatar-fallback" aria-label={`${user.nickname}的头像`}>
      {user.nickname.slice(0, 1) || user.username.slice(0, 1)}
    </div>
  );
};

const AuthScreen = ({
  tokenStore,
  onAuthenticated,
}: {
  tokenStore: TokenStore;
  onAuthenticated: (user: UserMe) => void;
}) => {
  const api = useMemo(() => createUserApi({ baseUrl: API_BASE_URL, tokenStore }), [tokenStore]);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setLoading(true);
    setError("");
    try {
      if (mode === "login") {
        await api.login({
          username: String(form.get("username") ?? ""),
          password: String(form.get("password") ?? ""),
        });
      } else {
        await api.register({
          username: String(form.get("username") ?? ""),
          nickname: String(form.get("nickname") ?? ""),
          password: String(form.get("password") ?? ""),
          email: String(form.get("email") ?? "") || undefined,
          gender: Number(form.get("gender") ?? 0),
          city: String(form.get("city") ?? "") || undefined,
        });
      }
      onAuthenticated(await api.getMe());
    } catch (err) {
      setError(err instanceof Error ? err.message : "认证失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <div className="brand-mark">
          <Music2 size={28} />
        </div>
        <p className="eyebrow">EchoMemory</p>
        <h1>回声记忆</h1>
        <p className="auth-copy">用 AI Agent 连接你的音乐偏好、记忆片段与创作线索。</p>
        <div className="segmented">
          <button className={mode === "login" ? "active" : ""} onClick={() => setMode("login")} type="button">
            登录
          </button>
          <button className={mode === "register" ? "active" : ""} onClick={() => setMode("register")} type="button">
            注册
          </button>
        </div>
        <form className="form-stack" onSubmit={handleSubmit}>
          <label>
            用户名
            <input name="username" minLength={3} maxLength={32} required />
          </label>
          {mode === "register" && (
            <label>
              昵称
              <input name="nickname" minLength={1} maxLength={32} required />
            </label>
          )}
          <label>
            密码
            <input name="password" type="password" minLength={6} maxLength={128} required />
          </label>
          {mode === "register" && (
            <>
              <label>
                邮箱
                <input name="email" type="email" />
              </label>
              <label>
                性别
                <select name="gender" defaultValue="0">
                  <option value="0">未知</option>
                  <option value="1">男</option>
                  <option value="2">女</option>
                </select>
              </label>
              <label>
                居住城市
                <select name="city" defaultValue="">
                  <option value="">暂不选择</option>
                  {cityOptions.map((city) => (
                    <option value={city} key={city}>
                      {city}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}
          {error && <p className="form-error">{error}</p>}
          <button className="primary-button" disabled={loading} type="submit">
            {loading ? "处理中" : mode === "login" ? "进入账户" : "创建账户"}
          </button>
        </form>
      </section>
      <section className="auth-artifact" aria-hidden="true">
        <div className="sound-card pink">Agent Profile</div>
        <div className="sound-card teal">Memory Graph</div>
        <div className="sound-card lavender">Taste Tags</div>
      </section>
    </main>
  );
};

const Shell = ({
  user,
  route,
  setRoute,
  onLogout,
  children,
}: {
  user: UserMe;
  route: RouteName;
  setRoute: (route: RouteName) => void;
  onLogout: () => void;
  children: ReactNode;
}) => (
  <div className="app-shell">
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-mark small">
          <Music2 size={20} />
        </div>
        <span>回声记忆</span>
      </div>
      <nav>
        <button className={route === "home" ? "active" : ""} onClick={() => setRoute("home")} type="button">
          <LayoutDashboard size={18} />
          首页
        </button>
        <button className={route === "profile" ? "active" : ""} onClick={() => setRoute("profile")} type="button">
          <CircleUserRound size={18} />
          个人中心
        </button>
        <button className={route === "admin" ? "active" : ""} onClick={() => setRoute("admin")} type="button">
          <UserRoundCog size={18} />
          管理后台
        </button>
        <button className={route === "music" ? "active" : ""} onClick={() => setRoute("music")} type="button">
          <Music2 size={18} />
          音乐模块
        </button>
      </nav>
      <button className="ghost-button logout-button" onClick={onLogout} type="button">
        <LogOut size={18} />
        退出登录
      </button>
    </aside>
    <main className="content">
      <header className="topbar">
        <div>
          <p className="eyebrow">Windows Desktop Alpha</p>
          <h2>{route === "home" ? "首页" : route === "profile" ? "个人中心" : route === "admin" ? "管理后台" : "音乐占位"}</h2>
        </div>
        <div className="user-chip">
          <Avatar user={user} />
          <div>
            <strong>{user.nickname}</strong>
            <span>{roleLabel[user.role]}</span>
          </div>
        </div>
      </header>
      {children}
    </main>
  </div>
);

const HomePage = ({ user, onSearch }: { user: UserMe; onSearch: (q: string) => Promise<UserSearchItem[]> }) => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<UserSearchItem[]>([]);
  const [error, setError] = useState("");

  const handleSearch = async () => {
    if (!query.trim()) {
      setResults([]);
      return;
    }
    try {
      setResults(await onSearch(query.trim()));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "搜索失败");
    }
  };

  return (
    <section className="page-grid">
      <article className="hero-card">
        <div>
          <p className="eyebrow">Profile Signal</p>
          <h1>欢迎，{user.nickname}</h1>
          <p>{user.bio || "你的音乐偏好会随着听歌历史逐步形成更清晰的回声画像。"}</p>
        </div>
        <div className="level-badge">Lv.{user.level}</div>
      </article>
      <article className="metric-card peach">
        <span>经验值</span>
        <strong>{user.exp}</strong>
      </article>
      <article className="metric-card ochre">
        <span>获赞</span>
        <strong>{user.like_count}</strong>
      </article>
      <article className="panel wide">
        <div className="panel-title">
          <UsersRound size={20} />
          <h3>用户搜索</h3>
        </div>
        <div className="search-row">
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索用户名或昵称" />
          <button className="primary-button" onClick={handleSearch} type="button">
            <Search size={18} />
            搜索
          </button>
        </div>
        {error && <p className="form-error">{error}</p>}
        <div className="result-list">
          {results.map((item) => (
            <div className="result-item" key={item.id}>
              <span>{item.nickname}</span>
              <small>@{item.username} · Lv.{item.level}</small>
            </div>
          ))}
        </div>
      </article>
      <PlaceholderModule title="音乐模块占位" />
    </section>
  );
};

const ProfilePage = ({ user, onSave }: { user: UserMe; onSave: (input: FormData) => Promise<void> }) => {
  const [error, setError] = useState("");
  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      await onSave(new FormData(event.currentTarget));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    }
  };

  return (
    <section className="profile-layout">
      <article className="profile-card">
        <Avatar user={user} />
        <h3>{user.nickname}</h3>
        <p>@{user.username}</p>
        <div className="badge-row">
          <span>{roleLabel[user.role]}</span>
          {user.is_verified && (
            <span>
              <BadgeCheck size={14} />
              已认证
            </span>
          )}
        </div>
      </article>
      <form className="panel form-stack" onSubmit={handleSubmit}>
        <h3>资料编辑</h3>
        <label>
          昵称
          <input name="nickname" defaultValue={user.nickname} required />
        </label>
        <label>
          邮箱
          <input name="email" type="email" defaultValue={user.email ?? ""} />
        </label>
        <label>
          手机号
          <input name="phone" defaultValue={user.phone ?? ""} />
        </label>
        <label>
          性别
          <select name="gender" defaultValue={String(user.gender)}>
            <option value="0">未知</option>
            <option value="1">男</option>
            <option value="2">女</option>
          </select>
        </label>
        <label>
          生日
          <input name="birth" type="date" defaultValue={user.birth ?? ""} />
        </label>
        <label>
          居住城市
          <select name="city" defaultValue={user.city ?? ""} aria-label="居住城市">
            <option value="">暂不选择</option>
            {cityOptions.map((city) => (
              <option value={city} key={city}>
                {city}
              </option>
            ))}
          </select>
        </label>
        <label>
          简介
          <textarea name="bio" defaultValue={user.bio ?? ""} rows={4} />
        </label>
        {error && <p className="form-error">{error}</p>}
        <button className="primary-button" type="submit">
          保存资料
        </button>
      </form>
    </section>
  );
};

const AdminPage = ({
  user,
  listUsers,
  banUser,
  unbanUser,
}: {
  user: UserMe;
  listUsers: (q: string) => Promise<UserMe[]>;
  banUser: (userId: number) => Promise<UserMe>;
  unbanUser: (userId: number) => Promise<UserMe>;
}) => {
  const [users, setUsers] = useState<UserMe[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");

  if (!isAdmin(user)) {
    return (
      <section className="empty-state">
        <ShieldCheck size={42} />
        <h3>需要管理员权限</h3>
        <p>当前账号没有访问用户管理的权限。</p>
      </section>
    );
  }

  const load = async () => {
    try {
      setUsers(await listUsers(query));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    }
  };

  return (
    <section className="panel admin-panel">
      <div className="panel-title">
        <Settings size={20} />
        <h3>用户管理</h3>
      </div>
      <div className="search-row">
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索用户" />
        <button className="primary-button" onClick={load} type="button">
          搜索
        </button>
      </div>
      {error && <p className="form-error">{error}</p>}
      <div className="admin-table">
        {(users.length ? users : [user]).map((item) => (
          <div className="admin-row" key={item.id}>
            <span>{item.nickname}</span>
            <small>@{item.username}</small>
            <span>{roleLabel[item.role]}</span>
            <span>{statusLabel[item.status]}</span>
            {item.status === 0 ? (
              <button className="danger-button" onClick={() => void banUser(item.id)} type="button">
                <Ban size={16} />
                封禁
              </button>
            ) : (
              <button className="ghost-button" onClick={() => void unbanUser(item.id)} type="button">
                解封
              </button>
            )}
          </div>
        ))}
      </div>
      <PlaceholderModule title="内容审核占位" compact />
    </section>
  );
};

const PlaceholderModule = ({ title, compact = false }: { title: string; compact?: boolean }) => (
  <article className={compact ? "placeholder compact" : "placeholder"}>
    <Music2 size={compact ? 22 : 34} />
    <h3>{title}</h3>
    <p>该模块本阶段仅展示入口和状态，不接入真实业务接口。</p>
  </article>
);

const appTokenStore = createMemoryTokenStore();

export default function App({ tokenStore = appTokenStore, initialRoute = "home" }: AppProps) {
  const api = useMemo(() => createUserApi({ baseUrl: API_BASE_URL, tokenStore }), [tokenStore]);
  const [route, setRoute] = useState<RouteName>(initialRoute);
  const [user, setUser] = useState<UserMe | null>(null);
  const [loading, setLoading] = useState(Boolean(tokenStore.get()));
  const [error, setError] = useState("");

  useEffect(() => {
    if (!tokenStore.get()) {
      setLoading(false);
      return;
    }
    api
      .getMe()
      .then(setUser)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          tokenStore.clear();
        }
        setError(err instanceof Error ? err.message : "加载当前用户失败");
      })
      .finally(() => setLoading(false));
  }, [api, tokenStore]);

  if (loading) {
    return <div className="loading-screen">正在进入回声记忆</div>;
  }

  if (!user) {
    return <AuthScreen tokenStore={tokenStore} onAuthenticated={setUser} />;
  }

  const saveProfile = async (formData: FormData) => {
    const updated = await api.updateMe({
      nickname: String(formData.get("nickname") ?? ""),
      email: String(formData.get("email") ?? "") || undefined,
      phone: String(formData.get("phone") ?? "") || undefined,
      gender: Number(formData.get("gender") ?? user.gender),
      birth: String(formData.get("birth") ?? "") || undefined,
      bio: String(formData.get("bio") ?? "") || undefined,
      city: String(formData.get("city") ?? "") || undefined,
    });
    setUser(updated);
  };

  return (
    <Shell
      user={user}
      route={route}
      setRoute={setRoute}
      onLogout={() => {
        void api.logout();
        setUser(null);
      }}
    >
      {error && <p className="form-error">{error}</p>}
      {route === "home" && <HomePage user={user} onSearch={api.searchUsers} />}
      {route === "profile" && <ProfilePage user={user} onSave={saveProfile} />}
      {route === "admin" && (
        <AdminPage
          user={user}
          listUsers={(q) => api.adminListUsers({ q })}
          banUser={(userId) => api.adminBanUser(userId, 3)}
          unbanUser={api.adminUnbanUser}
        />
      )}
      {route === "music" && <PlaceholderModule title="音乐模块占位" />}
    </Shell>
  );
}
