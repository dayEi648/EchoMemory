import { useEffect, useState } from "react";
import { Routes, Route, Navigate, Outlet } from "react-router-dom";

import { useAuthStore } from "./shared/stores/authStore";
import { usePlayerStore } from "./shared/stores/playerStore";
import { useInboxStore } from "./shared/stores/inboxStore";
import { AppShell } from "./components/layout/AppShell";
import { AuthPage } from "./pages/AuthPage";
import { DiscoverPage } from "./pages/DiscoverPage";
import { DailyRecommendPage } from "./pages/DailyRecommendPage";
import { RadarPage } from "./pages/RadarPage";
import { RoamPage } from "./pages/RoamPage";
import { PlaylistsPage } from "./pages/PlaylistsPage";
import { LibraryPage } from "./pages/LibraryPage";
import { HistoryPage } from "./pages/HistoryPage";
import { EchoPage } from "./pages/EchoPage";
import { SearchPage } from "./pages/SearchPage";
import { ProfilePage } from "./pages/ProfilePage";
import { AccountPage } from "./pages/AccountPage";
import { MessagesPage } from "./pages/MessagesPage";
import { AIAssistantPage } from "./pages/AIAssistantPage";
import { AdminShell } from "./pages/admin/AdminShell";
import { AdminDashboardPage } from "./pages/admin/AdminDashboardPage";
import { UserManagementPage } from "./pages/admin/UserManagementPage";
import { AdminMusicPage } from "./pages/admin/AdminMusicPage";
import { AdminMusicImportPage } from "./pages/admin/AdminMusicImportPage";
import { DictionaryPage } from "./pages/admin/DictionaryPage";
import { AdminAlbumPage } from "./pages/admin/AdminAlbumPage";
import { AdminCarouselPage } from "./pages/admin/AdminCarouselPage";
import { AdminHotnessPage } from "./pages/admin/AdminHotnessPage";
import { AdminLogPage } from "./pages/admin/AdminLogPage";
import { AdminAIConversationMonitorPage } from "./pages/admin/AdminAIConversationMonitorPage";
import { AdminContentModerationMonitorPage } from "./pages/admin/AdminContentModerationMonitorPage";
import { MusicRouteOpener } from "./pages/MusicRouteOpener";
import { AlbumDetailPage } from "./pages/AlbumDetailPage";
import { PlaylistDetailPage } from "./pages/PlaylistDetailPage";
import { SpacePage } from "./pages/SpacePage";
import { BrowsePage } from "./pages/BrowsePage";
import { AdminCommentModerationPage } from "./pages/admin/AdminCommentModerationPage";
import { AdminSpacePostModerationPage } from "./pages/admin/AdminSpacePostModerationPage";
import { AdminMusicKnowledgePage } from "./pages/admin/AdminMusicKnowledgePage";

/** 未登录时重定向到登录页 */
const RequireAuth = () => {
  const { user, loading, initialized } = useAuthStore();

  useEffect(() => {
    if (!initialized) {
      void useAuthStore.getState().init();
    }
  }, [initialized]);

  // 用户登录后恢复上一次的播放器状态
  useEffect(() => {
    if (user && initialized) {
      usePlayerStore.getState().initFromStorage();
    }
  }, [user, initialized]);

  // 用户登录后建立 WebSocket 推送并刷新未读数
  useEffect(() => {
    if (user && initialized) {
      useInboxStore.getState().connectWebSocket();
      void useInboxStore.getState().refreshUnread();
    }
  }, [user, initialized]);

  // 用户登出时重置 inbox
  useEffect(() => {
    if (!user && initialized) {
      useInboxStore.getState().reset();
    }
  }, [user, initialized]);

  if (loading) {
    return (
      <div className="loading-screen">
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: 12,
              background: "var(--color-ink)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              animation: "pulse-loading 1.5s ease-in-out infinite",
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 18V5l12-2v13" />
              <circle cx="6" cy="18" r="3" />
              <circle cx="18" cy="16" r="3" />
            </svg>
          </div>
          <div style={{ fontSize: 14, fontWeight: 500 }}>正在进入回声记忆</div>
        </div>
      </div>
    );
  }

  if (!user) {
    return <AuthPage />;
  }

  if (user.status !== 0) {
    const statusMessage =
      user.status === 1
        ? "账号已被临时封禁，暂时无法使用。"
        : user.status === 2
          ? "账号已被暂停使用，请联系管理员。"
          : "账号已被封禁，无法继续使用。";

    return (
      <div className="loading-screen">
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, maxWidth: 360, textAlign: "center" }}>
          <div style={{ fontSize: 16, fontWeight: 600 }}>无法进入应用</div>
          <p style={{ margin: 0, fontSize: 14, color: "var(--color-muted)", lineHeight: 1.6 }}>{statusMessage}</p>
          <button
            type="button"
            onClick={() => void useAuthStore.getState().logout()}
            style={{
              padding: "8px 18px",
              borderRadius: 10,
              border: "none",
              background: "var(--color-ink)",
              color: "white",
              cursor: "pointer",
              fontSize: 14,
              fontWeight: 600,
            }}
          >
            退出登录
          </button>
        </div>
      </div>
    );
  }

  return <Outlet />;
};

const ADMIN_ROLE_POLL_MS = 30_000;

/** 非管理员重定向到首页；进入与停留期间持续校验管理员身份 */
const AdminRouteGuard = () => {
  const { user, refreshUser } = useAuthStore();
  const [verified, setVerified] = useState(false);

  const isAdmin = !!user && (user.role === 2 || user.role === 3);

  useEffect(() => {
    let cancelled = false;

    const runCheck = async () => {
      await refreshUser();
      if (!cancelled) setVerified(true);
    };

    void runCheck();

    const intervalId = window.setInterval(() => {
      void refreshUser();
    }, ADMIN_ROLE_POLL_MS);

    const onFocus = () => {
      void refreshUser();
    };
    window.addEventListener("focus", onFocus);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
      window.removeEventListener("focus", onFocus);
    };
  }, [refreshUser]);

  if (!verified) {
    if (!isAdmin) {
      return <Navigate to="/" replace />;
    }
    return (
      <div className="loading-screen">
        <div style={{ fontSize: 14, fontWeight: 500 }}>验证权限中...</div>
      </div>
    );
  }

  if (!isAdmin) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
};

export default function App() {
  return (
    <Routes>
      <Route element={<RequireAuth />}>
        {/* 主应用路由 */}
        <Route element={<AppShell />}>
          <Route path="/" element={<DiscoverPage />} />
          <Route path="/daily-recommend" element={<DailyRecommendPage />} />
          <Route path="/personal-radar" element={<RadarPage />} />
          <Route path="/personal-roam" element={<RoamPage />} />
          <Route path="/playlists" element={<PlaylistsPage />} />
          <Route path="/library" element={<LibraryPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/echo" element={<EchoPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/profile/:userId" element={<ProfilePage />} />
          <Route path="/account" element={<AccountPage />} />
          <Route path="/music/:musicId" element={<MusicRouteOpener />} />
          <Route path="/album/:albumId" element={<AlbumDetailPage />} />
          <Route path="/playlist/:playlistId" element={<PlaylistDetailPage />} />
          <Route path="/browse" element={<BrowsePage />} />
          <Route path="/space" element={<SpacePage />} />
          <Route path="/space/:userId" element={<SpacePage />} />
          <Route path="/messages" element={<MessagesPage />} />
          <Route path="/ai-assistant" element={<AIAssistantPage />} />
        </Route>

        {/* 管理后台路由 */}
        <Route element={<AdminRouteGuard />}>
          <Route element={<AdminShell />}>
            <Route path="/admin" element={<AdminDashboardPage />} />
            <Route path="/admin/users" element={<UserManagementPage />} />
            <Route path="/admin/music" element={<AdminMusicPage />} />
            <Route path="/admin/music/import" element={<AdminMusicImportPage />} />
            <Route path="/admin/dict" element={<DictionaryPage />} />
            <Route path="/admin/albums" element={<AdminAlbumPage />} />
            <Route path="/admin/carousel" element={<AdminCarouselPage />} />
            <Route path="/admin/hotness" element={<AdminHotnessPage />} />
            <Route path="/admin/logs" element={<AdminLogPage />} />
            <Route
              path="/admin/music-knowledge"
              element={<AdminMusicKnowledgePage />}
            />
            <Route path="/admin/comments" element={<AdminCommentModerationPage />} />
            <Route path="/admin/space-posts" element={<AdminSpacePostModerationPage />} />
            <Route
              path="/admin/agent-monitor/ai-conversation"
              element={<AdminAIConversationMonitorPage />}
            />
            <Route
              path="/admin/agent-monitor/content-moderation"
              element={<AdminContentModerationMonitorPage />}
            />
          </Route>
        </Route>
      </Route>

      {/* Catch all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
