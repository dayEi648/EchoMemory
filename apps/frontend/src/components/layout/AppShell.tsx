import { Outlet, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";

import { TopBar } from "./TopBar";
import { SideNav } from "./SideNav";
import { PlayerBar } from "./PlayerBar";

export const AppShell = () => {
  const location = useLocation();

  return (
    <div className="app-shell">
      <TopBar />
      <div className="main-layout">
        <SideNav />
        <main className="main-content">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.25, ease: [0.25, 0.1, 0.25, 1] }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
      <PlayerBar />
    </div>
  );
};
