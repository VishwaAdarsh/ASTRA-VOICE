import React from "react";
import { useApp } from "../context/AppContext";
import { WebGLOrb } from "./WebGLOrb";

export const Header = () => {
  const { currentView, setCurrentView, assistantState } = useApp();

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
  };

  return (
    <header className="fixed top-0 left-0 w-full z-40 flex justify-between items-center px-6 md:px-12 h-16 bg-[#121415]/70 backdrop-blur-xl border-b border-white/[0.04]">
      {/* Left Title / Greeting */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setCurrentView("home")}
          className="flex items-center gap-2 text-left group cursor-pointer"
        >
          {currentView !== "home" && (
            <span className="material-symbols-outlined text-[#cabeff] text-xl group-hover:-translate-x-0.5 transition-transform">
              arrow_back
            </span>
          )}
          <span className="font-semibold text-lg md:text-xl text-[#e2e2e3] tracking-tight">
            {currentView === "home" ? getGreeting() : "Astra"}
          </span>
        </button>
      </div>

      {/* Center Mini Ambient Indicator when not on Home screen */}
      {currentView !== "home" && (
        <div 
          onClick={() => setCurrentView("home")}
          className="cursor-pointer flex items-center gap-2 px-3 py-1 rounded-full bg-white/[0.04] border border-white/[0.08] hover:bg-white/[0.08] transition-colors"
          title="Return to Voice Assistant"
        >
          <div className="w-5 h-5 rounded-full overflow-hidden flex items-center justify-center">
            <WebGLOrb size={22} interactive={false} />
          </div>
          <span className="text-xs font-medium uppercase tracking-widest text-[#c9c4d8]">
            {assistantState === "idle" ? "Astra" : assistantState}
          </span>
        </div>
      )}

      {/* Right Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setCurrentView("design")}
          className={"w-10 h-10 flex items-center justify-center rounded-full transition-all duration-200 cursor-pointer " + (currentView === "design" ? "bg-[#7c5cfc]/20 text-[#cabeff] border border-[#7c5cfc]/40" : "text-[#938ea1] hover:text-[#e2e2e3] hover:bg-white/10")}
          title="Design Tokens and Shader Studio"
        >
          <span className="material-symbols-outlined text-xl">palette</span>
        </button>

        <button
          onClick={() => setCurrentView(currentView === "settings" ? "home" : "settings")}
          className={"w-10 h-10 flex items-center justify-center rounded-full transition-all duration-200 cursor-pointer " + (currentView === "settings" ? "bg-[#7c5cfc]/20 text-[#cabeff] border border-[#7c5cfc]/40" : "text-[#938ea1] hover:text-[#e2e2e3] hover:bg-white/10")}
          title="Settings"
        >
          <span className="material-symbols-outlined text-xl">settings</span>
        </button>
      </div>
    </header>
  );
};
