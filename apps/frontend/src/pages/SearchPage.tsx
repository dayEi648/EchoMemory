import { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Music, ListMusic, Disc, User, Search } from "lucide-react";
import { toast } from "sonner";
import { motion } from "framer-motion";

import { useAuthStore } from "../shared/stores/authStore";
import type { UserSearchItem } from "../shared/api/types";
import { Avatar } from "../components/ui/Avatar";
import { EmptyState } from "../components/ui/EmptyState";
import { FadeIn } from "../components/motion/FadeIn";
import { StaggerContainer, StaggerItem } from "../components/motion/StaggerContainer";

const tabs = [
  { key: "all", label: "综合", icon: Search },
  { key: "songs", label: "单曲", icon: Music },
  { key: "playlists", label: "歌单", icon: ListMusic },
  { key: "albums", label: "专辑", icon: Disc },
  { key: "users", label: "用户", icon: User },
];

export const SearchPage = () => {
  const [searchParams] = useSearchParams();
  const query = searchParams.get("q") ?? "";
  const [activeTab, setActiveTab] = useState("all");
  const { api } = useAuthStore();
  const navigate = useNavigate();
  const [userResults, setUserResults] = useState<UserSearchItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!query.trim()) return;
    setLoading(true);
    api
      .searchUsers(query.trim())
      .then(setUserResults)
      .catch((err) => {
        toast.error(err instanceof Error ? err.message : "搜索失败");
      })
      .finally(() => setLoading(false));
  }, [query, api]);

  if (!query.trim()) {
    return (
      <FadeIn>
        <EmptyState
          icon={Search}
          title="请输入搜索关键词"
          description="在顶部搜索框输入内容，即可搜索歌曲、歌单、专辑和用户。"
        />
      </FadeIn>
    );
  }

  return (
    <div>
      <FadeIn>
        <h1 className="page-title">「{query}」的搜索结果</h1>
      </FadeIn>

      <FadeIn delay={0.06}>
        <div className="search-tabs">
          {tabs.map((tab) => (
            <motion.button
              key={tab.key}
              className={`search-tab ${activeTab === tab.key ? "active" : ""}`}
              onClick={() => setActiveTab(tab.key)}
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              type="button"
            >
              <tab.icon size={14} />
              {tab.label}
            </motion.button>
          ))}
        </div>
      </FadeIn>

      {loading ? (
        <FadeIn delay={0.12}>
          <div className="empty-state">
            <p>搜索中...</p>
          </div>
        </FadeIn>
      ) : (
        <>
          {(activeTab === "all" || activeTab === "songs") && (
            <section style={{ marginBottom: 28 }}>
              <FadeIn delay={0.1}>
                <div className="section-header">
                  <h3 className="page-section-title">单曲</h3>
                </div>
              </FadeIn>
              <FadeIn delay={0.15}>
                <EmptyState
                  icon={Music}
                  title="音乐搜索功能即将上线"
                  compact
                />
              </FadeIn>
            </section>
          )}

          {(activeTab === "all" || activeTab === "playlists") && (
            <section style={{ marginBottom: 28 }}>
              <FadeIn delay={0.1}>
                <div className="section-header">
                  <h3 className="page-section-title">歌单</h3>
                </div>
              </FadeIn>
              <FadeIn delay={0.15}>
                <EmptyState
                  icon={ListMusic}
                  title="歌单搜索功能即将上线"
                  compact
                />
              </FadeIn>
            </section>
          )}

          {(activeTab === "all" || activeTab === "albums") && (
            <section style={{ marginBottom: 28 }}>
              <FadeIn delay={0.1}>
                <div className="section-header">
                  <h3 className="page-section-title">专辑</h3>
                </div>
              </FadeIn>
              <FadeIn delay={0.15}>
                <EmptyState
                  icon={Disc}
                  title="专辑搜索功能即将上线"
                  compact
                />
              </FadeIn>
            </section>
          )}

          {(activeTab === "all" || activeTab === "users") && userResults.length > 0 && (
            <section style={{ marginBottom: 28 }}>
              <FadeIn delay={0.1}>
                <div className="section-header">
                  <h3 className="page-section-title">用户</h3>
                  {activeTab === "all" && userResults.length > 6 && (
                    <button
                      className="ghost-button"
                      onClick={() => setActiveTab("users")}
                      style={{ fontSize: 13 }}
                    >
                      查看更多
                    </button>
                  )}
                </div>
              </FadeIn>
              <StaggerContainer
                staggerDelay={0.05}
                className={`user-search-grid ${activeTab === "all" ? "compact" : "full"}`}
              >
                {(activeTab === "all" ? userResults.slice(0, 6) : userResults).map((item) => (
                  <StaggerItem key={item.id}>
                    <motion.div
                      className="user-search-card"
                      whileHover={{
                        y: -2,
                        boxShadow: "0 4px 12px rgba(0,0,0,0.05)",
                      }}
                      transition={{ duration: 0.2 }}
                      onClick={() => navigate(`/profile/${item.id}`)}
                    >
                      <Avatar user={item} size="xl" />
                      <div className="user-search-card-nickname">
                        {item.nickname}
                      </div>
                      {item.bio && (
                        <div className="user-search-card-bio" title={item.bio}>
                          {item.bio}
                        </div>
                      )}
                      <div className="user-search-card-meta">
                        @{item.username} · Lv.{item.level}
                      </div>
                    </motion.div>
                  </StaggerItem>
                ))}
              </StaggerContainer>
            </section>
          )}

          {activeTab === "users" && userResults.length === 0 && (
            <FadeIn delay={0.1}>
              <EmptyState icon={User} title="未找到相关用户" />
            </FadeIn>
          )}
        </>
      )}
    </div>
  );
};
