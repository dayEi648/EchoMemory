import { Clock } from "lucide-react";

import { EmptyState } from "../components/ui/EmptyState";
import { FadeIn } from "../components/motion/FadeIn";

export const HistoryPage = () => {
  return (
    <div>
      <FadeIn>
        <h1 className="page-title">最近播放</h1>
      </FadeIn>

      <FadeIn delay={0.1}>
        <EmptyState
          icon={Clock}
          title="暂无播放记录"
          description="你播放过的歌曲会按时间顺序显示在这里，方便你随时继续聆听。"
        />
      </FadeIn>
    </div>
  );
};
