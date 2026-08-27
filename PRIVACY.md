# ASTRA — Privacy Policy & Data Management Guidelines

```text
================================================================================
                                 A S T R A
                         Privacy & Data Protection
================================================================================
```

* **Document Version:** 1.0.0
* **Status:** Authoritative Privacy Guidelines
* **Target Operating System:** Windows 10 / Windows 11

---

## 1. Core Privacy Guarantees

ASTRA is designed with strict privacy-first principles:

1. **Zero Hidden Surveillance**:
   - **No Continuous Screen Monitoring**: Screenshots and visual analysis occur ONLY when explicitly requested by the user.
   - **No Continuous Microphone Capture**: Audio recording occurs ONLY when the microphone is active via push-to-talk or explicit voice activation.
   - **No Webcam Access**: Webcam recording and camera surveillance are completely disabled and out of scope.
   - **No Location Tracking**: Continuous GPS/IP location tracking is completely disabled and out of scope.

2. **Data Minimization & Local Storage**:
   - Long-term memory, task execution logs, and proactive automations are stored locally on your machine in `data/astra_memory.db`.
   - Screenshots generated during vision analysis are stored temporarily in `data/temp_vision/` and cleaned up automatically.

---

## 2. Data Classification & Handling

| Category | Storage Location | Retention Policy | User Controls |
| :--- | :--- | :--- | :--- |
| **Voice Audio** | RAM (In-Memory Buffer) | Ephemeral (Discarded immediately after STT processing) | Voice Toggle in UI |
| **Screenshots** | `data/temp_vision/*.png` | Temporary (Cleaned up automatically on task finish) | Manual Delete / UI Clean |
| **Memories** | `data/astra_memory.db` (`memories`) | 30 Days (Configurable via `MEMORY_EXPIRATION_DAYS`) | Remember / Forget / Clear UI |
| **Task History** | `data/astra_memory.db` (`tasks`) | Persistent (SQLite audit log) | Clear History UI |
| **Automations** | `data/astra_memory.db` (`automations`) | Persistent until deleted by user | Pause / Resume / Delete UI |
| **System Logs** | `data/logs/astra.log` | Rotated at 5MB (Max 3 backups) | Manual log delete |

---

## 3. User Data Control & Deletion

Users maintain total control over stored assistant data:
- **Forget Memory**: Use the UI `MemoryPage` or command `"forget [memory_content]"` to delete specific stored facts.
- **Delete Automation**: Use `AutomationsPage` to pause or delete any proactive automation.
- **Emergency Stop**: Use `🛑 STOP ASTRA` or `🛑 STOP ALL AUTOMATIONS` at any time to immediately halt execution.
