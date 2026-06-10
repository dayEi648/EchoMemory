import { useState } from "react";
import type { UserMe } from "../../shared/api/types";

export const Avatar = ({
  user,
  size = "md",
}: {
  user: Pick<UserMe, "avatar_url" | "nickname" | "username">;
  size?: "sm" | "md" | "lg" | "xl";
}) => {
  const [error, setError] = useState(false);

  const sizeClass = {
    sm: "w-7 h-7 text-xs",
    md: "w-8 h-8 text-sm",
    lg: "w-10 h-10 text-base",
    xl: "w-20 h-20 text-2xl",
  }[size];

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
      {user.nickname.slice(0, 1) || user.username.slice(0, 1)}
    </div>
  );
};
