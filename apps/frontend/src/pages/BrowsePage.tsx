import { useState, useEffect, useCallback, useRef } from "react";
import { Music, Disc, ListMusic, Sparkles } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";

import { musicApi, albumApi, playlistApi } from "../shared/api/instances";
import { usePlayMusic } from "../shared/usePlayMusic";
import type { MusicListItem, AlbumListItem, PlaylistListItem } from "../shared/api/types";
import { formatAuthors, formatAlbumTitle } from "../shared/utils";
import { SongRow } from "../components/ui/SongRow";
import { CoverCard } from "../components/ui/CoverCard";
import { PaginationBar } from "../components/ui/PaginationBar";
import { BrowseFilterPanel, EMPTY_FILTERS } from "../components/ui/BrowseFilterPanel";
import type { BrowseFilters } from "../components/ui/BrowseFilterPanel";
import { EmptyState } from "../components/ui/EmptyState";
import { getApiErrorMessage } from "../shared/apiError";
import { FadeIn } from "../components/motion/FadeIn";
import { StaggerContainer, StaggerItem } from "../components/motion/StaggerContainer";

type BrowseTab = "music" | "albums" | "playlists";

const tabs: { key: BrowseTab; label: string; icon: React.ElementType }[] = [
  { key: "music", label: "音乐", icon: Music },
  { key: "albums", label: "专辑", icon: Disc },
  { key: "playlists", label: "歌单", icon: ListMusic },
];

const PAGE_SIZE = 20;

/** Tab 切换过渡方向 */
const tabDirections: Record<BrowseTab, number> = { music: -1, albums: 0, playlists: 1 };

export const BrowsePage = () => {
  const navigate = useNavigate();
  const { playMusicListItem } = usePlayMusic();
  const contentRef = useRef<HTMLDivElement>(null);

  const [activeTab, setActiveTab] = useState<BrowseTab>("music");
  const [prevTab, setPrevTab] = useState<BrowseTab>("music");

  // 各 tab 独立状态
  const [musicFilters, setMusicFilters] = useState<BrowseFilters>(EMPTY_FILTERS);
  const [albumFilters, setAlbumFilters] = useState<BrowseFilters>(EMPTY_FILTERS);
  const [playlistFilters, setPlaylistFilters] = useState<BrowseFilters>(EMPTY_FILTERS);

  const [musicPage, setMusicPage] = useState(0);
  const [albumPage, setAlbumPage] = useState(0);
  const [playlistPage, setPlaylistPage] = useState(0);

  const [musicItems, setMusicItems] = useState<MusicListItem[]>([]);
  const [albumItems, setAlbumItems] = useState<AlbumListItem[]>([]);
  const [playlistItems, setPlaylistItems] = useState<PlaylistListItem[]>([]);

  const [musicTotal, setMusicTotal] = useState(0);
  const [albumTotal, setAlbumTotal] = useState(0);
  const [playlistTotal, setPlaylistTotal] = useState(0);

  const [loading, setLoading] = useState(false);
  const [initialized, setInitialized] = useState<Set<BrowseTab>>(new Set());

  // 当前活跃状态
  const filters = activeTab === "music" ? musicFilters : activeTab === "albums" ? albumFilters : playlistFilters;
  const setFilters = activeTab === "music" ? setMusicFilters : activeTab === "albums" ? setAlbumFilters : setPlaylistFilters;
  const page = activeTab === "music" ? musicPage : activeTab === "albums" ? albumPage : playlistPage;
  const setPage = activeTab === "music" ? setMusicPage : activeTab === "albums" ? setAlbumPage : setPlaylistPage;

  // 首屏自动加载
  useEffect(() => {
    if (!initialized.has(activeTab)) {
      fetchTab(activeTab, filters, 0);
      setInitialized((prev) => new Set(prev).add(activeTab));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  const fetchTab = useCallback(
    async (tab: BrowseTab, f: BrowseFilters, p: number) => {
      setLoading(true);
      try {
        const baseParams: Record<string, unknown> = { limit: PAGE_SIZE, offset: p * PAGE_SIZE };
        if (f.q) baseParams.q = f.q;
        if (f.emotion_tag_ids.length === 1) baseParams.emotion_tag_id = f.emotion_tag_ids[0];
        if (f.interest_tag_ids.length === 1) baseParams.interest_tag_id = f.interest_tag_ids[0];

        if (tab === "music") {
          if (f.style_id != null) baseParams.style_id = f.style_id;
          if (f.language_id != null) baseParams.language_id = f.language_id;
          if (f.instrument_ids.length === 1) baseParams.instrument_id = f.instrument_ids[0];
          if (f.release_date_from) baseParams.release_date_from = f.release_date_from;
          if (f.release_date_to) baseParams.release_date_to = f.release_date_to;
          const res = await musicApi.listMusic(baseParams as Parameters<typeof musicApi.listMusic>[0]);
          setMusicItems(res.items);
          setMusicTotal(res.total);
        } else if (tab === "albums") {
          const res = await albumApi.listAlbums(baseParams as Parameters<typeof albumApi.listAlbums>[0]);
          setAlbumItems(res.items);
          setAlbumTotal(res.total);
        } else {
          const res = await playlistApi.searchPlaylists(baseParams as Parameters<typeof playlistApi.searchPlaylists>[0]);
          setPlaylistItems(res.items);
          setPlaylistTotal(res.total);
        }
      } catch (err) {
        toast.error(getApiErrorMessage(err, "加载失败"));
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  const handleApply = () => {
    setPage(0);
    fetchTab(activeTab, filters, 0);
  };

  const handleReset = () => {
    const empty = { ...EMPTY_FILTERS };
    setFilters(empty);
    setPage(0);
    fetchTab(activeTab, empty, 0);
  };

  const handlePageChange = (p: number) => {
    setPage(p);
    fetchTab(activeTab, filters, p);
  };

  const handleTabChange = (tab: BrowseTab) => {
    setPrevTab(activeTab);
    setActiveTab(tab);
  };

  const currentItems = activeTab === "music" ? musicItems : activeTab === "albums" ? albumItems : playlistItems;
  const currentTotal = activeTab === "music" ? musicTotal : activeTab === "albums" ? albumTotal : playlistTotal;
  const totalPages = Math.max(1, Math.ceil(currentTotal / PAGE_SIZE));
  const hasResults = currentItems.length > 0;
  const dir = tabDirections[activeTab] > tabDirections[prevTab] ? 1 : -1;

  return (
    <div className="browse-page">
      {/* 页面头部 */}
      <FadeIn>
        <div className="browse-page-header">
          <div className="browse-page-title-row">
            <h1 className="browse-page-title">
              <Sparkles size={20} style={{ color: "var(--color-brand-coral)" }} />
              详细分类
            </h1>
            {currentTotal > 0 && (
              <span className="browse-page-count">
                共 {currentTotal.toLocaleString()} 条
              </span>
            )}
          </div>

          {/* Tab 切换 */}
          <div className="category-tabs">
            {tabs.map((tab) => (
              <motion.button
                key={tab.key}
                className={`category-tab${activeTab === tab.key ? " active" : ""}`}
                onClick={() => handleTabChange(tab.key)}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                type="button"
              >
                <tab.icon size={14} />
                {tab.label}
              </motion.button>
            ))}
          </div>
        </div>
      </FadeIn>

      {/* 筛选栏 */}
      <FadeIn delay={0.08}>
        <BrowseFilterPanel
          tab={activeTab}
          filters={filters}
          onFiltersChange={setFilters}
          onApply={handleApply}
          onReset={handleReset}
          loading={loading}
        />
      </FadeIn>

      {/* 内容区域 */}
      <div ref={contentRef} className="browse-content">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, x: dir * 24 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: dir * -24 }}
            transition={{ duration: 0.25, ease: [0.25, 0.1, 0.25, 1] }}
          >
            {loading && !hasResults ? (
              <div className="browse-loading">
                <motion.div
                  className="browse-loading-spinner"
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
                />
                <span>加载中...</span>
              </div>
            ) : !hasResults ? (
              <FadeIn>
                <EmptyState
                  icon={activeTab === "music" ? Music : activeTab === "albums" ? Disc : ListMusic}
                  title={
                    activeTab === "music"
                      ? "没有找到匹配的音乐"
                      : activeTab === "albums"
                        ? "没有找到匹配的专辑"
                        : "没有找到匹配的歌单"
                  }
                  description="试试调整筛选条件或换个关键词"
                  accent={activeTab === "music" ? "peach" : activeTab === "albums" ? "lavender" : "mint"}
                />
              </FadeIn>
            ) : activeTab === "music" ? (
              <StaggerContainer staggerDelay={0.02}>
                {(currentItems as MusicListItem[]).map((song, i) => (
                  <StaggerItem key={song.id}>
                    <SongRow
                      index={i}
                      showIndex
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
            ) : (
              <StaggerContainer className="playlist-rail" staggerDelay={0.03}>
                {activeTab === "albums"
                  ? (currentItems as AlbumListItem[]).map((album) => (
                      <StaggerItem key={album.id}>
                        <motion.div whileHover={{ y: -4 }} transition={{ duration: 0.25 }}>
                          <CoverCard
                            id={album.id}
                            title={album.title}
                            subtitle={`${album.play_count.toLocaleString()} 次播放`}
                            coverUrl={album.cover_icon_url ?? undefined}
                            onClick={() => navigate(`/album/${album.id}`)}
                          />
                        </motion.div>
                      </StaggerItem>
                    ))
                  : (currentItems as PlaylistListItem[]).map((pl) => (
                      <StaggerItem key={pl.id}>
                        <motion.div whileHover={{ y: -4 }} transition={{ duration: 0.25 }}>
                          <CoverCard
                            id={pl.id}
                            title={pl.title}
                            subtitle={pl.user?.nickname ?? "未知用户"}
                            coverUrl={pl.cover_icon_url ?? undefined}
                            onClick={() => navigate(`/playlist/${pl.id}`)}
                          />
                        </motion.div>
                      </StaggerItem>
                    ))}
              </StaggerContainer>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* 分页 */}
      {hasResults && totalPages > 1 && (
        <FadeIn delay={0.2}>
          <PaginationBar
            page={page}
            totalPages={totalPages}
            onPageChange={handlePageChange}
            loading={loading}
            total={currentTotal}
            pageSize={PAGE_SIZE}
          />
        </FadeIn>
      )}
    </div>
  );
};
