import { useState, useRef, useEffect } from "react";
import {
  ChevronDown,
  LogOut,
  Settings,
  ShieldCheck,
  User,
  Heart,
  Clock,
  Music,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";

import { useAuthStore } from "../../shared/stores/authStore";
import type { UserMe } from "../../shared/api/types";
import { Avatar } from "../ui/Avatar";

const roleLabel: Record<UserMe["role"], string> = {
  0: "普通用户",
  1: "VIP",
  2: "管理员",
  3: "超级管理员",
};

export const AvatarMenu = () => {
  const { user, logout } = useAuthStore();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, []);

  if (!user) return null;

  const isAdmin = user.role === 2 || user.role === 3;

  const handleNavigate = (path: string) => {
    setOpen(false);
    navigate(path);
  };

  const handleLogout = async () => {
    setOpen(false);
    await logout();
  };

  const menuItems = [
    { icon: User, label: "我的主页", path: `/profile/${user.id}` },
    { icon: Settings, label: "账号设置", path: "/account" },
    { icon: Heart, label: "我的收藏", path: "/library" },
    { icon: Clock, label: "最近播放", path: "/history" },
    { icon: Music, label: "AI 回声", path: "/echo" },
  ];

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <motion.button
        className="avatar-trigger"
        onClick={() => setOpen(!open)}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        type="button"
      >
        <Avatar user={user} size="sm" />
        <span className="nickname">{user.nickname}</span>
        <motion.div
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronDown size={14} className="text-muted" />
        </motion.div>
      </motion.button>

      <AnimatePresence>
        {open && (
          <motion.div
            className="avatar-menu-dropdown"
            initial={{ opacity: 0, scale: 0.96, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -4 }}
            transition={{ duration: 0.18, ease: [0.25, 0.1, 0.25, 1] }}
          >
            <div className="menu-header">
              <div className="name">{user.nickname}</div>
              <div className="role">
                {roleLabel[user.role]} · Lv.{user.level}
              </div>
            </div>

            {menuItems.map((item, i) => (
              <motion.button
                key={item.label}
                onClick={() => handleNavigate(item.path)}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.03 * i, duration: 0.15 }}
                type="button"
              >
                <item.icon size={16} />
                {item.label}
              </motion.button>
            ))}

            {isAdmin && (
              <>
                <div className="menu-divider" />
                <motion.button
                  onClick={() => handleNavigate("/admin")}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.15, duration: 0.15 }}
                  type="button"
                >
                  <ShieldCheck size={16} />
                  管理后台
                </motion.button>
              </>
            )}

            <div className="menu-divider" />
            <motion.button
              className="danger"
              onClick={handleLogout}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.18, duration: 0.15 }}
              type="button"
            >
              <LogOut size={16} />
              退出登录
            </motion.button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
