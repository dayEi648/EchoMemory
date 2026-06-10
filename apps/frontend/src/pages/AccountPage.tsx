import { useRef, useState } from "react";
import { Camera, User, Shield, BadgeCheck } from "lucide-react";
import { toast } from "sonner";
import { motion } from "framer-motion";

import { useAuthStore } from "../shared/stores/authStore";
import { Avatar } from "../components/ui/Avatar";
import { PageTitle } from "../components/ui/PageTitle";
import { FadeIn } from "../components/motion/FadeIn";

import { CITY_OPTIONS } from "../shared/constants";

const roleLabel: Record<number, string> = {
  0: "普通用户",
  1: "VIP",
  2: "管理员",
  3: "超级管理员",
};

const statusLabel: Record<number, string> = {
  0: "正常",
  1: "临时封禁",
  2: "限制中",
  3: "已封禁",
};

export const AccountPage = () => {
  const { user, updateProfile } = useAuthStore();
  const [saving, setSaving] = useState(false);
  const [selectedAvatar, setSelectedAvatar] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!user) return null;

  const handleAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.error("请选择图片文件");
      return;
    }
    setSelectedAvatar(file);
    const reader = new FileReader();
    reader.onloadend = () => setAvatarPreview(reader.result as string);
    reader.readAsDataURL(file);
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSaving(true);
    try {
      await updateProfile({
        nickname: String(form.get("nickname") ?? ""),
        email: String(form.get("email") ?? "") || undefined,
        phone: String(form.get("phone") ?? "") || undefined,
        gender: Number(form.get("gender") ?? user.gender),
        birth: String(form.get("birth") ?? "") || undefined,
        bio: String(form.get("bio") ?? "") || undefined,
        city: String(form.get("city") ?? "") || undefined,
        avatar: selectedAvatar ?? undefined,
      });
      setSelectedAvatar(null);
      setAvatarPreview(null);
      toast.success("资料已保存");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <FadeIn>
        <PageTitle icon={User}>账号设置</PageTitle>
      </FadeIn>

      <div style={{ display: "grid", gap: 20 }}>
        {/* Profile Card */}
        <FadeIn delay={0.08}>
          <motion.div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 20,
              padding: 24,
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: 14,
            }}
            whileHover={{ boxShadow: "0 4px 16px rgba(0,0,0,0.04)" }}
            transition={{ duration: 0.25 }}
          >
            <div style={{ position: "relative" }}>
              <Avatar
                user={{
                  avatar_url: avatarPreview ?? user.avatar_url,
                  nickname: user.nickname,
                  username: user.username,
                }}
                size="lg"
              />
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                style={{ display: "none" }}
                onChange={handleAvatarChange}
              />
              <motion.button
                style={{
                  position: "absolute",
                  bottom: -2,
                  right: -2,
                  width: 28,
                  height: 28,
                  borderRadius: "50%",
                  background: "var(--color-ink)",
                  color: "white",
                  border: "2px solid var(--color-surface)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                }}
                whileHover={{ scale: 1.12 }}
                whileTap={{ scale: 0.9 }}
                type="button"
                title="更换头像"
                onClick={() => fileInputRef.current?.click()}
              >
                <Camera size={12} />
              </motion.button>
            </div>
            <div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>
                {user.nickname}
                {user.is_verified && (
                  <BadgeCheck
                    size={16}
                    style={{
                      display: "inline",
                      verticalAlign: "-2px",
                      marginLeft: 4,
                      color: "var(--color-accent-2)",
                    }}
                  />
                )}
              </div>
              <div style={{ fontSize: 13, color: "var(--color-muted)", marginTop: 2 }}>
                @{user.username} · {roleLabel[user.role]}
              </div>
              <motion.div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  marginTop: 8,
                  padding: "3px 10px",
                  borderRadius: 20,
                  fontSize: 12,
                  fontWeight: 600,
                  background: user.status === 0 ? "#e6f7f4" : "#fde8e8",
                  color: user.status === 0 ? "var(--color-accent-2)" : "var(--color-danger)",
                }}
                whileHover={{ scale: 1.03 }}
              >
                <Shield size={12} />
                {statusLabel[user.status]}
              </motion.div>
            </div>
          </motion.div>
        </FadeIn>

        {/* Edit Form */}
        <FadeIn delay={0.16}>
          <div className="form-panel">
            <h3>基础资料</h3>
            <form className="form-stack" onSubmit={handleSubmit}>
              <label>
                昵称
                <input name="nickname" defaultValue={user.nickname} required />
              </label>
              <label>
                邮箱
                <input name="email" type="email" defaultValue={user.email ?? ""} />
              </label>
              <label>
                手机号
                <input name="phone" defaultValue={user.phone ?? ""} />
              </label>
              <label>
                性别
                <select name="gender" defaultValue={String(user.gender)}>
                  <option value="0">未知</option>
                  <option value="1">男</option>
                  <option value="2">女</option>
                </select>
              </label>
              <label>
                生日
                <input name="birth" type="date" defaultValue={user.birth ?? ""} />
              </label>
              <label>
                居住城市
                <select name="city" defaultValue={user.city ?? ""} aria-label="居住城市">
                  <option value="">暂不选择</option>
                  {CITY_OPTIONS.map((city) => (
                    <option value={city} key={city}>
                      {city}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                简介
                <textarea name="bio" defaultValue={user.bio ?? ""} rows={4} />
              </label>
              <motion.button
                className="primary-button"
                disabled={saving}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                type="submit"
              >
                {saving ? "保存中" : "保存资料"}
              </motion.button>
            </form>
          </div>
        </FadeIn>
      </div>
    </div>
  );
};
