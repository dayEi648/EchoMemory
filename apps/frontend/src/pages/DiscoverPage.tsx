import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Sparkles,
  TrendingUp,
  Flame,
  Music,
  Disc,
  Radio,
  Compass,
  Zap,
  Trophy,
} from "lucide-react";
import { toast } from "sonner";
import { getApiErrorMessage } from "../shared/apiError";

import {
  musicApi,
  carouselApi,
  recommendationApi,
} from "../shared/api/instances";
import type {
  MusicListItem,
  AlbumListItem,
  PlaylistListItem,
} from "../shared/api/types";
import type { CarouselItem } from "../shared/api/carouselApi";
import { formatAuthors, formatAlbumTitle } from "../shared/utils";
import { usePlayMusic } from "../shared/usePlayMusic";
import { HeroCarousel } from "../components/ui/HeroCarousel";
import type { CarouselSlide } from "../components/ui/HeroCarousel";
import { ChartColumn } from "../components/ui/ChartColumn";
import { CoverCard } from "../components/ui/CoverCard";
import { SongRow } from "../components/ui/SongRow";
import { SectionHeader } from "../components/ui/SectionHeader";
import {
  StaggerContainer,
  StaggerItem,
} from "../components/motion/StaggerContainer";
import { FadeIn } from "../components/motion/FadeIn";
import { EmptyState } from "../components/ui/EmptyState";

/** 无轮播数据时的占位 slides */
const FALLBACK_SLIDES: CarouselSlide[] = [
  {
    title: "发现你的音乐记忆",
    subtitle: "EchoMemory 用 AI 理解你的品味，为你推荐专属好音乐",
    gradient: "linear-gradient(135deg, #1a3a3a 0%, #2d5a5a 60%, #3a6a6a 100%)",
  },
  {
    title: "新歌推荐 · 每日更新",
    subtitle: "精选最新上架的好音乐，不错过每一首心动",
    gradient: "linear-gradient(135deg, #4a1a3a 0%, #7a2d5a 60%, #9a4a7a 100%)",
  },
  {
    title: "热门榜单 · 实时排行",
    subtitle: "最受欢迎的歌曲、专辑和歌单，大家都在听什么？",
    gradient: "linear-gradient(135deg, #1a2a4a 0%, #2d3a7a 60%, #4a5a9a 100%)",
  },
];

/** 将 API 返回的 CarouselItem 转为轮播 slide */
function carouselItemToSlide(
  item: CarouselItem,
  navigate: (path: string) => void,
  playMusicById: (id: number) => void,
): CarouselSlide {
  const onClick =
    item.type === "music"
      ? () => playMusicById(item.target_id)
      : () => navigate(`/album/${item.target_id}`);
  return {
    title: item.title,
    subtitle: item.description,
    gradient: "",
    imageUrl: item.image_url,
    onClick,
  };
}

/** 每日推荐 / 私人入口 卡片数据 */
const DAILY_CARDS = [
  {
    key: "daily",
    icon: Sparkles,
    title: "每日推荐",
    subtitle: "根据你的口味生成",
    gradient: "linear-gradient(135deg, #ff4d8b, #ff7aa8)",
    iconAccent: "pink" as const,
    path: "/daily-recommend",
  },
  {
    key: "radar",
    icon: Radio,
    title: "私人雷达",
    subtitle: "探索你可能喜欢的新歌",
    gradient: "linear-gradient(135deg, #1a3a3a, #2d5a5a)",
    iconAccent: "teal" as const,
    path: "/personal-radar",
  },
  {
    key: "roam",
    icon: Compass,
    title: "私人漫游",
    subtitle: "随机发现更多惊喜",
    gradient: "linear-gradient(135deg, #b8a4ed, #d4c8f5)",
    iconAccent: "lavender" as const,
    path: "/personal-roam",
  },
] as const;

function settledValue<T>(result: PromiseSettledResult<T>, fallback: T): T {
  return result.status === "fulfilled" ? result.value : fallback;
}

export const DiscoverPage = () => {
  const navigate = useNavigate();
  const { playMusicListItem, playMusicById } = usePlayMusic();

  const [hotSongs, setHotSongs] = useState<MusicListItem[]>([]);
  const [newSongs, setNewSongs] = useState<MusicListItem[]>([]);
  const [recommendChart, setRecommendChart] = useState<MusicListItem[]>([]);
  const [recommendedPlaylists, setRecommendedPlaylists] = useState<
    PlaylistListItem[]
  >([]);
  const [recommendedAlbums, setRecommendedAlbums] = useState<AlbumListItem[]>(
    [],
  );
  const [loading, setLoading] = useState(true);
  const [carouselSlides, setCarouselSlides] =
    useState<CarouselSlide[]>(FALLBACK_SLIDES);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const thirtyDaysAgo = new Date();
        thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
        const dateFrom = thirtyDaysAgo.toISOString().slice(0, 10);

        const results = await Promise.allSettled([
          musicApi.listMusic({ limit: 5, sort_by: "hot" }),
          musicApi.listMusic({
            limit: 8,
            sort_by: "hot",
            release_date_from: dateFrom,
          }),
          recommendationApi.getRecommendedPlaylists({ limit: 6 }),
          recommendationApi.getRecommendedAlbums({ limit: 6 }),
          recommendationApi.getRecommendationChart({ limit: 5 }),
          carouselApi.listCarousel(),
        ]);

        if (cancelled) return;

        const hasFailure = results.some((r) => r.status === "rejected");
        if (hasFailure) {
          toast.error("部分内容加载失败，请稍后重试");
        }

        const [
          hotResult,
          newResult,
          playlistResult,
          albumResult,
          chartResult,
          carouselResult,
        ] = results;

        const hotRes = settledValue(hotResult, { items: [] as MusicListItem[], total: 0 });
        const newRes = settledValue(newResult, { items: [] as MusicListItem[], total: 0 });
        const playlistRes = settledValue(playlistResult, { items: [] as PlaylistListItem[], total: 0 });
        const albumRes = settledValue(albumResult, { items: [] as AlbumListItem[], total: 0 });
        const chartRes = settledValue(chartResult, { items: [] as MusicListItem[] });
        const carouselRes = settledValue(carouselResult, [] as CarouselItem[]);

        setHotSongs(hotRes.items);
        setNewSongs(newRes.items);
        setRecommendedPlaylists(playlistRes.items);
        setRecommendedAlbums(albumRes.items);
        setRecommendChart(chartRes.items);

        if (carouselRes.length > 0) {
          setCarouselSlides(
            carouselRes.map((item) =>
              carouselItemToSlide(
                item,
                (path) => navigate(path),
                (id) => playMusicById(id),
              ),
            ),
          );
        }
      } catch (err) {
        if (!cancelled) toast.error(getApiErrorMessage(err, "加载内容失败，请稍后重试"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
    // playMusicById 来自 usePlayMusic，仅在轮播图点击中使用；避免每次渲染触发重新加载
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navigate]);

  return (
    <div>
      {/* ====== 1. Hero Carousel ====== */}
      <FadeIn>
        <HeroCarousel slides={carouselSlides} interval={5000} />
      </FadeIn>

      {/* ====== 2. 每日推荐 + 私人入口 ====== */}
      <FadeIn delay={0.1}>
        <section className="discover-daily-section">
          <div className="discover-daily-grid">
            {DAILY_CARDS.map((card) => (
              <motion.div
                key={card.key}
                className="discover-daily-card"
                style={{
                  background: card.gradient,
                  cursor: card.path ? "pointer" : "default",
                }}
                whileHover={card.path ? { y: -4, scale: 1.02 } : undefined}
                transition={{ duration: 0.25 }}
                onClick={card.path ? () => navigate(card.path) : undefined}
              >
                <div className="discover-daily-card-icon">
                  <card.icon size={24} />
                </div>
                <div className="discover-daily-card-text">
                  <div className="discover-daily-card-title">{card.title}</div>
                  <div className="discover-daily-card-subtitle">
                    {card.subtitle}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </section>
      </FadeIn>

      {/* ====== 3. 推荐歌单 ====== */}
      <FadeIn delay={0.15}>
        <section className="discover-section">
          <SectionHeader
            title="推荐歌单"
            action={
              <button
                className="section-link"
                onClick={() => navigate("/browse?tab=playlists")}
                type="button"
              >
                查看更多 →
              </button>
            }
          />
          {recommendedPlaylists.length > 0 ? (
            <StaggerContainer className="playlist-rail">
              {recommendedPlaylists.map((playlist) => (
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
          ) : (
            <EmptyState
              icon={Music}
              title="暂无推荐歌单"
              accent="lavender"
              compact
            />
          )}
        </section>
      </FadeIn>

      {/* ====== 4. 推荐专辑 ====== */}
      <FadeIn delay={0.18}>
        <section className="discover-section">
          <SectionHeader
            title="推荐专辑"
            action={
              <button
                className="section-link"
                onClick={() => navigate("/browse?tab=albums")}
                type="button"
              >
                查看更多 →
              </button>
            }
          />
          {recommendedAlbums.length > 0 ? (
            <StaggerContainer className="playlist-rail">
              {recommendedAlbums.map((album) => (
                <StaggerItem key={album.id}>
                  <CoverCard
                    id={album.id}
                    title={album.title}
                    subtitle={`${album.play_count.toLocaleString()} 次播放`}
                    coverUrl={album.cover_icon_url ?? undefined}
                    onClick={() => navigate(`/album/${album.id}`)}
                  />
                </StaggerItem>
              ))}
            </StaggerContainer>
          ) : (
            <EmptyState
              icon={Disc}
              title="暂无推荐专辑"
              accent="peach"
              compact
            />
          )}
        </section>
      </FadeIn>

      {/* ====== 5. 热门榜单（三列） ====== */}
      <FadeIn delay={0.2}>
        <section className="discover-section">
          <SectionHeader
            title={
              <>
                <TrendingUp
                  size={18}
                  style={{
                    display: "inline",
                    verticalAlign: "-3px",
                    marginRight: 6,
                  }}
                />
                热门榜单
              </>
            }
          />
          <div className="discover-chart-grid">
            <ChartColumn
              title="热歌榜"
              icon={Flame}
              accent="coral"
              songs={hotSongs}
              loading={loading}
              onPlay={(song) => playMusicListItem(song)}
              onViewAll={() => navigate("/browse?tab=music")}
            />
            <ChartColumn
              title="新歌榜"
              icon={Zap}
              accent="teal"
              songs={newSongs}
              loading={loading}
              onPlay={(song) => playMusicListItem(song)}
              onViewAll={() => navigate("/browse?tab=music")}
            />
            <ChartColumn
              title="推荐榜"
              icon={Trophy}
              accent="ochre"
              songs={recommendChart}
              loading={loading}
              onPlay={(song) => playMusicListItem(song)}
              onViewAll={() => navigate("/browse?tab=music")}
            />
          </div>
        </section>
      </FadeIn>

      {/* ====== 6. 最新上架 ====== */}
      <FadeIn delay={0.25}>
        <section className="discover-section">
          <SectionHeader
            title="最新上架"
            action={
              <button
                className="section-link"
                onClick={() => navigate("/browse?tab=music")}
                type="button"
              >
                查看全部 →
              </button>
            }
          />
          {loading ? (
            <div className="empty-state" style={{ padding: "32px 20px" }}>
              <p>加载中...</p>
            </div>
          ) : newSongs.length === 0 ? (
            <EmptyState
              icon={Music}
              title="暂无新歌上架"
              accent="peach"
              compact
            />
          ) : (
            <StaggerContainer staggerDelay={0.03}>
              {newSongs.map((song, i) => (
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
          )}
        </section>
      </FadeIn>
    </div>
  );
};
