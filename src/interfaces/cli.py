"""
ASTRA Terminal CLI Interface (Phase 1).
Provides an interactive command-line interface for testing and interacting with ASTRA.
"""

import sys
from src.core.lifecycle import SystemLifecycle
from src.voice.manager import VoiceManager
from src.voice.models import VoiceState

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def run_voice_mode(agent, voice_manager: VoiceManager) -> None:
    """Run interactive voice session mode."""
    diag = voice_manager.get_diagnostics()
    print("\n--- ASTRA Voice Mode ---")
    print(f"Microphone: {diag.device_name} (Status: {diag.status})")
    print(f"STT Provider: {voice_manager.voice_config.stt_provider}")
    print(f"TTS Provider: {voice_manager.voice_config.tts_provider}")
    print("Press Enter to speak a command, or type 'exit' to return to CLI text mode.\n")

    while True:
        try:
            cmd = input("[Voice Mode - Press Enter to Speak] > ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if cmd.lower() in ("exit", "quit", "q", "back"):
            print("Returning to text CLI mode...\n")
            break

        print("\n🎙 Listening... Speak now...")
        response, result = voice_manager.listen_and_process(duration_seconds=3.0)
        print(f"ASTRA > {response}\n")


def run_cli(start_in_voice_mode: bool = False) -> None:
    """Run interactive terminal CLI session for ASTRA."""
    lifecycle = SystemLifecycle()
    agent = lifecycle.startup()
    voice_manager = VoiceManager(agent=agent, config=lifecycle.config)

    print("\n========================================")
    print("              ASTRA                     ")
    print("      Personal AI Assistant (Phase 2)    ")
    print("========================================\n")
    print("Type 'voice' for voice mode, 'help' for commands, or 'exit' to exit.\n")

    if start_in_voice_mode:
        run_voice_mode(agent, voice_manager)

    try:
        while True:
            try:
                user_input = input("You > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting ASTRA...")
                break

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break

            if user_input.lower() in ("voice", "v", "listen"):
                run_voice_mode(agent, voice_manager)
                continue

            if user_input.lower() in ("help", "?"):
                print("\nASTRA Phase 2 Supported Commands:")
                print("  - voice                       (Launch voice mode)")
                print("  - open calculator")
                print("  - open notepad")
                print("  - open chrome")
                print("  - open downloads")
                print("  - open documents")
                print("  - open youtube")
                print("  - open google")
                print("  - show system information\n")
                continue

            print()
            response_text, result = agent.process_command(user_input)
            print(f"ASTRA > {response_text}\n")

    finally:
        lifecycle.shutdown()


if __name__ == "__main__":
    run_cli()

