import React, { useEffect, useState } from "react";
import { useApp } from "../context/AppContext";

export const ConfirmationBottomSheet = () => {
  const { confirmationModal, setConfirmationModal } = useApp();
  const [secondsLeft, setSecondsLeft] = useState(6);

  useEffect(() => {
    if (!confirmationModal.isOpen) return;

    setSecondsLeft(confirmationModal.timer || 6);
    const interval = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          if (confirmationModal.onConfirm) confirmationModal.onConfirm();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [confirmationModal.isOpen]);

  if (!confirmationModal.isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 backdrop-blur-sm p-4 animate-fade-in">
      <div className="w-full max-w-[640px] glass-panel rounded-3xl border border-white/[0.12] p-6 md:p-8 shadow-2xl space-y-6 animate-slide-up">
        {/* Handle */}
        <div className="w-12 h-1.5 bg-white/20 rounded-full mx-auto" />

        {/* Icon & Title */}
        <div className="flex flex-col items-center text-center space-y-3">
          <div className="w-14 h-14 rounded-full bg-[#7c5cfc]/20 text-[#cabeff] flex items-center justify-center orb-glow">
            <span className="material-symbols-outlined text-3xl">notifications_active</span>
          </div>

          <h2 className="text-xl font-bold text-white tracking-tight">
            {confirmationModal.title || "Confirmation Required"}
          </h2>
          <p className="text-sm text-[#c9c4d8] max-w-md">
            {confirmationModal.description}
          </p>
        </div>

        {/* Action Item Details Card */}
        {confirmationModal.itemDetails && (
          <div className="p-4 rounded-2xl bg-white/[0.04] border border-white/[0.06] flex items-center justify-between text-xs">
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-[#cabeff]">event_available</span>
              <div>
                <div className="font-semibold text-white text-sm">{confirmationModal.itemDetails.title}</div>
                <div className="text-[#938ea1]">{confirmationModal.itemDetails.time}</div>
              </div>
            </div>
            <span className="px-2.5 py-1 rounded-full bg-[#7c5cfc]/20 text-[#cabeff] font-medium">
              {confirmationModal.itemDetails.category || "Auto"}
            </span>
          </div>
        )}

        {/* Progress Bar & Actions */}
        <div className="space-y-4">
          <div className="w-full bg-white/[0.06] h-1.5 rounded-full overflow-hidden">
            <div
              className="bg-[#7c5cfc] h-full transition-all duration-1000 ease-linear"
              style={{ width: (secondsLeft / 6) * 100 + "%" }}
            />
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => confirmationModal.onCancel && confirmationModal.onCancel()}
              className="flex-1 py-3 rounded-2xl bg-white/[0.06] hover:bg-white/[0.1] text-xs font-semibold text-[#e2e2e3] transition-all cursor-pointer active:scale-98"
            >
              Cancel
            </button>
            <button
              onClick={() => confirmationModal.onConfirm && confirmationModal.onConfirm()}
              className="flex-1 py-3 rounded-2xl bg-[#7c5cfc] hover:bg-[#6b47fc] text-xs font-semibold text-white transition-all cursor-pointer active:scale-98 shadow-[0_0_20px_rgba(124,92,252,0.4)] flex items-center justify-center gap-2"
            >
              <span>Confirm ({secondsLeft}s)</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
