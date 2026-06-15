import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { MessageCircle, ArrowLeft, FileText, Image, Heart, TrendingUp } from "lucide-react";
import { toast } from "sonner";
import { motion } from "framer-motion";

import { useAuthStore } from "../shared/stores/authStore";
import { spacePostApi } from "../shared/api/instances";
import type { SpacePostListItem, UserPublic } from "../shared/api/types";
import { FadeIn } from "../components/motion/FadeIn";
import { EmptyState } from "../components/ui/EmptyState";
import { PageTitle } from "../components/ui/PageTitle";
import { PaginationBar } from "../components/ui/PaginationBar";
import { PaginatedPageLayout } from "../components/layout/PaginatedPageLayout";
import { CreatePostForm } from "../components/ui/CreatePostForm";
import { SpacePostCard } from "../components/ui/SpacePostCard";
import { getApiErrorMessage } from "../shared/apiError";
import type { PostAuthor } from "../components/ui/SpacePostCard";

const PAGE_SIZE = 10;

export const SpacePage = () => {
  const { userId: userIdParam } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const { user: currentUser, api } = useAuthStore();

  const targetUserId = userIdParam ? Number(userIdParam) : undefined;
  const isOwnSpace = !targetUserId || targetUserId === currentUser?.id;

  const [posts, setPosts] = useState<SpacePostListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [targetAuthor, setTargetAuthor] = useState<PostAuthor | null>(null);

  const loadPosts = useCallback(async () => {
    setLoading(true);
    try {
      const result = await spacePostApi.listPosts({
        user_id: targetUserId,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      });
      setPosts(result.items);
      setTotal(result.total);
    } catch (err) {
      toast.error(getApiErrorMessage(err, "加载动态失败"));
    } finally {
      setLoading(false);
    }
  }, [targetUserId, page]);

  useEffect(() => {
    if (targetUserId && targetUserId !== currentUser?.id) {
      api.getPublicUser(targetUserId)
        .then((u: UserPublic) => setTargetAuthor({ id: u.id, nickname: u.nickname, username: u.username, avatar_url: u.avatar_url, like_count: u.like_count }))
        .catch((err) => {
          setTargetAuthor(null);
          toast.error(getApiErrorMessage(err, "加载用户信息失败"));
        });
    } else {
      setTargetAuthor(null);
    }
  }, [targetUserId, currentUser, api]);

  useEffect(() => { loadPosts(); }, [loadPosts]);

  const author: PostAuthor =
    targetAuthor ??
    (currentUser ? { id: currentUser.id, nickname: currentUser.nickname, username: currentUser.username, avatar_url: currentUser.avatar_url, like_count: currentUser.like_count } : { id: 0, nickname: "未知", username: "unknown", avatar_url: null, like_count: 0 });

  const handleCreated = (post: SpacePostListItem) => {
    setPosts((prev) => [post, ...prev]);
    setTotal((prev) => prev + 1);
  };

  const handleDelete = async (postId: number) => {
    try {
      await spacePostApi.deletePost(postId);
      setPosts((prev) => prev.filter((p) => p.id !== postId));
      setTotal((prev) => Math.max(0, prev - 1));
    } catch (err) {
      toast.error(getApiErrorMessage(err, "删除失败"));
      throw err;
    }
  };

  const handleLike = async (postId: number) => {
    try {
      await spacePostApi.likePost(postId);
    } catch (err) {
      toast.error(getApiErrorMessage(err, "操作失败"));
      throw err;
    }
  };

  const handleUnlike = async (postId: number) => {
    try {
      await spacePostApi.unlikePost(postId);
    } catch (err) {
      toast.error(getApiErrorMessage(err, "操作失败"));
      throw err;
    }
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const imagePostCount = posts.filter((p) => p.images.length > 0).length;

  return (
    <PaginatedPageLayout
      header={(
        <FadeIn>
          {targetUserId && !isOwnSpace && (
            <motion.button
              className="section-link" onClick={() => navigate(-1)}
              whileHover={{ x: -4 }}
              style={{ display: "inline-flex", alignItems: "center", gap: 4, marginBottom: 8 }}
            >
              <ArrowLeft size={16} /> 返回
            </motion.button>
          )}
          <PageTitle icon={MessageCircle} iconSize={22}>
            {isOwnSpace ? "个人空间" : `${author.nickname} 的空间`}
          </PageTitle>
        </FadeIn>
      )}
      footer={
        (totalPages > 1 || total > 0) ? (
          <PaginationBar page={page} totalPages={totalPages} onPageChange={setPage} loading={loading} total={total} />
        ) : undefined
      }
    >
      {/* Stats Bar */}
      <FadeIn delay={0.06}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
            gap: 12,
            marginBottom: 24,
          }}
        >
          <motion.div className="profile-stat-card" whileHover={{ y: -3 }} transition={{ duration: 0.2 }}>
            <div className="stat-card-icon icon-accent-bg icon-accent-bg--lavender"><FileText size={20} /></div>
            <div className="stat-card-value">{total}</div>
            <div className="stat-card-label">全部说说</div>
          </motion.div>
          <motion.div className="profile-stat-card" whileHover={{ y: -3 }} transition={{ duration: 0.2 }}>
            <div className="stat-card-icon icon-accent-bg icon-accent-bg--mint"><Image size={20} /></div>
            <div className="stat-card-value">{imagePostCount}</div>
            <div className="stat-card-label">带图说说</div>
          </motion.div>
          <motion.div className="profile-stat-card" whileHover={{ y: -3 }} transition={{ duration: 0.2 }}>
            <div className="stat-card-icon icon-accent-bg icon-accent-bg--coral"><Heart size={20} /></div>
            <div className="stat-card-value">{author.like_count}</div>
            <div className="stat-card-label">获赞总数</div>
          </motion.div>
          <motion.div className="profile-stat-card" whileHover={{ y: -3 }} transition={{ duration: 0.2 }}>
            <div className="stat-card-icon icon-accent-bg icon-accent-bg--ochre"><TrendingUp size={20} /></div>
            <div className="stat-card-value">Lv.{currentUser?.level ?? "—"}</div>
            <div className="stat-card-label">当前等级</div>
          </motion.div>
        </div>
      </FadeIn>

      {/* Create form (own space only) */}
      {isOwnSpace && (
        <FadeIn delay={0.08}>
          <CreatePostForm onCreated={handleCreated} />
        </FadeIn>
      )}

      {/* Post list */}
      {loading ? (
        <div className="loading-screen" style={{ height: "30vh" }}><div style={{ fontSize: 14, fontWeight: 500 }}>加载中...</div></div>
      ) : posts.length === 0 ? (
        <FadeIn delay={0.1}>
          <EmptyState icon={MessageCircle} title={isOwnSpace ? "还没有发表过说说" : "该用户暂无公开说说"} description={isOwnSpace ? "分享你的音乐心情，记录每一个瞬间。" : "该用户还没有公开发布过说说。"} />
        </FadeIn>
      ) : (
        <FadeIn delay={0.08}>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {posts.map((post) => (
              <SpacePostCard key={post.id} post={post} author={author} currentUserId={currentUser?.id ?? 0} onDelete={handleDelete} onLike={handleLike} onUnlike={handleUnlike} />
            ))}
          </div>
        </FadeIn>
      )}
    </PaginatedPageLayout>
  );
};
