import { useCallback, useEffect, useState } from "react";
import { api, getToken, setToken, setUnauthorizedHandler } from "./api";
import type { Me } from "./types";
import AuthView from "./views/AuthView";
import ClosetView from "./views/ClosetView";
import InsightsView from "./views/InsightsView";
import SettingsView from "./views/SettingsView";
import TodayView from "./views/TodayView";

const TABS = [
  { id: "today", label: "Plan", icon: "M4 6h16M4 12h16M4 18h10" },
  { id: "closet", label: "Closet", icon: "M12 3l7 4-3 3v11H8V10L5 7z" },
  { id: "insights", label: "Insights", icon: "M5 20V10M12 20V4M19 20v-7" },
  { id: "settings", label: "Settings", icon: "M12 15a3 3 0 100-6 3 3 0 000 6zM4 12h2M18 12h2M12 4v2M12 18v2" },
] as const;
type Tab = (typeof TABS)[number]["id"];

function initialTab(): Tab {
  const h = window.location.hash.slice(1);
  return (TABS.find((t) => t.id === h)?.id ?? "today") as Tab;
}

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(!!getToken());
  const [tab, setTab] = useState<Tab>(initialTab);

  const signOut = useCallback(() => {
    setToken(null);
    setMe(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(signOut);
    if (!getToken()) return;
    api<Me>("/api/me")
      .then(setMe)
      .catch(() => signOut())
      .finally(() => setLoading(false));
  }, [signOut]);

  useEffect(() => {
    const onHash = () => setTab(initialTab());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const go = (t: Tab) => {
    window.location.hash = t;
    setTab(t);
  };

  if (loading) return <div className="splash">Warpdrobe</div>;
  if (!me)
    return (
      <AuthView
        onAuthed={(token, user) => {
          setToken(token);
          setMe(user);
        }}
      />
    );

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">
          warp<b>drobe</b>
        </span>
        <span className="hello">Hi, {me.name.split(" ")[0]}</span>
      </header>
      <main className="content">
        {tab === "today" && <TodayView me={me} onGoSettings={() => go("settings")} onGoCloset={() => go("closet")} />}
        {tab === "closet" && <ClosetView />}
        {tab === "insights" && <InsightsView />}
        {tab === "settings" && <SettingsView me={me} onChange={setMe} onSignOut={signOut} />}
      </main>
      <nav className="tabbar" aria-label="Main">
        {TABS.map((t) => (
          <button key={t.id} className={tab === t.id ? "active" : ""} onClick={() => go(t.id)} aria-current={tab === t.id}>
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d={t.icon} />
            </svg>
            {t.label}
          </button>
        ))}
      </nav>
    </div>
  );
}
