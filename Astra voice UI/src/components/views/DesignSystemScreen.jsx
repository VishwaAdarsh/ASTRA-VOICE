import React from "react";
import { useApp } from "../../context/AppContext";
import { WebGLOrb } from "../WebGLOrb";

export const DesignSystemScreen = () => {
  const { settings, setSettings, showToast } = useApp();

  const colorTokens = [
    { name: "Primary", token: "--color-primary", hex: "#cabeff", desc: "Key accents & active badges" },
    { name: "Custom Primary", token: "--color-primary-custom", hex: "#7c5cfc", desc: "Living orb source light" },
    { name: "Surface Base", token: "--color-surface", hex: "#121415", desc: "Deep dark ambient background" },
    { name: "Surface Container", token: "--color-surface-container", hex: "#1e2021", desc: "Glass cards & dock containers" },
    { name: "Surface Container High", token: "--color-surface-container-high", hex: "#282a2b", desc: "Elevated modals & popups" },
    { name: "On Surface", token: "--color-on-surface", hex: "#e2e2e3", desc: "Primary text & high contrast" },
    { name: "On Surface Variant", token: "--color-on-surface-variant", hex: "#c9c4d8", desc: "Secondary text & descriptions" },
    { name: "Outline Variant", token: "--color-outline-variant", hex: "#484555", desc: "Glassmorphic 1px borders" }
  ];

  const typographyTokens = [
    { label: "display-orb", spec: "Plus Jakarta Sans 48px / 600 (-0.02em)", sample: "Astra Calm Presence" },
    { label: "headline-lg", spec: "Plus Jakarta Sans 32px / 600 (-0.01em)", sample: "Reminders & Tasks" },
    { label: "body-xl", spec: "Plus Jakarta Sans 20px / 400 (Line Height 32px)", sample: "Serene living light ambient companion" },
    { label: "body-md", spec: "Plus Jakarta Sans 16px / 400 (Line Height 24px)", sample: "Optimized for distance legibility and minimal eye strain" },
    { label: "label-caps", spec: "Plus Jakarta Sans 12px / 700 (+0.1em)", sample: "VOICE ASSISTANT SYSTEM" }
  ];

  const orbPalette = ["#7c5cfc", "#3b82f6", "#10b981", "#ec4899", "#f59e0b", "#8b5cf6"];

  const copyToken = (val) => {
    navigator.clipboard.writeText(val);
    showToast("Copied to clipboard: " + val);
  };

  return (
    <div className="flex-1 w-full max-w-[800px] mx-auto px-6 pt-24 pb-32 space-y-10">
      <div>
        <h1 className="text-3xl font-bold text-[#e2e2e3] tracking-tight">Design System & Shader Studio</h1>
        <p className="text-sm text-[#938ea1] mt-1">Astra Design System specifications, tokens, and WebGL shader parameters</p>
      </div>

      {/* Interactive Shader Customizer */}
      <section className="glass-panel p-6 md:p-8 rounded-3xl border border-white/[0.08] space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-white">Living Orb WebGL Shader</h2>
            <p className="text-xs text-[#938ea1]">Custom 2D Fragment Shader with Audio-Reactivity</p>
          </div>
          <div className="w-16 h-16 rounded-full overflow-hidden flex items-center justify-center orb-glow">
            <WebGLOrb size={64} interactive={false} />
          </div>
        </div>

        {/* Color Palette Switcher */}
        <div>
          <label className="block text-xs uppercase font-semibold tracking-wider text-[#938ea1] mb-2">
            Orb Primary Light Source Color
          </label>
          <div className="flex items-center gap-3">
            {orbPalette.map((c) => (
              <button
                key={c}
                onClick={() => setSettings((p) => ({ ...p, orbColor: c }))}
                style={{ backgroundColor: c }}
                className={"w-9 h-9 rounded-full transition-transform cursor-pointer " +
                  (settings.orbColor === c ? "ring-4 ring-white/40 scale-110" : "hover:scale-105 opacity-80 hover:opacity-100")}
              />
            ))}
          </div>
        </div>
      </section>

      {/* Color Tokens */}
      <section className="space-y-4">
        <h2 className="text-lg font-bold text-white">Color Palette & Tokens</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {colorTokens.map((item, i) => (
            <div
              key={i}
              onClick={() => copyToken(item.hex)}
              className="glass-panel p-4 rounded-2xl border border-white/[0.06] flex items-center justify-between hover:border-[#7c5cfc]/40 cursor-pointer transition-all"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl border border-white/10 shadow-inner" style={{ backgroundColor: item.hex }} />
                <div>
                  <div className="text-sm font-semibold text-white">{item.name}</div>
                  <div className="text-xs text-[#938ea1]">{item.desc}</div>
                </div>
              </div>
              <code className="text-xs font-mono text-[#cabeff] px-2 py-1 rounded bg-white/[0.04]">
                {item.hex}
              </code>
            </div>
          ))}
        </div>
      </section>

      {/* Typography Scale */}
      <section className="space-y-4">
        <h2 className="text-lg font-bold text-white">Typography Scale (Plus Jakarta Sans)</h2>
        <div className="glass-panel p-6 rounded-3xl border border-white/[0.08] divide-y divide-white/[0.06]">
          {typographyTokens.map((t, i) => (
            <div key={i} className="py-4 first:pt-0 last:pb-0">
              <div className="flex items-center justify-between text-xs text-[#938ea1] mb-1 font-mono">
                <span>{t.label}</span>
                <span>{t.spec}</span>
              </div>
              <div className="text-[#e2e2e3] font-medium tracking-tight">
                {t.sample}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};
