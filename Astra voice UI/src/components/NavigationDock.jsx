import React from "react";
import { useApp } from "../context/AppContext";

export const NavigationDock = () => {
  const { currentView, setCurrentView, startVoiceInput, stopVoiceInput, assistantState } = useApp();

  const navItems = [
    { id: "home", label: "Assistant", icon: "graphic_eq" },
    { id: "conversation", label: "Thread", icon: "forum" },
    { id: "reminders", label: "Reminders", icon: "notifications" },
    { id: "tasks", label: "Tasks & Notes", icon: "task_alt" },
    { id: "settings", label: "Settings", icon: "tune" }
  ];

  return (
    <nav className="fixed bottom-5 left-1/2 -translate-x-1/2 z-40">
      <div className="flex items-center gap-1.5 p-1.5 rounded-full bg-[#1e2021]/80 backdrop-blur-2xl border border-white/[0.08] shadow-[0_8px_32px_rgba(0,0,0,0.5)]">
        {navItems.map((item) => {
          const isActive = currentView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setCurrentView(item.id)}
              className={"flex items-center gap-2 px-3.5 py-2 rounded-full text-xs font-medium transition-all duration-200 cursor-pointer " +
                (isActive
                  ? "bg-[#7c5cfc] text-white shadow-[0_0_20px_rgba(124,92,252,0.4)] font-semibold"
                  : "text-[#c9c4d8] hover:text-white hover:bg-white/[0.06]")}
            >
              <span className="material-symbols-outlined text-[18px]">{item.icon}</span>
              <span className={isActive ? "inline-block" : "hidden md:inline-block"}>{item.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
};
