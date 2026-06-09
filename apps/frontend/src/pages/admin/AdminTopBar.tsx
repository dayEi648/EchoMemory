import { ArrowLeft, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";

import { useAuthStore } from "../../shared/stores/authStore";
import { Avatar } from "../../components/ui/Avatar";

export const AdminTopBar = () => {
  const { user } = useAuthStore();

  return (
    <header className="admin-top-bar">
      <motion.div whileHover={{ x: -2 }} transition={{ duration: 0.15 }}>
        <Link to="/" className="back-link">
          <ArrowLeft size={16} />
          返回主站
        </Link>
      </motion.div>
      <div className="admin-title">
        <ShieldCheck size={16} style={{ display: "inline", verticalAlign: "-2px", marginRight: 6 }} />
        管理后台
      </div>
      {user && (
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          <Avatar user={user} size="sm" />
          <span style={{ fontSize: 13, fontWeight: 600 }}>{user.nickname}</span>
        </div>
      )}
    </header>
  );
};
