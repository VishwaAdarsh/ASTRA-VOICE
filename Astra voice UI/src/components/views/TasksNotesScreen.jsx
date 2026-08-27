import React, { useState } from "react";
import { useApp } from "../../context/AppContext";

export const TasksNotesScreen = () => {
  const { tasks, addTask, toggleTask, deleteTask, notes, addNote, deleteNote, startVoiceInput } = useApp();
  const [tab, setTab] = useState("tasks"); // 'tasks' | 'notes'
  const [searchQuery, setSearchQuery] = useState("");

  // Task Modal state
  const [isTaskModalOpen, setIsTaskModalOpen] = useState(false);
  const [taskTitle, setTaskTitle] = useState("");
  const [taskCategory, setTaskCategory] = useState("Development");

  // Note Modal state
  const [isNoteModalOpen, setIsNoteModalOpen] = useState(false);
  const [noteTitle, setNoteTitle] = useState("");
  const [noteBody, setNoteBody] = useState("");
  const [noteTag, setNoteTag] = useState("Design");

  const filteredTasks = tasks.filter((t) =>
    t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    t.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredNotes = notes.filter((n) =>
    n.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    n.body.toLowerCase().includes(searchQuery.toLowerCase()) ||
    n.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const handleCreateTask = (e) => {
    e.preventDefault();
    if (taskTitle.trim()) {
      addTask({
        title: taskTitle,
        category: taskCategory,
        completed: false,
        priority: "medium",
        dueDate: "Today"
      });
      setTaskTitle("");
      setIsTaskModalOpen(false);
    }
  };

  const handleCreateNote = (e) => {
    e.preventDefault();
    if (noteBody.trim()) {
      addNote({
        title: noteTitle || "Voice Note",
        body: noteBody,
        date: new Date().toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" }),
        tags: [noteTag],
        color: "#7c5cfc"
      });
      setNoteTitle("");
      setNoteBody("");
      setIsNoteModalOpen(false);
    }
  };

  return (
    <div className="flex-1 w-full max-w-[800px] mx-auto px-6 pt-24 pb-32">
      {/* Top Segmented Control */}
      <div className="flex bg-[#1e2021] p-1 rounded-full mb-8 border border-white/[0.06] shadow-sm">
        <button
          onClick={() => setTab("tasks")}
          className={"flex-1 py-2.5 rounded-full text-center text-xs uppercase tracking-wider font-bold transition-all cursor-pointer " +
            (tab === "tasks" ? "bg-[#7c5cfc]/25 text-[#cabeff] border border-[#7c5cfc]/30 shadow-inner" : "text-[#938ea1] hover:text-white")}
        >
          Tasks ({tasks.length})
        </button>
        <button
          onClick={() => setTab("notes")}
          className={"flex-1 py-2.5 rounded-full text-center text-xs uppercase tracking-wider font-bold transition-all cursor-pointer " +
            (tab === "notes" ? "bg-[#7c5cfc]/25 text-[#cabeff] border border-[#7c5cfc]/30 shadow-inner" : "text-[#938ea1] hover:text-white")}
        >
          Notes ({notes.length})
        </button>
      </div>

      {/* Header & Search */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div className="relative flex-1">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={"Search " + tab + "..."}
            className="w-full bg-[#1e2021] border border-white/[0.08] rounded-xl pl-9 pr-4 py-2 text-xs text-[#e2e2e3] placeholder-[#938ea1] focus:outline-none focus:border-[#7c5cfc]"
          />
          <span className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-sm text-[#938ea1]">search</span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={startVoiceInput}
            className="flex items-center gap-1 px-3 py-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-xs text-[#cabeff] cursor-pointer"
          >
            <span className="material-symbols-outlined text-sm">mic</span>
            <span>Voice</span>
          </button>
          <button
            onClick={() => (tab === "tasks" ? setIsTaskModalOpen(true) : setIsNoteModalOpen(true))}
            className="flex items-center gap-1 px-4 py-2 rounded-xl bg-[#7c5cfc] hover:bg-[#6b47fc] text-white text-xs font-semibold cursor-pointer shadow-[0_0_15px_rgba(124,92,252,0.3)]"
          >
            <span className="material-symbols-outlined text-sm">add</span>
            <span>Add {tab === "tasks" ? "Task" : "Note"}</span>
          </button>
        </div>
      </div>

      {/* Tasks View */}
      {tab === "tasks" && (
        <div className="space-y-2.5">
          {filteredTasks.length === 0 ? (
            <div className="text-center py-12 glass-panel rounded-2xl border border-white/[0.04]">
              <span className="material-symbols-outlined text-4xl text-[#938ea1]/50 mb-2">task</span>
              <p className="text-[#938ea1] text-sm">No tasks found.</p>
            </div>
          ) : (
            filteredTasks.map((t) => (
              <div
                key={t.id}
                className={"group flex items-center justify-between p-3.5 rounded-2xl transition-all " +
                  (t.completed ? "bg-white/[0.02] border border-white/[0.04] opacity-60" : "glass-panel hover:bg-[#1e2021]/80")}
              >
                <div className="flex items-center gap-3.5 flex-1">
                  <button
                    onClick={() => toggleTask(t.id)}
                    className={"w-5 h-5 rounded-lg flex items-center justify-center border transition-all cursor-pointer " +
                      (t.completed ? "bg-[#7c5cfc] border-[#7c5cfc] text-white" : "border-[#938ea1]/40 hover:border-[#cabeff]")}
                  >
                    {t.completed && <span className="material-symbols-outlined text-xs">check</span>}
                  </button>

                  <div className="flex-1">
                    <span className={"text-sm " + (t.completed ? "line-through text-[#938ea1]" : "text-[#e2e2e3]")}>
                      {t.title}
                    </span>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[11px] text-[#938ea1]">{t.category}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.04] text-[#cabeff]">{t.dueDate}</span>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => deleteTask(t.id)}
                  className="opacity-0 group-hover:opacity-100 p-1 text-[#938ea1] hover:text-red-400 transition-all cursor-pointer"
                >
                  <span className="material-symbols-outlined text-sm">delete</span>
                </button>
              </div>
            ))
          )}
        </div>
      )}

      {/* Notes View */}
      {tab === "notes" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredNotes.length === 0 ? (
            <div className="col-span-2 text-center py-12 glass-panel rounded-2xl border border-white/[0.04]">
              <span className="material-symbols-outlined text-4xl text-[#938ea1]/50 mb-2">note</span>
              <p className="text-[#938ea1] text-sm">No notes recorded yet.</p>
            </div>
          ) : (
            filteredNotes.map((n) => (
              <div
                key={n.id}
                className="group glass-panel p-5 rounded-2xl border border-white/[0.08] hover:border-[#7c5cfc]/30 flex flex-col justify-between transition-all"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-bold text-sm text-[#e2e2e3]">{n.title}</h3>
                    <button
                      onClick={() => deleteNote(n.id)}
                      className="opacity-0 group-hover:opacity-100 text-[#938ea1] hover:text-red-400 transition-all cursor-pointer"
                    >
                      <span className="material-symbols-outlined text-sm">delete</span>
                    </button>
                  </div>
                  <p className="text-xs text-[#c9c4d8] leading-relaxed line-clamp-4">{n.body}</p>
                </div>

                <div className="flex items-center justify-between mt-4 pt-3 border-t border-white/[0.06] text-[11px] text-[#938ea1]">
                  <span>{n.date}</span>
                  <div className="flex gap-1">
                    {n.tags?.map((tg, i) => (
                      <span key={i} className="px-2 py-0.5 rounded-full bg-[#7c5cfc]/15 text-[#cabeff]">
                        #{tg}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Add Task Modal */}
      {isTaskModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md p-4">
          <div className="glass-panel w-full max-w-md p-6 rounded-3xl border border-white/[0.1]">
            <h3 className="text-lg font-bold text-white mb-4">Create New Task</h3>
            <form onSubmit={handleCreateTask} className="space-y-4">
              <input
                type="text"
                required
                value={taskTitle}
                onChange={(e) => setTaskTitle(e.target.value)}
                placeholder="What needs to be done?"
                className="w-full bg-[#121415] border border-white/[0.08] rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#7c5cfc]"
              />
              <div className="flex gap-2">
                {["Development", "Design System", "Product", "QA"].map((c) => (
                  <button
                    type="button"
                    key={c}
                    onClick={() => setTaskCategory(c)}
                    className={"flex-1 py-1.5 rounded-lg text-xs font-medium cursor-pointer " +
                      (taskCategory === c ? "bg-[#7c5cfc] text-white" : "bg-white/[0.04] text-[#938ea1]")}
                  >
                    {c}
                  </button>
                ))}
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsTaskModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs text-[#938ea1]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl bg-[#7c5cfc] text-white text-xs font-semibold"
                >
                  Add Task
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Note Modal */}
      {isNoteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md p-4">
          <div className="glass-panel w-full max-w-md p-6 rounded-3xl border border-white/[0.1]">
            <h3 className="text-lg font-bold text-white mb-4">New Note</h3>
            <form onSubmit={handleCreateNote} className="space-y-4">
              <input
                type="text"
                value={noteTitle}
                onChange={(e) => setNoteTitle(e.target.value)}
                placeholder="Note Title (Optional)"
                className="w-full bg-[#121415] border border-white/[0.08] rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#7c5cfc]"
              />
              <textarea
                required
                rows={4}
                value={noteBody}
                onChange={(e) => setNoteBody(e.target.value)}
                placeholder="Type your notes or voice thoughts here..."
                className="w-full bg-[#121415] border border-white/[0.08] rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#7c5cfc]"
              />
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsNoteModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs text-[#938ea1]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl bg-[#7c5cfc] text-white text-xs font-semibold"
                >
                  Save Note
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
