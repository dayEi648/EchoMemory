import { useState } from "react";
import type { UserMe } from "../../shared/api/types";

export const Avatar = ({
  user,
  size = "md",
  variant = "default",
}: {
  user: Pick<UserMe, "avatar_url" | "nickname" | "username">;
  size?: "sm" | "md" | "lg" | "xl";
  /** profile：个人页头部 80px 圆形头像样式 */
  variant?: "default" | "profile";
}) => {
  const [error, setError] = useState(false);

  const sizeClass = {
    sm: "w-7 h-7 text-xs",
    md: "w-8 h-8 text-sm",
    lg: "w-10 h-10 text-base",
    xl: "w-20 h-20 text-2xl",
  }[size];

  const initial = user.nickname.slice(0, 1) || user.username.slice(0, 1);

  if (variant === "profile") {
    if (user.avatar_url && !error) {
      return (
        <img
          className="avatar-large"
          src={user.avatar_url}
          alt={`${user.nickname}的头像`}
          onError={() => setError(true)}
        />
      );
    }
    return (
      <div className="avatar-large-fallback" aria-label={`${user.nickname}的头像`}>
        {initial}
      </div>
    );
  }

  if (user.avatar_url && !error) {
    return (
      <img
        className={`${sizeClass} rounded-full object-cover`}
        src={user.avatar_url}
        alt={`${user.nickname}的头像`}
        onError={() => setError(true)}
      />
    );
  }

  return (
    <div
      className={`${sizeClass} rounded-full bg-accent text-white font-bold flex items-center justify-center`}
      aria-label={`${user.nickname}的头像`}
    >
      {initial}
    </div>
  );
};
