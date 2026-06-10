import { useEffect } from "react";
import { Routes, Route, Navigate, Outlet } from "react-router-dom";

import { useAuthStore } from "./shared/stores/authStore";
import { AppShell } from "./components/layout/AppShell";
import { AuthPage } from "./pages/AuthPage";
import { DiscoverPage } from "./pages/DiscoverPage";
import { PlaylistsPage } from "./pages/PlaylistsPage";
import { LibraryPage } from "./pages/LibraryPage";
import { HistoryPage } from "./pages/HistoryPage";
import { EchoPage } from "./pages/EchoPage";
import { SearchPage } from "./pages/SearchPage";
import { ProfilePage } from "./pages/ProfilePage";
import { AccountPage } from "./pages/AccountPage";
import { AdminShell } from "./pages/admin/AdminShell";
import { AdminDashboardPage } from "./pages/admin/AdminDashboardPage";
import { UserManagementPage } from "./pages/admin/UserManagementPage";
import { AdminMusicPage } from "./pages/admin/AdminMusicPage";
import { AdminMusicImportPage } from "./pages/admin/AdminMusicImportPage";
import { DictionaryPage } from "./pages/admin/DictionaryPage";
import { MusicDetailPage } from "./pages/MusicDetailPage";
import { AlbumDetailPage } from "./pages/AlbumDetailPage";

/** 未登录时重定向到登录页 */
const RequireAuth = () => {
  const { user, loading, initialized } = useAuthStore();

  useEffect(() => {
    if (!initialized) {
      void useAuthStore.getState().init();
    }
  }, [initialized]);

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

  return <Outlet />;
};

/** 非管理员重定向到首页 */
const AdminRouteGuard = () => {
  const { user } = useAuthStore();
  if (!user || (user.role !== 2 && user.role !== 3)) {
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
          <Route path="/playlists" element={<PlaylistsPage />} />
          <Route path="/library" element={<LibraryPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/echo" element={<EchoPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/profile/:userId" element={<ProfilePage />} />
          <Route path="/account" element={<AccountPage />} />
          <Route path="/music/:musicId" element={<MusicDetailPage />} />
          <Route path="/album/:albumId" element={<AlbumDetailPage />} />
        </Route>

        {/* 管理后台路由 */}
        <Route element={<AdminRouteGuard />}>
          <Route element={<AdminShell />}>
            <Route path="/admin" element={<AdminDashboardPage />} />
            <Route path="/admin/users" element={<UserManagementPage />} />
            <Route path="/admin/music" element={<AdminMusicPage />} />
            <Route path="/admin/music/import" element={<AdminMusicImportPage />} />
            <Route path="/admin/dict" element={<DictionaryPage />} />
          </Route>
        </Route>
      </Route>

      {/* Catch all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
