import React, { useState } from "react";
import { useApp } from "../../context/AppContext";

export const RemindersScreen = () => {
  const { reminders, addReminder, toggleReminder, deleteReminder, startVoiceInput } = useApp();
  const [filter, setFilter] = useState("all"); // 'all' | 'today' | 'upcoming' | 'completed'
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newTime, setNewTime] = useState("Today, 6:00 PM");
  const [newCategory, setNewCategory] = useState("Personal");

  const filteredReminders = reminders.filter((r) => {
    if (filter === "today") return r.date === "Today" && !r.completed;
    if (filter === "upcoming") return r.date !== "Today" && !r.completed;
    if (filter === "completed") return r.completed;
    return true;
  });

  const handleAdd = (e) => {
    e.preventDefault();
    if (newTitle.trim()) {
      addReminder({
        title: newTitle,
        time: newTime,
        date: newTime.includes("Today") ? "Today" : "Upcoming",
        category: newCategory,
        completed: false,
        priority: "medium"
      });
      setNewTitle("");
      setIsModalOpen(false);
    }
  };

  return (
    <div className="flex-1 w-full max-w-[800px] mx-auto px-6 pt-24 pb-32">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-[#e2e2e3] tracking-tight">Reminders</h1>
          <p className="text-sm text-[#938ea1] mt-1">Stay effortlessly ahead of your day</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={startVoiceInput}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-full bg-white/[0.05] hover:bg-white/[0.08] border border-white/[0.08] text-xs font-medium text-[#cabeff] transition-all cursor-pointer"
            title="Add via Voice"
          >
            <span className="material-symbols-outlined text-sm">mic</span>
            <span>Voice Add</span>
          </button>
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-[#7c5cfc] hover:bg-[#6b47fc] text-white text-xs font-semibold transition-all cursor-pointer shadow-[0_0_20px_rgba(124,92,252,0.3)]"
          >
            <span className="material-symbols-outlined text-sm">add</span>
            <span>New</span>
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 mb-6 overflow-x-auto pb-2">
        {[
          { id: "all", label: "All (" + reminders.length + ")" },
          { id: "today", label: "Today" },
          { id: "upcoming", label: "Upcoming" },
          { id: "completed", label: "Completed" }
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setFilter(t.id)}
            className={"px-4 py-1.5 rounded-full text-xs font-medium transition-all cursor-pointer " +
              (filter === t.id
                ? "bg-[#7c5cfc]/25 text-[#cabeff] border border-[#7c5cfc]/40 font-semibold"
                : "bg-white/[0.03] text-[#938ea1] hover:text-white border border-white/[0.04]")}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Reminders List */}
      <div className="space-y-3">
        {filteredReminders.length === 0 ? (
          <div className="text-center py-16 glass-panel rounded-2xl border border-white/[0.04]">
            <span className="material-symbols-outlined text-4xl text-[#938ea1]/50 mb-2">notifications_off</span>
            <p className="text-[#938ea1] text-sm">No reminders in this view.</p>
            <p className="text-xs text-[#938ea1]/70 mt-1">Say "Remind me at 4 PM to..." to create one automatically.</p>
          </div>
        ) : (
          filteredReminders.map((rem) => (
            <div
              key={rem.id}
              className={"group flex items-center justify-between p-4 rounded-2xl transition-all duration-200 " +
                (rem.completed
                  ? "bg-white/[0.02] border border-white/[0.03] opacity-60"
                  : "glass-panel hover:border-[#7c5cfc]/30 hover:bg-[#1e2021]/80")}
            >
              <div className="flex items-center gap-4 flex-1">
                <button
                  onClick={() => toggleReminder(rem.id)}
                  className={"w-6 h-6 rounded-full flex items-center justify-center border transition-all cursor-pointer " +
                    (rem.completed
                      ? "bg-[#7c5cfc] border-[#7c5cfc] text-white"
                      : "border-[#938ea1]/40 hover:border-[#cabeff]")}
                >
                  {rem.completed && <span className="material-symbols-outlined text-sm">check</span>}
                </button>

                <div className="flex-1">
                  <div className={"text-sm font-medium " + (rem.completed ? "line-through text-[#938ea1]" : "text-[#e2e2e3]")}>
                    {rem.title}
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-[#938ea1]">
                    <span className="flex items-center gap-1 text-[#cabeff]">
                      <span className="material-symbols-outlined text-xs">schedule</span>
                      {rem.time}
                    </span>
                    <span className="px-2 py-0.5 rounded-md bg-white/[0.04] border border-white/[0.06]">
                      {rem.category}
                    </span>
                  </div>
                </div>
              </div>

              <button
                onClick={() => deleteReminder(rem.id)}
                className="opacity-0 group-hover:opacity-100 p-2 text-[#938ea1] hover:text-red-400 transition-all cursor-pointer"
                title="Delete Reminder"
              >
                <span className="material-symbols-outlined text-lg">delete</span>
              </button>
            </div>
          ))
        )}
      </div>

      {/* Add Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md p-4">
          <div className="glass-panel w-full max-w-md p-6 rounded-3xl border border-white/[0.1] shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-white">Create Reminder</h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-[#938ea1] hover:text-white cursor-pointer"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            <form onSubmit={handleAdd} className="space-y-4">
              <div>
                <label className="block text-xs uppercase tracking-wider text-[#938ea1] mb-1.5">Reminder Title</label>
                <input
                  type="text"
                  required
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. Schedule sync with engineering"
                  className="w-full bg-[#121415] border border-white/[0.08] rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#7c5cfc]"
                />
              </div>

              <div>
                <label className="block text-xs uppercase tracking-wider text-[#938ea1] mb-1.5">Time / Date</label>
                <input
                  type="text"
                  value={newTime}
                  onChange={(e) => setNewTime(e.target.value)}
                  placeholder="e.g. Today, 5:30 PM"
                  className="w-full bg-[#121415] border border-white/[0.08] rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#7c5cfc]"
                />
              </div>

              <div>
                <label className="block text-xs uppercase tracking-wider text-[#938ea1] mb-1.5">Category</label>
                <div className="flex gap-2">
                  {["Personal", "Work", "Health", "Home"].map((cat) => (
                    <button
                      type="button"
                      key={cat}
                      onClick={() => setNewCategory(cat)}
                      className={"flex-1 py-1.5 rounded-lg text-xs font-medium cursor-pointer " +
                        (newCategory === cat ? "bg-[#7c5cfc] text-white" : "bg-white/[0.04] text-[#938ea1] hover:text-white")}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-white/[0.06]">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-medium text-[#938ea1] hover:text-white cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl bg-[#7c5cfc] hover:bg-[#6b47fc] text-white text-xs font-semibold cursor-pointer shadow-[0_0_15px_rgba(124,92,252,0.3)]"
                >
                  Save Reminder
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
