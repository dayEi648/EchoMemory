import { useState } from "react";
import { Music2, Headphones, Network, Tags, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";

import { useAuthStore } from "../shared/stores/authStore";
import { getApiErrorMessage } from "../shared/apiError";

import { CITY_OPTIONS } from "../shared/constants";

export const AuthPage = () => {
  const { login, register } = useAuthStore();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setLoading(true);
    try {
      if (mode === "login") {
        await login(
          String(form.get("username") ?? ""),
          String(form.get("password") ?? ""),
        );
      } else {
        await register({
          username: String(form.get("username") ?? ""),
          nickname: String(form.get("nickname") ?? ""),
          password: String(form.get("password") ?? ""),
          email: String(form.get("email") ?? "") || undefined,
          gender: Number(form.get("gender") ?? 0),
          city: String(form.get("city") ?? "") || undefined,
        });
      }
      toast.success(mode === "login" ? "欢迎回来" : "注册成功");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "认证失败"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
        >
          <div className="brand-mark">
            <Music2 size={24} />
          </div>
          <p className="eyebrow">EchoMemory</p>
          <h1>回声记忆</h1>
          <p className="auth-copy">
            用 AI Agent 连接你的音乐偏好、记忆片段与创作线索。
            {mode === "login" ? "登录以继续探索。" : "创建账户开启音乐之旅。"}
          </p>

          <div className="segmented">
            <motion.button
              className={mode === "login" ? "active" : ""}
              onClick={() => setMode("login")}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              type="button"
            >
              登录
            </motion.button>
            <motion.button
              className={mode === "register" ? "active" : ""}
              onClick={() => setMode("register")}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              type="button"
            >
              注册
            </motion.button>
          </div>

          <AnimatePresence mode="wait">
            <motion.form
              key={mode}
              className="form-stack"
              onSubmit={handleSubmit}
              initial={{ opacity: 0, x: mode === "login" ? -12 : 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: mode === "login" ? 12 : -12 }}
              transition={{ duration: 0.25 }}
            >
              <label>
                用户名
                <input name="username" />
              </label>
              {mode === "register" && (
                <label>
                  昵称
                  <input name="nickname" />
                </label>
              )}
              <label>
                密码
                <input name="password" type="password" />
              </label>
              {mode === "register" && (
                <>
                  <label>
                    邮箱
                    <input name="email" />
                  </label>
                  <label>
                    性别
                    <select name="gender" defaultValue="0">
                      <option value="0">未知</option>
                      <option value="1">男</option>
                      <option value="2">女</option>
                    </select>
                  </label>
                  <label>
                    居住城市
                    <select name="city" defaultValue="">
                      <option value="">暂不选择</option>
                      {CITY_OPTIONS.map((city) => (
                        <option value={city} key={city}>
                          {city}
                        </option>
                      ))}
                    </select>
                  </label>
                </>
              )}
              <motion.button
                className="primary-button"
                disabled={loading}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                type="submit"
              >
                {loading ? "处理中" : mode === "login" ? "进入账户" : "创建账户"}
              </motion.button>
            </motion.form>
          </AnimatePresence>
        </motion.div>
      </section>

      <section className="auth-artifact" aria-hidden="true">
        {/* 背景纹理 */}
        <div className="artifact-dot-grid" />

        {/* 背景光晕 —— framer-motion 驱动漂浮 */}
        <motion.div
          className="artifact-glow glow-1"
          animate={{ x: [0, 30, 0], y: [0, -22, 0] }}
          transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="artifact-glow glow-2"
          animate={{ x: [0, -22, 0], y: [0, 26, 0] }}
          transition={{ duration: 16, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="artifact-glow glow-3"
          animate={{ x: [0, 15, 0], y: [0, -18, 0] }}
          transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="artifact-glow glow-4"
          animate={{ x: [0, -18, 0], y: [0, 20, 0] }}
          transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
        />

        {/* 中央回声圆环 —— framer-motion 驱动脉冲扩散 */}
        <div className="echo-rings">
          {[0, 1, 2, 3].map((i) => (
            <motion.div
              key={i}
              className={`echo-ring echo-ring-color-${i % 3}`}
              initial={{ scale: 0.22, opacity: 0.85 }}
              animate={{ scale: 1, opacity: 0 }}
              transition={{
                duration: 7,
                delay: i * 1.75,
                repeat: Infinity,
                repeatDelay: 3,
                ease: "easeOut",
              }}
            />
          ))}
        </div>

        {/* 中心品牌图标 */}
        <div className="artifact-center">
          <Music2 size={32} strokeWidth={1.5} />
        </div>

        {/* 特性卡片 */}
        <motion.div
          className="auth-feature-card auth-feature-card-1"
          animate={{ y: [0, -6, 0] }}
          transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
        >
          <Headphones size={20} />
          <div>
            <div className="feature-title">AI 音乐推荐</div>
            <div className="feature-desc">智能理解你的音乐品味</div>
          </div>
        </motion.div>

        <motion.div
          className="auth-feature-card auth-feature-card-2"
          animate={{ y: [0, 8, 0] }}
          transition={{ duration: 6, repeat: Infinity, ease: "easeInOut", delay: 1 }}
        >
          <Network size={20} />
          <div>
            <div className="feature-title">记忆图谱</div>
            <div className="feature-desc">构建你的专属音乐记忆网络</div>
          </div>
        </motion.div>

        <motion.div
          className="auth-feature-card auth-feature-card-3"
          animate={{ y: [0, -5, 0] }}
          transition={{ duration: 7, repeat: Infinity, ease: "easeInOut", delay: 2 }}
        >
          <Tags size={20} />
          <div>
            <div className="feature-title">口味标签</div>
            <div className="feature-desc">精准刻画听歌偏好</div>
          </div>
        </motion.div>

        <motion.div
          className="auth-feature-card auth-feature-card-4"
          animate={{ y: [0, 7, 0] }}
          transition={{ duration: 6.5, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
        >
          <Sparkles size={20} />
          <div>
            <div className="feature-title">AI 回声</div>
            <div className="feature-desc">与你对话的音乐智能体</div>
          </div>
        </motion.div>
      </section>
    </main>
  );
};
