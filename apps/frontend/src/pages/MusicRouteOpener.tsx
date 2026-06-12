import { useEffect } from "react";
import { Navigate, useParams } from "react-router-dom";

import { usePlayerViewStore } from "../shared/stores/playerViewStore";

/**
 * 兼容旧链接 /music/:musicId：打开全屏播放页并回到首页。
 */
export const MusicRouteOpener = () => {
  const { musicId } = useParams<{ musicId: string }>();
  const open = usePlayerViewStore((s) => s.open);

  useEffect(() => {
    const id = Number(musicId);
    if (!Number.isNaN(id) && id > 0) {
      open(id);
    }
  }, [musicId, open]);

  return <Navigate to="/" replace />;
};
