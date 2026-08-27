import React from "react";
import { AppProvider, useApp } from "./context/AppContext";
import { Header } from "./components/Header";
import { NavigationDock } from "./components/NavigationDock";
import { HomeScreen } from "./components/views/HomeScreen";
import { ConversationScreen } from "./components/views/ConversationScreen";
import { RemindersScreen } from "./components/views/RemindersScreen";
import { TasksNotesScreen } from "./components/views/TasksNotesScreen";
import { SettingsScreen } from "./components/views/SettingsScreen";
import { DesignSystemScreen } from "./components/views/DesignSystemScreen";
import { ConfirmationBottomSheet } from "./components/ConfirmationBottomSheet";

const MainContent = () => {
  const { currentView, toastMessage } = useApp();

  const renderView = () => {
    switch (currentView) {
      case "conversation":
        return <ConversationScreen />;
      case "reminders":
        return <RemindersScreen />;
      case "tasks":
        return <TasksNotesScreen />;
      case "settings":
        return <SettingsScreen />;
      case "design":
        return <DesignSystemScreen />;
      case "home":
      default:
        return <HomeScreen />;
    }
  };

  return (
    <div className="min-h-screen flex flex-col relative bg-[#121415] text-[#e2e2e3] selection:bg-[#7c5cfc]/30 selection:text-white">
      {/* Background Ambient Soft Violet Gradients */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-[#7c5cfc]/[0.08] rounded-full blur-[140px]" />
        <div className="absolute bottom-10 right-10 w-[400px] h-[400px] bg-[#947dff]/[0.04] rounded-full blur-[120px]" />
      </div>

      <Header />

      <main className="flex-1 flex flex-col relative z-10">
        {renderView()}
      </main>

      <NavigationDock />

      <ConfirmationBottomSheet />

      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-20 left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 rounded-full bg-[#1e2021]/95 border border-[#7c5cfc]/40 shadow-2xl backdrop-blur-xl flex items-center gap-2 text-xs font-medium text-white animate-fade-in">
          <span className="material-symbols-outlined text-[#cabeff] text-base">
            {toastMessage.icon || "check_circle"}
          </span>
          <span>{toastMessage.text}</span>
        </div>
      )}
    </div>
  );
};

export default function App() {
  return (
    <AppProvider>
      <MainContent />
    </AppProvider>
  );
}
