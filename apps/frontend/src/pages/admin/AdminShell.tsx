import { Outlet, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";

import { AdminTopBar } from "./AdminTopBar";
import { AdminSideNav } from "./AdminSideNav";

export const AdminShell = () => {
  const location = useLocation();

  return (
    <div className="admin-shell">
      <AdminTopBar />
      <div className="admin-layout">
        <AdminSideNav />
        <main className="admin-content">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.22, ease: [0.25, 0.1, 0.25, 1] }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
};
