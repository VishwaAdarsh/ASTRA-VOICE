import React from "react";
import { useApp } from "../../context/AppContext";

export const SettingsScreen = () => {
  const { settings, setSettings, resetData, showToast } = useApp();

  const handleSettingChange = (key, val) => {
    setSettings((prev) => ({ ...prev, [key]: val }));
  };

  const voices = [
    { id: "Aura", name: "Aura (Serene & Crisp - Default)" },
    { id: "Breeze", name: "Breeze (Deep & Grounded)" },
    { id: "Cove", name: "Cove (Warm & Gentle)" },
    { id: "Juniper", name: "Juniper (Bright & Expressive)" }
  ];

  return (
    <div className="flex-1 w-full max-w-[800px] mx-auto px-6 pt-24 pb-32">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-[#e2e2e3] tracking-tight">Settings</h1>
        <p className="text-sm text-[#938ea1] mt-1">Configure your Astra voice assistant & ambient UI</p>
      </div>

      <div className="space-y-6">
        {/* Voice Preferences */}
        <section className="glass-panel p-6 rounded-3xl border border-white/[0.08] space-y-5">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-[#cabeff] text-2xl">record_voice_over</span>
            <div>
              <h2 className="text-base font-bold text-white">Voice Model & Output</h2>
              <p className="text-xs text-[#938ea1]">Personalize Astra's speech persona</p>
            </div>
          </div>

          <div className="space-y-4 pt-2">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#938ea1] mb-2">
                Assistant Voice
              </label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {voices.map((v) => (
                  <button
                    key={v.id}
                    onClick={() => handleSettingChange("voiceName", v.id)}
                    className={"p-3 rounded-xl text-left text-xs font-medium border transition-all cursor-pointer " +
                      (settings.voiceName === v.id
                        ? "bg-[#7c5cfc]/20 border-[#7c5cfc] text-white shadow-sm"
                        : "bg-white/[0.02] border-white/[0.06] text-[#938ea1] hover:text-white")}
                  >
                    {v.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Speech Rate Slider */}
            <div>
              <div className="flex justify-between text-xs text-[#938ea1] mb-1.5 font-medium">
                <span>Speaking Rate ({settings.speechRate}x)</span>
                <span>Normal: 1.0x</span>
              </div>
              <input
                type="range"
                min="0.75"
                max="1.5"
                step="0.05"
                value={settings.speechRate}
                onChange={(e) => handleSettingChange("speechRate", parseFloat(e.target.value))}
                className="w-full accent-[#7c5cfc] cursor-pointer"
              />
            </div>

            {/* Speech Pitch Slider */}
            <div>
              <div className="flex justify-between text-xs text-[#938ea1] mb-1.5 font-medium">
                <span>Voice Pitch ({settings.speechPitch}x)</span>
                <span>Default: 1.0x</span>
              </div>
              <input
                type="range"
                min="0.7"
                max="1.3"
                step="0.05"
                value={settings.speechPitch}
                onChange={(e) => handleSettingChange("speechPitch", parseFloat(e.target.value))}
                className="w-full accent-[#7c5cfc] cursor-pointer"
              />
            </div>
          </div>
        </section>

        {/* Interaction Controls */}
        <section className="glass-panel p-6 rounded-3xl border border-white/[0.08] space-y-4">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-[#cabeff] text-2xl">hearing</span>
            <div>
              <h2 className="text-base font-bold text-white">Listening & Triggers</h2>
              <p className="text-xs text-[#938ea1]">Wake word and speech triggers</p>
            </div>
          </div>

          <div className="divide-y divide-white/[0.06] pt-1">
            <div className="flex items-center justify-between py-3">
              <div>
                <div className="text-sm font-medium text-[#e2e2e3]">Auto-Speak Responses</div>
                <div className="text-xs text-[#938ea1]">Read replies aloud automatically</div>
              </div>
              <input
                type="checkbox"
                checked={settings.autoSpeak}
                onChange={(e) => handleSettingChange("autoSpeak", e.target.checked)}
                className="w-5 h-5 accent-[#7c5cfc] cursor-pointer"
              />
            </div>

            <div className="flex items-center justify-between py-3">
              <div>
                <div className="text-sm font-medium text-[#e2e2e3]">Sound Effects</div>
                <div className="text-xs text-[#938ea1]">Play chime on state change</div>
              </div>
              <input
                type="checkbox"
                checked={settings.soundEffects}
                onChange={(e) => handleSettingChange("soundEffects", e.target.checked)}
                className="w-5 h-5 accent-[#7c5cfc] cursor-pointer"
              />
            </div>

            <div className="flex items-center justify-between py-3">
              <div>
                <div className="text-sm font-medium text-[#e2e2e3]">Wake Word Detection ("Hey Astra")</div>
                <div className="text-xs text-[#938ea1]">Continuous passive listening mode</div>
              </div>
              <input
                type="checkbox"
                checked={settings.wakeWord}
                onChange={(e) => handleSettingChange("wakeWord", e.target.checked)}
                className="w-5 h-5 accent-[#7c5cfc] cursor-pointer"
              />
            </div>
          </div>
        </section>

        {/* Data & Reset */}
        <section className="glass-panel p-6 rounded-3xl border border-white/[0.08] flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-white">Reset Local Data</h3>
            <p className="text-xs text-[#938ea1]">Restore initial reminders, tasks, notes, and messages</p>
          </div>
          <button
            onClick={resetData}
            className="px-4 py-2 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-300 border border-red-500/30 text-xs font-semibold transition-all cursor-pointer"
          >
            Reset All
          </button>
        </section>
      </div>
    </div>
  );
};
