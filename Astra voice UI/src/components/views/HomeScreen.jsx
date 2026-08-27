import React, { useState } from "react";
import { useApp } from "../../context/AppContext";
import { WebGLOrb } from "../WebGLOrb";

export const HomeScreen = () => {
  const {
    assistantState,
    interimTranscript,
    startVoiceInput,
    stopVoiceInput,
    processQuery,
    audioLevel,
    setCurrentView
  } = useApp();

  const [textPrompt, setTextPrompt] = useState("");

  const suggestedPrompts = [
    { label: "Remind me at 5:00 PM to review tokens", action: "Remind me at 5:00 PM to review tokens" },
    { label: "What's the weather today?", action: "What's the weather today?" },
    { label: "Add task: Finalize audio shader curves", action: "Add task: Finalize audio shader curves" },
    { label: "What's on my schedule?", action: "What's on my schedule?" }
  ];

  const handleOrbClick = () => {
    if (assistantState === "listening") {
      stopVoiceInput();
    } else {
      startVoiceInput();
    }
  };

  const handlePromptSubmit = (e) => {
    e.preventDefault();
    if (textPrompt.trim()) {
      processQuery(textPrompt);
      setTextPrompt("");
    }
  };

  const getStateLabel = () => {
    if (assistantState === "listening") return "Listening...";
    if (assistantState === "thinking") return "Thinking...";
    if (assistantState === "speaking") return "Speaking...";
    return "Tap orb or say \"Hey Astra\"";
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center relative w-full max-w-[800px] mx-auto px-6 pt-24 pb-32">
      {/* Living Interactive Orb */}
      <div
        onClick={handleOrbClick}
        className={"relative rounded-full cursor-pointer transition-transform duration-300 hover:scale-105 active:scale-95 group " +
          (assistantState === "listening" ? "orb-glow-active" : assistantState === "speaking" ? "orb-glow-speaking" : "orb-glow")}
      >
        <WebGLOrb size={320} interactive={true} />

        {/* State Badge Overlay */}
        <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 px-4 py-1.5 rounded-full bg-[#1e2021]/90 backdrop-blur-md border border-white/[0.1] shadow-lg flex items-center gap-2 text-xs font-medium text-[#cabeff]">
          <span className={"w-2 h-2 rounded-full " +
            (assistantState === "listening" ? "bg-red-400 animate-ping" :
             assistantState === "thinking" ? "bg-amber-400 animate-pulse" :
             assistantState === "speaking" ? "bg-emerald-400 animate-bounce" :
             "bg-[#7c5cfc]")
          } />
          <span>{assistantState.toUpperCase()}</span>
        </div>
      </div>

      {/* Dynamic Status / Speech Transcription */}
      <div className="mt-12 text-center max-w-xl w-full min-h-[90px] flex flex-col items-center justify-center">
        {interimTranscript ? (
          <p className="text-xl md:text-2xl text-white font-medium leading-relaxed animate-pulse">
            "{interimTranscript}"
          </p>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <h2 className="text-xl md:text-2xl text-[#e2e2e3] font-medium tracking-tight">
              {getStateLabel()}
            </h2>
            <p className="text-sm text-[#938ea1]">
              Calm, ambient voice intelligence designed for your workflow
            </p>
          </div>
        )}

        {/* Waveform Bars when active */}
        {(assistantState === "listening" || assistantState === "speaking") && (
          <div className="flex items-center gap-1.5 mt-4 h-8">
            <div className="w-1 bg-[#7c5cfc] rounded-full animate-wave-1" style={{ height: Math.max(8, audioLevel * 40) + 'px' }} />
            <div className="w-1 bg-[#947dff] rounded-full animate-wave-2" style={{ height: Math.max(12, audioLevel * 50) + 'px' }} />
            <div className="w-1 bg-[#cabeff] rounded-full animate-wave-3" style={{ height: Math.max(16, audioLevel * 60) + 'px' }} />
            <div className="w-1 bg-[#947dff] rounded-full animate-wave-4" style={{ height: Math.max(12, audioLevel * 50) + 'px' }} />
            <div className="w-1 bg-[#7c5cfc] rounded-full animate-wave-5" style={{ height: Math.max(8, audioLevel * 40) + 'px' }} />
          </div>
        )}
      </div>

      {/* Suggested Prompt Chips */}
      <div className="mt-8 flex flex-wrap justify-center gap-2.5 max-w-xl">
        {suggestedPrompts.map((p, idx) => (
          <button
            key={idx}
            onClick={() => processQuery(p.action)}
            className="glass-pill px-4 py-2 rounded-full text-xs md:text-sm text-[#c9c4d8] hover:text-white transition-all duration-200 active:scale-95 cursor-pointer"
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Text Input Alternate */}
      <form onSubmit={handlePromptSubmit} className="mt-8 w-full max-w-md relative">
        <input
          type="text"
          value={textPrompt}
          onChange={(e) => setTextPrompt(e.target.value)}
          placeholder="Ask or type a voice command..."
          className="w-full bg-[#1e2021]/80 border border-white/[0.08] rounded-full pl-5 pr-12 py-3.5 text-sm text-[#e2e2e3] placeholder-[#938ea1] focus:outline-none focus:border-[#7c5cfc]/50 focus:ring-1 focus:ring-[#7c5cfc]/50 backdrop-blur-md"
        />
        <button
          type="submit"
          className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-[#7c5cfc] hover:bg-[#6b47fc] text-white flex items-center justify-center transition-transform active:scale-90 cursor-pointer"
        >
          <span className="material-symbols-outlined text-sm">send</span>
        </button>
      </form>
    </div>
  );
};
