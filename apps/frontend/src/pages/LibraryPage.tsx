import { useState, useEffect, useCallback } from "react";
import { Music2, Disc, ListMusic, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";

import { usePlayerStore } from "../shared/stores/playerStore";
import { collectionApi, musicApi } from "../shared/api/instances";
import type {
  MusicCollectionItem,
  AlbumCollectionItem,
  PlaylistCollectionItem,
  MusicListItem,
} from "../shared/api/types";
import { formatAuthors, toPlayerTrack } from "../shared/utils";
import { EmptyState } from "../components/ui/EmptyState";
import { FadeIn } from "../components/motion/FadeIn";
import { StaggerContainer, StaggerItem } from "../components/motion/StaggerContainer";
import { CoverCard } from "../components/ui/CoverCard";
import { SongRow } from "../components/ui/SongRow";
import { PaginationBar } from "../components/ui/PaginationBar";

const PAGE_SIZE = 12;

const tabs = [
  { key: "songs", label: "收藏歌曲", icon: Music2 },
  { key: "albums", label: "收藏专辑", icon: Disc },
  { key: "playlists", label: "收藏歌单", icon: ListMusic },
] as const;

type TabKey = (typeof tabs)[number]["key"];

export const LibraryPage = () => {
  const navigate = useNavigate();
  const playStandalone = usePlayerStore((s) => s.playStandalone);

  const [activeTab, setActiveTab] = useState<TabKey>("songs");

  // Songs
  const [songs, setSongs] = useState<MusicCollectionItem[]>([]);
  const [songsTotal, setSongsTotal] = useState(0);
  const [songsPage, setSongsPage] = useState(0);
  const [songsLoading, setSongsLoading] = useState(false);

  // Albums
  const [albums, setAlbums] = useState<AlbumCollectionItem[]>([]);
  const [albumsTotal, setAlbumsTotal] = useState(0);
  const [albumsPage, setAlbumsPage] = useState(0);
  const [albumsLoading, setAlbumsLoading] = useState(false);

  // Playlists
  const [playlists, setPlaylists] = useState<PlaylistCollectionItem[]>([]);
  const [playlistsTotal, setPlaylistsTotal] = useState(0);
  const [playlistsPage, setPlaylistsPage] = useState(0);
  const [playlistsLoading, setPlaylistsLoading] = useState(false);

  const loadSongs = useCallback(async () => {
    setSongsLoading(true);
    try {
      const res = await collectionApi.listMusicCollections({ limit: PAGE_SIZE, offset: songsPage * PAGE_SIZE });
      setSongs(res.items);
      setSongsTotal(res.total);
    } catch {
      toast.error("加载收藏歌曲失败");
    } finally {
      setSongsLoading(false);
    }
  }, [songsPage]);

  const loadAlbums = useCallback(async () => {
    setAlbumsLoading(true);
    try {
      const res = await collectionApi.listAlbumCollections({ limit: PAGE_SIZE, offset: albumsPage * PAGE_SIZE });
      setAlbums(res.items);
      setAlbumsTotal(res.total);
    } catch {
      toast.error("加载收藏专辑失败");
    } finally {
      setAlbumsLoading(false);
    }
  }, [albumsPage]);

  const loadPlaylists = useCallback(async () => {
    setPlaylistsLoading(true);
    try {
      const res = await collectionApi.listPlaylistCollections({ limit: PAGE_SIZE, offset: playlistsPage * PAGE_SIZE });
      setPlaylists(res.items);
      setPlaylistsTotal(res.total);
    } catch {
      toast.error("加载收藏歌单失败");
    } finally {
      setPlaylistsLoading(false);
    }
  }, [playlistsPage]);

  useEffect(() => {
    if (activeTab === "songs") loadSongs();
    else if (activeTab === "albums") loadAlbums();
    else loadPlaylists();
  }, [activeTab, loadSongs, loadAlbums, loadPlaylists]);

  /** 取消收藏歌曲 */
  const handleUncollectSong = async (item: MusicCollectionItem) => {
    try {
      await collectionApi.uncollectMusic(item.music.id);
      setSongs((prev) => prev.filter((s) => s.music.id !== item.music.id));
      setSongsTotal((t) => Math.max(0, t - 1));
      toast.success("已取消收藏");
    } catch {
      toast.error("操作失败");
    }
  };

  /** 取消收藏专辑 */
  const handleUncollectAlbum = async (item: AlbumCollectionItem) => {
    try {
      await collectionApi.uncollectAlbum(item.album.id);
      setAlbums((prev) => prev.filter((a) => a.album.id !== item.album.id));
      setAlbumsTotal((t) => Math.max(0, t - 1));
      toast.success("已取消收藏");
    } catch {
      toast.error("操作失败");
    }
  };

  /** 取消收藏歌单 */
  const handleUncollectPlaylist = async (item: PlaylistCollectionItem) => {
    try {
      await collectionApi.uncollectPlaylist(item.playlist.id);
      setPlaylists((prev) => prev.filter((p) => p.playlist.id !== item.playlist.id));
      setPlaylistsTotal((t) => Math.max(0, t - 1));
      toast.success("已取消收藏");
    } catch {
      toast.error("操作失败");
    }
  };

  /** 播放收藏的歌曲 */
  const handlePlaySong = async (music: MusicListItem) => {
    try {
      const detail = await musicApi.getMusicDetail(music.id);
      if (detail.file_url) {
        await playStandalone({ ...music, file_url: detail.file_url });
      } else {
        toast.error("该歌曲暂不可播放");
      }
    } catch {
      toast.error("加载歌曲失败");
    }
  };

  return (
    <div>
      <FadeIn>
        <h1 className="page-title">我的收藏</h1>
      </FadeIn>

      <FadeIn delay={0.08}>
        <div className="search-tabs" style={{ marginBottom: 20 }}>
          {tabs.map((tab) => (
            <motion.button
              key={tab.key}
              className={`search-tab ${activeTab === tab.key ? "active" : ""}`}
              onClick={() => setActiveTab(tab.key)}
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

      {/* ===== 收藏歌曲 ===== */}
      {activeTab === "songs" && (
        <>
          {songsLoading ? (
            <div className="loading-screen" style={{ height: "30vh" }}>
              <div style={{ fontSize: 14, fontWeight: 500 }}>加载中...</div>
            </div>
          ) : songs.length === 0 ? (
            <EmptyState icon={Music2} title="暂无收藏歌曲" description="在浏览歌曲时点击收藏，它们将出现在这里。" />
          ) : (
            <FadeIn delay={0.12}>
              <StaggerContainer staggerDelay={0.03}>
                {songs.map((item, i) => (
                  <StaggerItem key={item.music.id}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <SongRow
                          index={i}
                          name={item.music.title}
                          artist={formatAuthors(item.music.authors)}
                          musicId={item.music.id}
                          coverUrl={item.music.cover_icon_url ?? undefined}
                          onPlay={() => handlePlaySong(item.music)}
                        />
                      </div>
                      <motion.button
                        className="ghost-button"
                        onClick={() => handleUncollectSong(item)}
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        type="button"
                        title="取消收藏"
                        style={{ padding: "6px 8px", minHeight: "auto", color: "var(--color-muted)", flexShrink: 0 }}
                      >
                        <X size={16} />
                      </motion.button>
                    </div>
                  </StaggerItem>
                ))}
              </StaggerContainer>
              {(Math.ceil(songsTotal / PAGE_SIZE) > 1 || songsTotal > 0) && (
                <PaginationBar page={songsPage} totalPages={Math.ceil(songsTotal / PAGE_SIZE)} onPageChange={setSongsPage} loading={songsLoading} total={songsTotal} />
              )}
            </FadeIn>
          )}
        </>
      )}

      {/* ===== 收藏专辑 ===== */}
      {activeTab === "albums" && (
        <>
          {albumsLoading ? (
            <div className="loading-screen" style={{ height: "30vh" }}>
              <div style={{ fontSize: 14, fontWeight: 500 }}>加载中...</div>
            </div>
          ) : albums.length === 0 ? (
            <EmptyState icon={Disc} title="暂无收藏专辑" description="在浏览专辑时点击收藏，它们将出现在这里。" />
          ) : (
            <FadeIn delay={0.12}>
              <StaggerContainer className="playlist-rail">
                {albums.map((item) => (
                  <StaggerItem key={item.album.id}>
                    <div style={{ position: "relative" }}>
                      <CoverCard
                        id={item.album.id}
                        title={item.album.title}
                        subtitle={`播放量 ${item.album.play_count}`}
                        coverUrl={item.album.cover_icon_url ?? undefined}
                        onClick={() => navigate(`/album/${item.album.id}`)}
                      />
                      <motion.button
                        onClick={() => handleUncollectAlbum(item)}
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        type="button"
                        title="取消收藏"
                        style={{
                          position: "absolute",
                          top: 6,
                          right: 6,
                          width: 24,
                          height: 24,
                          borderRadius: "50%",
                          background: "rgba(0,0,0,0.5)",
                          color: "white",
                          border: "none",
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                      >
                        <X size={13} />
                      </motion.button>
                    </div>
                  </StaggerItem>
                ))}
              </StaggerContainer>
              {(Math.ceil(albumsTotal / PAGE_SIZE) > 1 || albumsTotal > 0) && (
                <PaginationBar page={albumsPage} totalPages={Math.ceil(albumsTotal / PAGE_SIZE)} onPageChange={setAlbumsPage} loading={albumsLoading} total={albumsTotal} />
              )}
            </FadeIn>
          )}
        </>
      )}

      {/* ===== 收藏歌单 ===== */}
      {activeTab === "playlists" && (
        <>
          {playlistsLoading ? (
            <div className="loading-screen" style={{ height: "30vh" }}>
              <div style={{ fontSize: 14, fontWeight: 500 }}>加载中...</div>
            </div>
          ) : playlists.length === 0 ? (
            <EmptyState icon={ListMusic} title="暂无收藏歌单" description="在浏览歌单时点击收藏，它们将出现在这里。" />
          ) : (
            <FadeIn delay={0.12}>
              <StaggerContainer className="playlist-rail">
                {playlists.map((item) => (
                  <StaggerItem key={item.playlist.id}>
                    <div style={{ position: "relative" }}>
                      <CoverCard
                        id={item.playlist.id}
                        title={item.playlist.title}
                        subtitle={`${item.playlist.user.nickname}${item.playlist.is_private ? " · 私密" : ""}`}
                        coverUrl={item.playlist.cover_icon_url ?? undefined}
                        onClick={() => navigate(`/playlist/${item.playlist.id}`)}
                      />
                      <motion.button
                        onClick={() => handleUncollectPlaylist(item)}
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        type="button"
                        title="取消收藏"
                        style={{
                          position: "absolute",
                          top: 6,
                          right: 6,
                          width: 24,
                          height: 24,
                          borderRadius: "50%",
                          background: "rgba(0,0,0,0.5)",
                          color: "white",
                          border: "none",
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                      >
                        <X size={13} />
                      </motion.button>
                    </div>
                  </StaggerItem>
                ))}
              </StaggerContainer>
              {(Math.ceil(playlistsTotal / PAGE_SIZE) > 1 || playlistsTotal > 0) && (
                <PaginationBar page={playlistsPage} totalPages={Math.ceil(playlistsTotal / PAGE_SIZE)} onPageChange={setPlaylistsPage} loading={playlistsLoading} total={playlistsTotal} />
              )}
            </FadeIn>
          )}
        </>
      )}
    </div>
  );
};
