import React, { useState, useRef, useEffect } from "react";
import { useApp } from "../../context/AppContext";

export const ConversationScreen = () => {
  const { messages, processQuery, speakText, startVoiceInput, assistantState } = useApp();
  const [inputText, setInputText] = useState("");
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (inputText.trim()) {
      processQuery(inputText);
      setInputText("");
    }
  };

  const renderWidget = (type, data) => {
    if (type === "WEATHER" && data) {
      return (
        <div className="mt-3 p-4 rounded-2xl bg-white/[0.04] border border-white/[0.08] backdrop-blur-md">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs uppercase tracking-wider text-[#938ea1]">{data.location}</span>
              <div className="text-3xl font-bold text-[#e2e2e3] mt-1">{data.temp}</div>
              <div className="text-sm text-[#cabeff]">{data.condition}</div>
            </div>
            <span className="material-symbols-outlined text-5xl text-[#cebdff]">partly_cloudy_day</span>
          </div>
          <div className="grid grid-cols-4 gap-2 mt-4 pt-3 border-t border-white/[0.06] text-center text-xs">
            {data.forecast?.map((f, i) => (
              <div key={i} className="flex flex-col items-center">
                <span className="text-[#938ea1]">{f.day}</span>
                <span className="material-symbols-outlined text-sm text-[#cabeff] my-1">{f.icon}</span>
                <span className="font-medium text-white">{f.temp}</span>
              </div>
            ))}
          </div>
        </div>
      );
    }

    if (type === "SCHEDULE" && data?.events) {
      return (
        <div className="mt-3 p-4 rounded-2xl bg-white/[0.04] border border-white/[0.08] space-y-2">
          <div className="text-xs uppercase tracking-wider text-[#cabeff] font-semibold mb-2">Today's Schedule</div>
          {data.events.map((ev, i) => (
            <div key={i} className="flex items-center justify-between p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.04]">
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-[#7c5cfc] text-lg">calendar_today</span>
                <div>
                  <div className="text-sm font-medium text-[#e2e2e3]">{ev.title}</div>
                  <div className="text-xs text-[#938ea1]">{ev.room}</div>
                </div>
              </div>
              <span className="text-xs font-semibold text-[#cebdff]">{ev.time}</span>
            </div>
          ))}
        </div>
      );
    }

    return null;
  };

  return (
    <div className="flex-1 flex flex-col w-full max-w-[800px] mx-auto px-6 pt-24 pb-32">
      {/* Header Info */}
      <div className="mb-6 flex items-center justify-between border-b border-white/[0.06] pb-4">
        <div>
          <h1 className="text-2xl font-bold text-[#e2e2e3]">Conversation</h1>
          <p className="text-sm text-[#938ea1]">Voice transcription and interactive dialogue history</p>
        </div>
        <button
          onClick={startVoiceInput}
          className="flex items-center gap-2 px-4 py-2 rounded-full bg-[#7c5cfc]/20 hover:bg-[#7c5cfc]/30 text-[#cabeff] border border-[#7c5cfc]/40 text-xs font-medium transition-all active:scale-95 cursor-pointer"
        >
          <span className="material-symbols-outlined text-base">mic</span>
          <span>Speak</span>
        </button>
      </div>

      {/* Messages Stream */}
      <div className="flex-1 space-y-4 overflow-y-auto pr-1">
        {messages.map((msg) => {
          const isUser = msg.sender === "user";
          return (
            <div
              key={msg.id}
              className={"flex flex-col " + (isUser ? "items-end" : "items-start")}
            >
              <div className="flex items-center gap-2 mb-1 px-1">
                <span className="text-xs text-[#938ea1] font-medium">
                  {isUser ? "You" : "Astra Voice"}
                </span>
                <span className="text-[10px] text-[#938ea1]/70">{msg.timestamp}</span>
              </div>

              <div
                className={"max-w-[85%] md:max-w-[75%] p-4 rounded-2xl " +
                  (isUser
                    ? "bg-[#7c5cfc] text-white rounded-br-sm shadow-[0_4px_20px_rgba(124,92,252,0.25)]"
                    : "glass-panel text-[#e2e2e3] rounded-bl-sm border border-white/[0.08]")}
              >
                <div className="leading-relaxed text-sm md:text-[15px]">{msg.text}</div>
                {renderWidget(msg.widgetType, msg.widgetData)}

                {!isUser && (
                  <div className="mt-3 flex items-center gap-3 pt-2 border-t border-white/[0.06]">
                    <button
                      onClick={() => speakText(msg.text)}
                      className="flex items-center gap-1 text-xs text-[#cabeff] hover:text-white transition-colors cursor-pointer"
                      title="Replay Voice Audio"
                    >
                      <span className="material-symbols-outlined text-sm">volume_up</span>
                      <span>Listen</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
        <div ref={endRef} />
      </div>

      {/* Input Bar */}
      <form onSubmit={handleSubmit} className="mt-6 flex items-center gap-2">
        <div className="flex-1 relative">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Type your message or voice query..."
            className="w-full bg-[#1e2021] border border-white/[0.08] rounded-full pl-5 pr-12 py-3 text-sm text-[#e2e2e3] placeholder-[#938ea1] focus:outline-none focus:border-[#7c5cfc]"
          />
          <button
            type="button"
            onClick={startVoiceInput}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-[#cabeff] hover:text-white transition-colors cursor-pointer"
            title="Start Microphone"
          >
            <span className="material-symbols-outlined text-lg">mic</span>
          </button>
        </div>
        <button
          type="submit"
          className="w-11 h-11 rounded-full bg-[#7c5cfc] hover:bg-[#6b47fc] text-white flex items-center justify-center transition-transform active:scale-95 cursor-pointer shadow-[0_0_15px_rgba(124,92,252,0.3)]"
        >
          <span className="material-symbols-outlined text-lg">send</span>
        </button>
      </form>
    </div>
  );
};
