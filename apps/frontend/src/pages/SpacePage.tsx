import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { MessageCircle, ArrowLeft } from "lucide-react";
import { toast } from "sonner";
import { motion } from "framer-motion";

import { useAuthStore } from "../shared/stores/authStore";
import { createSpacePostApi } from "../shared/api/spacePostApi";
import { createLocalStorageTokenStore } from "../shared/auth/tokenStore";
import type { SpacePostListItem, UserPublic } from "../shared/api/types";
import { FadeIn } from "../components/motion/FadeIn";
import { EmptyState } from "../components/ui/EmptyState";
import { PageTitle } from "../components/ui/PageTitle";
import { PaginationBar } from "../components/ui/PaginationBar";
import { CreatePostForm } from "../components/ui/CreatePostForm";
import { SpacePostCard } from "../components/ui/SpacePostCard";
import type { PostAuthor } from "../components/ui/SpacePostCard";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";
const tokenStore = createLocalStorageTokenStore();
const spacePostApi = createSpacePostApi({ baseUrl: API_BASE_URL, tokenStore });

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

  // Author info for the target user
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
    } catch {
      toast.error("加载动态失败");
    } finally {
      setLoading(false);
    }
  }, [targetUserId, page]);

  // Load author info for other user's space
  useEffect(() => {
    if (targetUserId && targetUserId !== currentUser?.id) {
      api
        .getPublicUser(targetUserId)
        .then((u: UserPublic) =>
          setTargetAuthor({
            id: u.id,
            nickname: u.nickname,
            username: u.username,
            avatar_url: u.avatar_url,
          }),
        )
        .catch(() => setTargetAuthor(null));
    } else {
      setTargetAuthor(null);
    }
  }, [targetUserId, currentUser, api]);

  useEffect(() => {
    loadPosts();
  }, [loadPosts]);

  const author: PostAuthor =
    targetAuthor ??
    (currentUser
      ? {
          id: currentUser.id,
          nickname: currentUser.nickname,
          username: currentUser.username,
          avatar_url: currentUser.avatar_url,
        }
      : { id: 0, nickname: "未知", username: "unknown", avatar_url: null });

  const handleCreated = (post: SpacePostListItem) => {
    setPosts((prev) => [post, ...prev]);
    setTotal((prev) => prev + 1);
  };

  const handleDelete = async (postId: number) => {
    await spacePostApi.deletePost(postId);
    setPosts((prev) => prev.filter((p) => p.id !== postId));
    setTotal((prev) => Math.max(0, prev - 1));
  };

  const handleLike = async (postId: number) => {
    await spacePostApi.likePost(postId);
  };

  const handleUnlike = async (postId: number) => {
    await spacePostApi.unlikePost(postId);
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div>
      <FadeIn>
        {targetUserId && !isOwnSpace && (
          <motion.button
            className="section-link"
            onClick={() => navigate(-1)}
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

      {/* Create form (only for own space) */}
      {isOwnSpace && (
        <FadeIn delay={0.06}>
          <CreatePostForm onCreated={handleCreated} />
        </FadeIn>
      )}

      {/* Post list */}
      {loading ? (
        <div className="loading-screen" style={{ height: "30vh" }}>
          <div style={{ fontSize: 14, fontWeight: 500 }}>加载中...</div>
        </div>
      ) : posts.length === 0 ? (
        <FadeIn delay={0.1}>
          <EmptyState
            icon={MessageCircle}
            title={isOwnSpace ? "还没有发表过说说" : "该用户暂无公开说说"}
            description={
              isOwnSpace
                ? "分享你的音乐心情，记录每一个瞬间。"
                : "该用户还没有公开发布过说说。"
            }
          />
        </FadeIn>
      ) : (
        <FadeIn delay={0.08}>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {posts.map((post) => (
              <SpacePostCard
                key={post.id}
                post={post}
                author={author}
                currentUserId={currentUser?.id ?? 0}
                onDelete={handleDelete}
                onLike={handleLike}
                onUnlike={handleUnlike}
              />
            ))}
          </div>

          {(totalPages > 1 || total > 0) && (
            <div style={{ marginTop: 24 }}>
              <PaginationBar
                page={page}
                totalPages={totalPages}
                onPageChange={setPage}
                loading={loading}
                total={total}
              />
            </div>
          )}
        </FadeIn>
      )}
    </div>
  );
};
