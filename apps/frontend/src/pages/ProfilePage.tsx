import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Music2, UserCheck, UserPlus, UserMinus, Disc, Clock, MessageCircle,
  LayoutList, ArrowRight, ListMusic, Heart,
} from "lucide-react";
import { toast } from "sonner";
import { motion } from "framer-motion";

import { useAuthStore } from "../shared/stores/authStore";
import { playlistApi, collectionApi, playHistoryApi } from "../shared/api/instances";
import { usePlayMusic } from "../shared/usePlayMusic";
import type { UserPublic, PlaylistListItem, AlbumCollectionItem, PlayHistoryItem } from "../shared/api/types";
import { Avatar } from "../components/ui/Avatar";
import { EmptyState } from "../components/ui/EmptyState";
import { FadeIn } from "../components/motion/FadeIn";
import { StaggerContainer, StaggerItem } from "../components/motion/StaggerContainer";
import { CoverCard } from "../components/ui/CoverCard";
import { SongRow } from "../components/ui/SongRow";

export const ProfilePage = () => {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const { api, user: currentUser } = useAuthStore();
  const { playMusicById } = usePlayMusic();
  const [profile, setProfile] = useState<UserPublic | null>(null);
  const [loading, setLoading] = useState(true);
  const [following, setFollowing] = useState(false);

  // Dashboard data (own profile only)
  const [myPlaylists, setMyPlaylists] = useState<PlaylistListItem[]>([]);
  const [myAlbums, setMyAlbums] = useState<AlbumCollectionItem[]>([]);
  const [myHistory, setMyHistory] = useState<PlayHistoryItem[]>([]);
  const [dashLoading, setDashLoading] = useState(false);
  const [publicPlaylists, setPublicPlaylists] = useState<PlaylistListItem[]>([]);
  const [publicPlaylistsLoading, setPublicPlaylistsLoading] = useState(false);

  const isOwnProfile = currentUser && userId && Number(userId) === currentUser.id;

  useEffect(() => {
    if (!userId) return;
    const id = Number(userId);
    if (Number.isNaN(id)) { setLoading(false); return; }

    if (currentUser && currentUser.id === id) {
      setProfile(currentUser);
      setLoading(false);
      return;
    }
    api.getPublicUser(id).then((data) => {
      setProfile(data);
      setFollowing(data.is_followed_by_me ?? false);
    }).catch((err) => {
      toast.error(err instanceof Error ? err.message : "加载用户资料失败");
    }).finally(() => setLoading(false));
  }, [userId, api, currentUser]);

  // Load dashboard data for own profile
  useEffect(() => {
    if (!isOwnProfile) return;
    setDashLoading(true);
    Promise.all([
      playlistApi.listPlaylists({ limit: 4 }),
      collectionApi.listAlbumCollections({ limit: 4 }),
      playHistoryApi.listPlayHistory({ limit: 5 }),
    ]).then(([pl, al, hi]) => {
      setMyPlaylists(pl.items);
      setMyAlbums(al.items);
      setMyHistory(hi.items);
    }).catch(() => {}).finally(() => setDashLoading(false));
  }, [isOwnProfile]);

  useEffect(() => {
    if (!userId || isOwnProfile) return;
    const id = Number(userId);
    if (Number.isNaN(id)) return;

    setPublicPlaylistsLoading(true);
    playlistApi
      .listPublicPlaylists(id, { limit: 12 })
      .then((res) => setPublicPlaylists(res.items))
      .catch(() => toast.error("加载公开歌单失败"))
      .finally(() => setPublicPlaylistsLoading(false));
  }, [userId, isOwnProfile]);

  const handleToggleFollow = async () => {
    if (!profile) return;
    try {
      if (following) { await api.unfollow(profile.id); setFollowing(false); toast.success("已取消关注"); }
      else { await api.follow(profile.id); setFollowing(true); toast.success("已关注"); }
    } catch (err) { toast.error(err instanceof Error ? err.message : "操作失败"); }
  };

  if (loading) return <FadeIn><div className="empty-state"><p>加载中...</p></div></FadeIn>;
  if (!profile) return <FadeIn><EmptyState icon={UserCheck} title="用户不存在" description="该用户可能已被删除或你无权查看。" /></FadeIn>;

  return (
    <div>
      {/* ====== Header (common) ====== */}
      <FadeIn>
        <motion.div className="profile-header" whileHover={{ boxShadow: "0 4px 16px rgba(0,0,0,0.04)" }} transition={{ duration: 0.25 }}>
          <Avatar
            user={{
              avatar_url: profile.avatar_url,
              nickname: profile.nickname,
              username: profile.username,
            }}
            variant="profile"
          />
          <div className="profile-meta" style={{ flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <h2 style={{ margin: 0 }}>{profile.nickname}</h2>
              {currentUser && currentUser.id !== profile.id && (
                <motion.button onClick={handleToggleFollow} whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} type="button"
                  style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "6px 14px", borderRadius: 8,
                    border: following ? "1px solid var(--color-border)" : "none",
                    background: following ? "var(--color-surface-soft)" : "var(--color-ink)",
                    color: following ? "var(--color-ink)" : "white", cursor: "pointer", fontSize: 13, fontWeight: 600 }}>
                  {following ? <UserMinus size={14} /> : <UserPlus size={14} />}
                  {following ? "已关注" : "关注"}
                </motion.button>
              )}
            </div>
            <div className="profile-handle">@{profile.username}</div>
            <div className="profile-stats">
              <motion.div className="stat" whileHover={{ scale: 1.05 }}><div className="stat-value">Lv.{profile.level}</div><div className="stat-label">等级</div></motion.div>
              <motion.div className="stat" whileHover={{ scale: 1.05 }}><div className="stat-value">{profile.exp}</div><div className="stat-label">经验</div></motion.div>
              <motion.div className="stat" whileHover={{ scale: 1.05 }}><div className="stat-value">{profile.like_count}</div><div className="stat-label">获赞</div></motion.div>
            </div>
          </div>
        </motion.div>
      </FadeIn>

      {profile.bio && (
        <FadeIn delay={0.1}><p style={{ fontSize: 14, color: "var(--color-muted)", marginBottom: 20, lineHeight: 1.6 }}>{profile.bio}</p></FadeIn>
      )}

      {/* ====== Own Profile Dashboard ====== */}
      {isOwnProfile && (
        <div className="profile-dashboard">
          {/* Quick Jump Buttons */}
          <FadeIn delay={0.12}>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 8 }}>
              {[
                { to: "/playlists", icon: LayoutList, label: "全部歌单" },
                { to: "/library", icon: Heart, label: "我的收藏" },
                { to: "/history", icon: Clock, label: "播放历史" },
                { to: "/space", icon: MessageCircle, label: "个人空间" },
                { to: "/account", icon: UserCheck, label: "编辑资料" },
              ].map((btn) => (
                <motion.button key={btn.to} onClick={() => navigate(btn.to)} whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} type="button"
                  style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 16px", borderRadius: 10,
                    background: "var(--color-surface)", border: "1px solid var(--color-border)", cursor: "pointer",
                    fontSize: 13, fontWeight: 500, color: "var(--color-ink)" }}>
                  <btn.icon size={15} />{btn.label}
                </motion.button>
              ))}
            </div>
          </FadeIn>

          {dashLoading ? (
            <div style={{ textAlign: "center", padding: 32, color: "var(--color-muted)", fontSize: 13 }}>加载中...</div>
          ) : (
            <>
              {/* My Playlists */}
              <FadeIn delay={0.15}>
                <div className="profile-section-card">
                  <div className="section-header" style={{ marginBottom: 12 }}>
                    <h3 style={{ margin: 0 }}><LayoutList size={16} style={{ display: "inline", verticalAlign: "-2px", marginRight: 6 }} />我的歌单</h3>
                    <button className="section-link" onClick={() => navigate("/playlists")}>查看全部 <ArrowRight size={14} /></button>
                  </div>
                  {myPlaylists.length === 0 ? (
                    <EmptyState icon={ListMusic} title="暂无歌单" description="创建你的第一个歌单吧" compact />
                  ) : (
                    <StaggerContainer className="playlist-rail">
                      {myPlaylists.map((p) => (
                        <StaggerItem key={p.id}>
                          <CoverCard id={p.id} title={p.title} subtitle={p.is_private ? "私密" : `${p.user.nickname}`} coverUrl={p.cover_icon_url ?? undefined} onClick={() => navigate(`/playlist/${p.id}`)} />
                        </StaggerItem>
                      ))}
                    </StaggerContainer>
                  )}
                </div>
              </FadeIn>

              {/* My Album Collections */}
              <FadeIn delay={0.2}>
                <div className="profile-section-card">
                  <div className="section-header" style={{ marginBottom: 12 }}>
                    <h3 style={{ margin: 0 }}><Disc size={16} style={{ display: "inline", verticalAlign: "-2px", marginRight: 6 }} />收藏专辑</h3>
                    <button className="section-link" onClick={() => navigate("/library")}>查看全部 <ArrowRight size={14} /></button>
                  </div>
                  {myAlbums.length === 0 ? (
                    <EmptyState icon={Disc} title="暂无收藏专辑" description="去发现音乐看看" compact />
                  ) : (
                    <StaggerContainer className="playlist-rail">
                      {myAlbums.map((a) => (
                        <StaggerItem key={a.album.id}>
                          <CoverCard id={a.album.id} title={a.album.title} subtitle={`播放量 ${a.album.play_count}`} coverUrl={a.album.cover_icon_url ?? undefined} onClick={() => navigate(`/album/${a.album.id}`)} />
                        </StaggerItem>
                      ))}
                    </StaggerContainer>
                  )}
                </div>
              </FadeIn>

              {/* My Recent History */}
              <FadeIn delay={0.25}>
                <div className="profile-section-card">
                  <div className="section-header" style={{ marginBottom: 12 }}>
                    <h3 style={{ margin: 0 }}><Clock size={16} style={{ display: "inline", verticalAlign: "-2px", marginRight: 6 }} />最近播放</h3>
                    <button className="section-link" onClick={() => navigate("/history")}>查看全部 <ArrowRight size={14} /></button>
                  </div>
                  {myHistory.length === 0 ? (
                    <EmptyState icon={Music2} title="暂无播放记录" description="开始听歌吧" compact />
                  ) : (
                    <StaggerContainer staggerDelay={0.04}>
                      {myHistory.map((item, i) => (
                        <StaggerItem key={item.id}>
                          <SongRow
                            name={item.music.title}
                            artist="未知艺人"
                            musicId={item.music.id}
                            coverUrl={item.music.cover_icon_url ?? undefined}
                            onPlay={() => playMusicById(item.music.id)}
                          />
                        </StaggerItem>
                      ))}
                    </StaggerContainer>
                  )}
                </div>
              </FadeIn>
            </>
          )}
        </div>
      )}

      {/* ====== Other User Profile ====== */}
      {!isOwnProfile && (
        <FadeIn delay={0.15}>
          <section>
            <div className="section-header" style={{ marginBottom: 12 }}>
              <h3 style={{ margin: 0 }}>
                <ListMusic size={16} style={{ display: "inline", verticalAlign: "-2px", marginRight: 6 }} />
                公开歌单
              </h3>
            </div>
            {publicPlaylistsLoading ? (
              <div style={{ textAlign: "center", padding: 32, color: "var(--color-muted)", fontSize: 13 }}>
                加载中...
              </div>
            ) : publicPlaylists.length === 0 ? (
              <EmptyState icon={ListMusic} title="该用户暂无公开歌单" compact />
            ) : (
              <StaggerContainer className="playlist-rail">
                {publicPlaylists.map((p) => (
                  <StaggerItem key={p.id}>
                    <CoverCard
                      id={p.id}
                      title={p.title}
                      subtitle={p.user.nickname}
                      coverUrl={p.cover_icon_url ?? undefined}
                      onClick={() => navigate(`/playlist/${p.id}`)}
                    />
                  </StaggerItem>
                ))}
              </StaggerContainer>
            )}
          </section>
        </FadeIn>
      )}
    </div>
  );
};
