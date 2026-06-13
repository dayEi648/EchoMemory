import { useEffect, useState } from "react";
import { Radio, Play } from "lucide-react";
import { toast } from "sonner";

import { recommendationApi } from "../shared/api/instances";
import type { MusicListItem } from "../shared/api/types";
import { formatAuthors } from "../shared/utils";
import { usePlayMusic } from "../shared/usePlayMusic";
import { PageTitle } from "../components/ui/PageTitle";
import { SongRow } from "../components/ui/SongRow";
import { EmptyState } from "../components/ui/EmptyState";
import { FadeIn } from "../components/motion/FadeIn";
import { StaggerContainer, StaggerItem } from "../components/motion/StaggerContainer";

export const RadarPage = () => {
  const { playMusicListItem } = usePlayMusic();
  const [songs, setSongs] = useState<MusicListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [dateLabel, setDateLabel] = useState("");

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await recommendationApi.getRadarRecommendations();
        if (cancelled) return;
        setSongs(res.items);
        setDateLabel(new Date().toLocaleDateString("zh-CN"));
      } catch {
        if (!cancelled) toast.error("加载私人雷达失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const handlePlayAll = () => {
    if (songs.length === 0) return;
    void playMusicListItem(songs[0]);
  };

  return (
    <div className="page-content">
      <FadeIn>
        <PageTitle icon={Radio} iconAccent="teal">
          私人雷达
        </PageTitle>
        <div className="daily-subtitle">
          {dateLabel ? `${dateLabel} · 从你的收藏与口味中探索` : "从你的收藏与口味中探索"}
        </div>
      </FadeIn>

      <FadeIn delay={0.1}>
        {songs.length > 0 && (
          <button
            type="button"
            className="daily-play-all"
            onClick={handlePlayAll}
          >
            <Play size={16} fill="currentColor" />
            播放全部
          </button>
        )}
      </FadeIn>

      <FadeIn delay={0.15}>
        {loading ? (
          <div className="empty-state" style={{ padding: "32px 20px" }}>
            <p>加载中...</p>
          </div>
        ) : songs.length === 0 ? (
          <EmptyState
            icon={Radio}
            title="暂无雷达内容"
            description="多去听听歌、收藏喜欢的音乐，雷达会越来越好用"
            accent="teal"
          />
        ) : (
          <StaggerContainer staggerDelay={0.03}>
            {songs.map((song, i) => (
              <StaggerItem key={song.id}>
                <SongRow
                  index={i}
                  showIndex
                  name={song.title}
                  artist={formatAuthors(song.authors)}
                  showAlbum={false}
                  musicId={song.id}
                  coverUrl={song.cover_icon_url ?? undefined}
                  isCollected={song.is_collected_by_me}
                  onPlay={() => playMusicListItem(song)}
                />
              </StaggerItem>
            ))}
          </StaggerContainer>
        )}
      </FadeIn>
    </div>
  );
};
