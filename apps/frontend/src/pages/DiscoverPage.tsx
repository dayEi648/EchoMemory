import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Sparkles, TrendingUp, Flame, Music, Disc, Radio, Compass, Zap } from "lucide-react";
import { toast } from "sonner";

import { musicApi, albumApi } from "../shared/api/instances";
import type { MusicListItem, AlbumListItem } from "../shared/api/types";
import { formatAuthors, formatAlbumTitle } from "../shared/utils";
import { usePlayMusic } from "../shared/usePlayMusic";
import { HeroCarousel } from "../components/ui/HeroCarousel";
import type { CarouselSlide } from "../components/ui/HeroCarousel";
import { ChartColumn } from "../components/ui/ChartColumn";
import { CoverCard } from "../components/ui/CoverCard";
import { SongRow } from "../components/ui/SongRow";
import { SectionHeader } from "../components/ui/SectionHeader";
import { StaggerContainer, StaggerItem } from "../components/motion/StaggerContainer";
import { FadeIn } from "../components/motion/FadeIn";
import { EmptyState } from "../components/ui/EmptyState";

const CAROUSEL_SLIDES: CarouselSlide[] = [
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

/** 每日推荐 / 私人入口 占位卡片数据 */
const DAILY_CARDS = [
  {
    key: "daily",
    icon: Sparkles,
    title: "每日推荐",
    subtitle: "根据你的口味生成",
    gradient: "linear-gradient(135deg, #ff4d8b, #ff7aa8)",
    iconAccent: "pink" as const,
  },
  {
    key: "radar",
    icon: Radio,
    title: "私人雷达",
    subtitle: "探索你可能喜欢的新歌",
    gradient: "linear-gradient(135deg, #1a3a3a, #2d5a5a)",
    iconAccent: "teal" as const,
  },
  {
    key: "roam",
    icon: Compass,
    title: "私人漫游",
    subtitle: "随机发现更多惊喜",
    gradient: "linear-gradient(135deg, #b8a4ed, #d4c8f5)",
    iconAccent: "lavender" as const,
  },
] as const;

export const DiscoverPage = () => {
  const navigate = useNavigate();
  const { playMusicListItem } = usePlayMusic();

  const [hotSongs, setHotSongs] = useState<MusicListItem[]>([]);
  const [newSongs, setNewSongs] = useState<MusicListItem[]>([]);
  const [albums, setAlbums] = useState<AlbumListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [hotRes, newRes, albumRes] = await Promise.all([
          musicApi.listMusic({ limit: 5 }), // 热歌：用默认排序
          musicApi.listMusic({ limit: 8 }), // 新歌
          albumApi.listAlbums({ limit: 6 }),
        ]);
        setHotSongs(hotRes.items ?? []);
        setNewSongs(newRes.items ?? []);
        setAlbums(albumRes.items ?? []);
      } catch {
        toast.error("加载内容失败，请稍后重试");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <div>
      {/* ====== 1. Hero Carousel ====== */}
      <FadeIn>
        <HeroCarousel slides={CAROUSEL_SLIDES} interval={5000} />
      </FadeIn>

      {/* ====== 2. 每日推荐 + 私人入口 ====== */}
      <FadeIn delay={0.1}>
        <section className="discover-daily-section">
          <div className="discover-daily-grid">
            {DAILY_CARDS.map((card) => (
              <motion.div
                key={card.key}
                className="discover-daily-card"
                style={{ background: card.gradient }}
                whileHover={{ y: -4, scale: 1.02 }}
                transition={{ duration: 0.25 }}
              >
                <div className="discover-daily-card-icon">
                  <card.icon size={24} />
                </div>
                <div className="discover-daily-card-text">
                  <div className="discover-daily-card-title">{card.title}</div>
                  <div className="discover-daily-card-subtitle">{card.subtitle}</div>
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
              <button className="section-link" onClick={() => navigate("/browse?tab=albums")} type="button">
                查看更多 →
              </button>
            }
          />
          {albums.length > 0 ? (
            <StaggerContainer className="playlist-rail">
              {albums.map((album) => (
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
            <EmptyState icon={Disc} title="暂无推荐专辑" accent="lavender" compact />
          )}
        </section>
      </FadeIn>

      {/* ====== 4. 热门榜单（三列） ====== */}
      <FadeIn delay={0.2}>
        <section className="discover-section">
          <SectionHeader
            title={
              <>
                <TrendingUp size={18} style={{ display: "inline", verticalAlign: "-3px", marginRight: 6 }} />
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
              icon={Sparkles}
              accent="lavender"
              songs={hotSongs.slice(0, 5)}
              loading={loading}
              onPlay={(song) => playMusicListItem(song)}
            />
          </div>
        </section>
      </FadeIn>

      {/* ====== 5. 最新上架 ====== */}
      <FadeIn delay={0.25}>
        <section className="discover-section">
          <SectionHeader
            title="最新上架"
            action={
              <button className="section-link" onClick={() => navigate("/browse?tab=music")} type="button">
                查看全部 →
              </button>
            }
          />
          {loading ? (
            <div className="empty-state" style={{ padding: "32px 20px" }}>
              <p>加载中...</p>
            </div>
          ) : newSongs.length === 0 ? (
            <EmptyState icon={Music} title="暂无新歌上架" accent="peach" compact />
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
