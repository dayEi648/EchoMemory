import { useEffect, useState } from "react";
import { Sparkles, Play } from "lucide-react";
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

export const DailyRecommendPage = () => {
  const { playMusicListItem } = usePlayMusic();
  const [songs, setSongs] = useState<MusicListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [dateLabel, setDateLabel] = useState("");

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await recommendationApi.getDailyRecommendations();
        if (cancelled) return;
        setSongs(res.items);
        setDateLabel(new Date().toLocaleDateString("zh-CN"));
      } catch {
        if (!cancelled) toast.error("加载每日推荐失败");
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
        <PageTitle icon={Sparkles} iconAccent="pink">
          每日推荐
        </PageTitle>
        <div className="daily-subtitle">
          {dateLabel ? `${dateLabel} · 根据你的口味推荐` : "根据你的口味推荐"}
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
            icon={Sparkles}
            title="暂无推荐"
            description="先去听几首歌，我们明天再为你准备推荐"
            accent="pink"
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
