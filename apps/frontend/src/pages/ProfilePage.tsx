import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Music2, UserCheck } from "lucide-react";
import { toast } from "sonner";
import { motion } from "framer-motion";

import { useAuthStore } from "../shared/stores/authStore";
import type { UserPublic } from "../shared/api/types";
import { Avatar } from "../components/ui/Avatar";
import { EmptyState } from "../components/ui/EmptyState";
import { FadeIn } from "../components/motion/FadeIn";

export const ProfilePage = () => {
  const { userId } = useParams<{ userId: string }>();
  const { api, user: currentUser } = useAuthStore();
  const [profile, setProfile] = useState<UserPublic | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!userId) return;
    const id = Number(userId);
    if (Number.isNaN(id)) {
      setLoading(false);
      return;
    }

    if (currentUser && currentUser.id === id) {
      setProfile(currentUser);
      setLoading(false);
      return;
    }

    api
      .getPublicUser(id)
      .then(setProfile)
      .catch((err) => {
        toast.error(err instanceof Error ? err.message : "加载用户资料失败");
      })
      .finally(() => setLoading(false));
  }, [userId, api, currentUser]);

  if (loading) {
    return (
      <FadeIn>
        <div className="empty-state">
          <p>加载中...</p>
        </div>
      </FadeIn>
    );
  }

  if (!profile) {
    return (
      <FadeIn>
        <EmptyState
          icon={UserCheck}
          title="用户不存在"
          description="该用户可能已被删除或你无权查看。"
        />
      </FadeIn>
    );
  }

  return (
    <div>
      <FadeIn>
        <motion.div
          className="profile-header"
          whileHover={{ boxShadow: "0 4px 16px rgba(0,0,0,0.04)" }}
          transition={{ duration: 0.25 }}
        >
          {profile.avatar_url ? (
            <img
              className="avatar-large"
              src={profile.avatar_url}
              alt={`${profile.nickname}的头像`}
            />
          ) : (
            <div className="avatar-large-fallback">
              {profile.nickname.slice(0, 1) || profile.username.slice(0, 1)}
            </div>
          )}
          <div className="profile-meta" style={{ flex: 1 }}>
            <h2>{profile.nickname}</h2>
            <div className="profile-handle">@{profile.username}</div>
            <div className="profile-stats">
              <motion.div className="stat" whileHover={{ scale: 1.05 }}>
                <div className="stat-value">Lv.{profile.level}</div>
                <div className="stat-label">等级</div>
              </motion.div>
              <motion.div className="stat" whileHover={{ scale: 1.05 }}>
                <div className="stat-value">{profile.exp}</div>
                <div className="stat-label">经验</div>
              </motion.div>
              <motion.div className="stat" whileHover={{ scale: 1.05 }}>
                <div className="stat-value">{profile.like_count}</div>
                <div className="stat-label">获赞</div>
              </motion.div>
            </div>
          </div>
        </motion.div>
      </FadeIn>

      {profile.bio && (
        <FadeIn delay={0.1}>
          <p
            style={{
              fontSize: 14,
              color: "var(--color-muted)",
              marginBottom: 20,
              lineHeight: 1.6,
            }}
          >
            {profile.bio}
          </p>
        </FadeIn>
      )}

      <FadeIn delay={0.15}>
        <section>
          <div className="section-header">
            <h3>
              <Music2 size={16} style={{ display: "inline", verticalAlign: "-2px" }} /> 公开歌单
            </h3>
          </div>
          <EmptyState
            icon={Music2}
            title="该用户暂无公开歌单"
            compact
          />
        </section>
      </FadeIn>
    </div>
  );
};
