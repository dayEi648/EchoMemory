import { toast } from "sonner";

import { musicApi } from "./api/instances";
import type { MusicListItem } from "./api/types";
import { usePlayerStore } from "./stores/playerStore";
import { toPlayerTrack, toPlayerTrackFromListItem } from "./utils";

/**
 * 统一「拉取音乐详情并独立播放」逻辑，供列表页复用。
 */
export function usePlayMusic() {
  const playStandalone = usePlayerStore((s) => s.playStandalone);

  const playMusicListItem = async (music: MusicListItem) => {
    try {
      const detail = await musicApi.getMusicDetail(music.id);
      if (detail.file_url) {
        await playStandalone(toPlayerTrackFromListItem(music, detail.file_url));
      } else {
        toast.error("该歌曲暂不可播放");
      }
    } catch {
      toast.error("加载歌曲失败");
    }
  };

  const playMusicById = async (musicId: number) => {
    try {
      const detail = await musicApi.getMusicDetail(musicId);
      if (detail.file_url) {
        await playStandalone(toPlayerTrack(detail));
      } else {
        toast.error("该歌曲暂不可播放");
      }
    } catch {
      toast.error("加载歌曲失败");
    }
  };

  return { playMusicListItem, playMusicById };
}
