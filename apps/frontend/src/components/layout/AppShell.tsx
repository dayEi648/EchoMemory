import { useEffect, useRef } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { MusicPlayerOverlay } from "../player/MusicPlayerOverlay";
import { TopBar } from "./TopBar";
import { SideNav } from "./SideNav";
import { PlayerBar } from "./PlayerBar";

export const AppShell = () => {
  const location = useLocation();
  const mainRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = mainRef.current;
    if (!el) return;
    el.classList.remove("page-enter");
    void el.offsetWidth;
    el.classList.add("page-enter");
  }, [location.pathname]);

  return (
    <div className="app-shell">
      <TopBar />
      <div className="main-layout">
        <SideNav />
        <main ref={mainRef} className="main-content">
          <Outlet />
        </main>
      </div>
      <PlayerBar />
      <MusicPlayerOverlay />
    </div>
  );
};
