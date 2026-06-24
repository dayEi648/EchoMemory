import { Bell, MessageCircle, UserPlus, Heart, MessageSquare, ShieldAlert } from "lucide-react";

/** 通知类型 → 图标映射 */
export const NOTIFICATION_ICON_MAP: Record<number, typeof Bell> = {
  0: UserPlus,
  1: MessageCircle,
  2: Heart,
  3: Heart,
  4: MessageSquare,
  5: ShieldAlert,
};

/** 通知类型 → 文案映射 */
export const NOTIFICATION_LABEL_MAP: Record<number, string> = {
  0: "关注了你",
  1: "回复了你的评论",
  2: "赞了你的评论",
  3: "赞了你的动态",
  4: "评论了你的动态",
  5: "审核处理了你发布的内容",
};

/** 格式化未读数字：>=10 显示 "9+" */
export function formatBadge(n: number): string {
  if (n >= 10) return "9+";
  return String(n);
}
