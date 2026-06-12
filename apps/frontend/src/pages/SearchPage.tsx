import { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  Music,
  ListMusic,
  Disc,
  User,
  Search,
  UserPlus,
  UserMinus,
} from "lucide-react";
import { toast } from "sonner";
import { motion } from "framer-motion";

import { useAuthStore } from "../shared/stores/authStore";
import { musicApi, albumApi, playlistApi } from "../shared/api/instances";
import { usePlayMusic } from "../shared/usePlayMusic";
import type {
  UserSearchItem,
  MusicListItem,
  AlbumListItem,
  PlaylistListItem,
} from "../shared/api/types";
import { Avatar } from "../components/ui/Avatar";
import { EmptyState } from "../components/ui/EmptyState";
import { FadeIn } from "../components/motion/FadeIn";
import {
  StaggerContainer,
  StaggerItem,
} from "../components/motion/StaggerContainer";
import { CoverCard } from "../components/ui/CoverCard";
import { SongRow } from "../components/ui/SongRow";
import { PaginationBar } from "../components/ui/PaginationBar";
import { PaginatedPageLayout } from "../components/layout/PaginatedPageLayout";
import { formatAlbumTitle, formatAuthors } from "../shared/utils";

const tabs = [
  { key: "all", label: "综合", icon: Search },
  { key: "songs", label: "单曲", icon: Music },
  { key: "playlists", label: "歌单", icon: ListMusic },
  { key: "albums", label: "专辑", icon: Disc },
  { key: "users", label: "用户", icon: User },
];

const PAGE_SIZE = 10;

const VALID_TABS = new Set(tabs.map((t) => t.key));

export const SearchPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get("q") ?? "";
  const tabFromUrl = searchParams.get("tab") ?? "all";
  const [activeTab, setActiveTab] = useState(() => (VALID_TABS.has(tabFromUrl) ? tabFromUrl : "all"));
  const { api, user: currentUser } = useAuthStore();
  const navigate = useNavigate();
  const { playMusicListItem } = usePlayMusic();

  const [userResults, setUserResults] = useState<UserSearchItem[]>([]);
  const [songResults, setSongResults] = useState<MusicListItem[]>([]);
  const [albumResults, setAlbumResults] = useState<AlbumListItem[]>([]);
  const [playlistResults, setPlaylistResults] = useState<PlaylistListItem[]>([]);
  const [userTotal, setUserTotal] = useState(0);
  const [songTotal, setSongTotal] = useState(0);
  const [albumTotal, setAlbumTotal] = useState(0);
  const [playlistTotal, setPlaylistTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [followedIds, setFollowedIds] = useState<Set<number>>(new Set());

  // 各 Tab 独立分页
  const [songPage, setSongPage] = useState(0);
  const [albumPage, setAlbumPage] = useState(0);
  const [playlistPage, setPlaylistPage] = useState(0);
  const [userPage, setUserPage] = useState(0);

  useEffect(() => {
    if (VALID_TABS.has(tabFromUrl)) {
      setActiveTab(tabFromUrl);
    }
  }, [tabFromUrl]);

  // 切换关键词时重置分页
  useEffect(() => {
    setSongPage(0);
    setAlbumPage(0);
    setPlaylistPage(0);
    setUserPage(0);
  }, [query]);

  // 综合页一次性加载；分类页按当前页加载
  useEffect(() => {
    if (!query.trim()) return;
    setLoading(true);

    if (activeTab === "all") {
      Promise.all([
        api.searchUsers(query.trim(), PAGE_SIZE, 0),
        musicApi.searchMusic({ q: query.trim(), limit: PAGE_SIZE, offset: 0 }),
        albumApi.searchAlbums({
          q: query.trim(),
          limit: PAGE_SIZE,
          offset: 0,
        }),
        playlistApi.searchPlaylists({
          q: query.trim(),
          limit: PAGE_SIZE,
          offset: 0,
        }),
      ])
        .then(([users, songs, albums, playlists]) => {
          setUserResults(users.items);
          setFollowedIds(
            new Set(users.items.filter((u) => u.is_followed_by_me).map((u) => u.id)),
          );
          setSongResults(songs.items);
          setAlbumResults(albums.items);
          setPlaylistResults(playlists.items);
          setUserTotal(users.total);
          setSongTotal(songs.total);
          setAlbumTotal(albums.total);
          setPlaylistTotal(playlists.total);
        })
        .catch((err) => {
          toast.error(err instanceof Error ? err.message : "搜索失败");
        })
        .finally(() => setLoading(false));
    } else if (activeTab === "songs") {
      musicApi
        .searchMusic({
          q: query.trim(),
          limit: PAGE_SIZE,
          offset: songPage * PAGE_SIZE,
        })
        .then((songs) => {
          setSongResults(songs.items);
          setSongTotal(songs.total);
        })
        .catch((err) => {
          toast.error(err instanceof Error ? err.message : "搜索失败");
        })
        .finally(() => setLoading(false));
    } else if (activeTab === "albums") {
      albumApi
        .searchAlbums({
          q: query.trim(),
          limit: PAGE_SIZE,
          offset: albumPage * PAGE_SIZE,
        })
        .then((albums) => {
          setAlbumResults(albums.items);
          setAlbumTotal(albums.total);
        })
        .catch((err) => {
          toast.error(err instanceof Error ? err.message : "搜索失败");
        })
        .finally(() => setLoading(false));
    } else if (activeTab === "playlists") {
      playlistApi
        .searchPlaylists({
          q: query.trim(),
          limit: PAGE_SIZE,
          offset: playlistPage * PAGE_SIZE,
        })
        .then((playlists) => {
          setPlaylistResults(playlists.items);
          setPlaylistTotal(playlists.total);
        })
        .catch((err) => {
          toast.error(err instanceof Error ? err.message : "搜索失败");
        })
        .finally(() => setLoading(false));
    } else if (activeTab === "users") {
      api
        .searchUsers(query.trim(), PAGE_SIZE, userPage * PAGE_SIZE)
        .then((users) => {
          setUserResults(users.items);
          setFollowedIds(
            new Set(users.items.filter((u) => u.is_followed_by_me).map((u) => u.id)),
          );
          setUserTotal(users.total);
        })
        .catch((err) => {
          toast.error(err instanceof Error ? err.message : "搜索失败");
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [query, activeTab, songPage, albumPage, playlistPage, userPage, api]);

  const handleToggleFollow = async (userId: number) => {
    try {
      if (followedIds.has(userId)) {
        await api.unfollow(userId);
        setFollowedIds((prev) => { const next = new Set(prev); next.delete(userId); return next; });
      } else {
        await api.follow(userId);
        setFollowedIds((prev) => { const next = new Set(prev); next.add(userId); return next; });
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "操作失败");
    }
  };

  const songTotalPages = Math.ceil(songTotal / PAGE_SIZE);
  const albumTotalPages = Math.ceil(albumTotal / PAGE_SIZE);
  const playlistTotalPages = Math.ceil(playlistTotal / PAGE_SIZE);
  const userTotalPages = Math.ceil(userTotal / PAGE_SIZE);

  const showSongSection =
    activeTab === "songs" || (activeTab === "all" && songResults.length > 0);
  const showPlaylistSection =
    activeTab === "playlists" ||
    (activeTab === "all" && playlistResults.length > 0);
  const showAlbumSection =
    activeTab === "albums" || (activeTab === "all" && albumResults.length > 0);
  const showUserSection =
    activeTab === "users" || (activeTab === "all" && userResults.length > 0);
  const allTabEmpty =
    activeTab === "all" &&
    songResults.length === 0 &&
    playlistResults.length === 0 &&
    albumResults.length === 0 &&
    userResults.length === 0;

  const emptyQuery = !query.trim();

  const paginationFooter =
    activeTab === "songs" && (songTotalPages > 1 || songTotal > 0) ? (
      <PaginationBar page={songPage} totalPages={songTotalPages} onPageChange={setSongPage} loading={loading} total={songTotal} />
    ) : activeTab === "albums" && (albumTotalPages > 1 || albumTotal > 0) ? (
      <PaginationBar page={albumPage} totalPages={albumTotalPages} onPageChange={setAlbumPage} loading={loading} total={albumTotal} />
    ) : activeTab === "playlists" && (playlistTotalPages > 1 || playlistTotal > 0) ? (
      <PaginationBar page={playlistPage} totalPages={playlistTotalPages} onPageChange={setPlaylistPage} loading={loading} total={playlistTotal} />
    ) : activeTab === "users" && (userTotalPages > 1 || userTotal > 0) ? (
      <PaginationBar page={userPage} totalPages={userTotalPages} onPageChange={setUserPage} loading={loading} total={userTotal} />
    ) : undefined;

  return (
    <PaginatedPageLayout
      header={(
        <>
          <FadeIn>
            <h1 className="page-title">
              {emptyQuery ? "搜索" : `「${query}」的搜索结果`}
            </h1>
          </FadeIn>
          <FadeIn delay={0.06}>
            <div className="category-tabs">
              {tabs.map((tab) => (
                <motion.button
                  key={tab.key}
                  className={`category-tab ${activeTab === tab.key ? "active" : ""}`}
                  onClick={() => {
                    setActiveTab(tab.key);
                    if (query) {
                      setSearchParams({ q: query, tab: tab.key });
                    }
                  }}
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  type="button"
                >
                  <tab.icon size={14} />
                  {tab.label}
                </motion.button>
              ))}
            </div>
          </FadeIn>
        </>
      )}
      footer={paginationFooter}
    >
      {emptyQuery ? (
        <FadeIn>
          <EmptyState
            icon={Search}
            title="请输入搜索关键词"
            description="在顶部搜索框输入内容，即可搜索歌曲、歌单、专辑和用户。"
          />
        </FadeIn>
      ) : loading ? (
        <FadeIn delay={0.12}>
          <div className="empty-state">
            <p>搜索中...</p>
          </div>
        </FadeIn>
      ) : (
        <>
          {allTabEmpty && (
            <FadeIn delay={0.12}>
              <EmptyState icon={Search} title="未找到相关内容" compact />
            </FadeIn>
          )}

          {/* Songs */}
          {showSongSection && (
            <section style={{ marginBottom: 28 }}>
              <FadeIn delay={0.1}>
                <div className="section-header">
                  <h3 className="page-section-title">
                    单曲
                    {songTotal > 0 && (
                      <span
                        style={{
                          fontSize: 13,
                          color: "var(--color-muted)",
                          fontWeight: 400,
                          marginLeft: 8,
                        }}
                      >
                        共 {songTotal} 首
                      </span>
                    )}
                  </h3>
                  {activeTab === "all" && songResults.length > 0 && (
                    <button
                      className="ghost-button"
                      onClick={() => setActiveTab("songs")}
                      style={{ fontSize: 13 }}
                    >
                      查看更多
                    </button>
                  )}
                </div>
              </FadeIn>
              {songResults.length === 0 ? (
                <FadeIn delay={0.15}>
                  <EmptyState icon={Music} title="未找到相关歌曲" compact />
                </FadeIn>
              ) : (
                <>
                  <StaggerContainer staggerDelay={0.04}>
                    {(activeTab === "all"
                      ? songResults.slice(0, 6)
                      : songResults
                    ).map((song, i) => (
                      <StaggerItem key={song.id}>
                        <SongRow
                          name={song.title}
                          artist={formatAuthors(song.authors)}
                          album={formatAlbumTitle(song.albums)}
                          playCount={song.play_count}
                          musicId={song.id}
                          coverUrl={song.cover_icon_url ?? undefined}
                          onPlay={() => playMusicListItem(song)}
                        />
                      </StaggerItem>
                    ))}
                  </StaggerContainer>
                </>
              )}
            </section>
          )}

          {/* Playlists */}
          {showPlaylistSection && (
            <section style={{ marginBottom: 28 }}>
              <FadeIn delay={0.1}>
                <div className="section-header">
                  <h3 className="page-section-title">
                    歌单
                    {playlistTotal > 0 && (
                      <span
                        style={{
                          fontSize: 13,
                          color: "var(--color-muted)",
                          fontWeight: 400,
                          marginLeft: 8,
                        }}
                      >
                        共 {playlistTotal} 个
                      </span>
                    )}
                  </h3>
                  {activeTab === "all" && playlistResults.length > 0 && (
                    <button
                      className="ghost-button"
                      onClick={() => setActiveTab("playlists")}
                      style={{ fontSize: 13 }}
                    >
                      查看更多
                    </button>
                  )}
                </div>
              </FadeIn>
              {playlistResults.length === 0 ? (
                <FadeIn delay={0.15}>
                  <EmptyState icon={ListMusic} title="未找到相关歌单" compact />
                </FadeIn>
              ) : (
                <StaggerContainer className="playlist-rail" staggerDelay={0.04}>
                  {(activeTab === "all"
                    ? playlistResults.slice(0, 5)
                    : playlistResults
                  ).map((playlist) => (
                    <StaggerItem key={playlist.id}>
                      <CoverCard
                        id={playlist.id}
                        title={playlist.title}
                        subtitle={playlist.user.nickname}
                        coverUrl={playlist.cover_icon_url ?? undefined}
                        onClick={() => navigate(`/playlist/${playlist.id}`)}
                      />
                    </StaggerItem>
                  ))}
                </StaggerContainer>
              )}
            </section>
          )}

          {/* Albums */}
          {showAlbumSection && (
            <section style={{ marginBottom: 28 }}>
              <FadeIn delay={0.1}>
                <div className="section-header">
                  <h3 className="page-section-title">
                    专辑
                    {albumTotal > 0 && (
                      <span
                        style={{
                          fontSize: 13,
                          color: "var(--color-muted)",
                          fontWeight: 400,
                          marginLeft: 8,
                        }}
                      >
                        共 {albumTotal} 张
                      </span>
                    )}
                  </h3>
                  {activeTab === "all" && albumResults.length > 0 && (
                    <button
                      className="ghost-button"
                      onClick={() => setActiveTab("albums")}
                      style={{ fontSize: 13 }}
                    >
                      查看更多
                    </button>
                  )}
                </div>
              </FadeIn>
              {albumResults.length === 0 ? (
                <FadeIn delay={0.15}>
                  <EmptyState icon={Disc} title="未找到相关专辑" compact />
                </FadeIn>
              ) : (
                <>
                  <StaggerContainer
                    className="playlist-rail"
                    staggerDelay={0.04}
                  >
                    {(activeTab === "all"
                      ? albumResults.slice(0, 5)
                      : albumResults
                    ).map((album) => (
                      <StaggerItem key={album.id}>
                        <CoverCard
                          id={album.id}
                          title={album.title}
                          subtitle={`播放量 ${album.play_count}`}
                          coverUrl={album.cover_icon_url ?? undefined}
                          onClick={() => navigate(`/album/${album.id}`)}
                        />
                      </StaggerItem>
                    ))}
                  </StaggerContainer>
                </>
              )}
            </section>
          )}

          {/* Users */}
          {showUserSection && (
            <section style={{ marginBottom: 28 }}>
              <FadeIn delay={0.1}>
                <div className="section-header">
                  <h3 className="page-section-title">
                    用户
                    {userTotal > 0 && (
                      <span
                        style={{
                          fontSize: 13,
                          color: "var(--color-muted)",
                          fontWeight: 400,
                          marginLeft: 8,
                        }}
                      >
                        共 {userTotal} 人
                      </span>
                    )}
                  </h3>
                  {activeTab === "all" && userResults.length > 0 && (
                    <button
                      className="ghost-button"
                      onClick={() => setActiveTab("users")}
                      style={{ fontSize: 13 }}
                    >
                      查看更多
                    </button>
                  )}
                </div>
              </FadeIn>
              {userResults.length === 0 ? (
                <FadeIn delay={0.15}>
                  <EmptyState icon={User} title="未找到相关用户" />
                </FadeIn>
              ) : (
                <>
                  <StaggerContainer
                    staggerDelay={0.05}
                    className={`user-search-grid ${activeTab === "all" ? "compact" : "full"}`}
                  >
                    {(activeTab === "all"
                      ? userResults.slice(0, 6)
                      : userResults
                    ).map((item) => (
                      <StaggerItem key={item.id}>
                        <motion.div
                          className="user-search-card"
                          whileHover={{
                            y: -2,
                            boxShadow: "0 4px 12px rgba(0,0,0,0.05)",
                          }}
                          transition={{ duration: 0.2 }}
                          onClick={() => navigate(`/profile/${item.id}`)}
                        >
                          <Avatar user={item} size="xl" />
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                            <div className="user-search-card-nickname">{item.nickname}</div>
                            {currentUser && currentUser.id !== item.id && (
                              <motion.button
                                onClick={(e) => { e.stopPropagation(); handleToggleFollow(item.id); }}
                                whileHover={{ scale: 1.05 }}
                                whileTap={{ scale: 0.92 }}
                                type="button"
                                style={{
                                  padding: "4px 10px",
                                  borderRadius: 6,
                                  border: followedIds.has(item.id) ? "1px solid var(--color-border)" : "none",
                                  background: followedIds.has(item.id) ? "var(--color-surface-soft)" : "var(--color-ink)",
                                  color: followedIds.has(item.id) ? "var(--color-ink)" : "white",
                                  cursor: "pointer",
                                  fontSize: 11,
                                  fontWeight: 600,
                                  flexShrink: 0,
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: 3,
                                }}
                              >
                                {followedIds.has(item.id) ? <UserMinus size={11} /> : <UserPlus size={11} />}
                                {followedIds.has(item.id) ? "已关注" : "关注"}
                              </motion.button>
                            )}
                          </div>
                          {item.bio && (
                            <div
                              className="user-search-card-bio"
                              title={item.bio}
                            >
                              {item.bio}
                            </div>
                          )}
                          <div className="user-search-card-meta">
                            @{item.username} · Lv.{item.level}
                          </div>
                        </motion.div>
                      </StaggerItem>
                    ))}
                  </StaggerContainer>
                </>
              )}
            </section>
          )}
        </>
      )}
    </PaginatedPageLayout>
  );
};
