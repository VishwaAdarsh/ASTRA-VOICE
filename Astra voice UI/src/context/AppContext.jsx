import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { voiceService } from '../services/voiceService';
import { astraApi, generateRequestId } from '../services/api';
import confetti from 'canvas-confetti';

const AppContext = createContext(null);

export const AppProvider = ({ children }) => {
  const [currentView, setCurrentView] = useState('home');
  const [assistantState, setAssistantState] = useState('idle'); // 'idle' | 'listening' | 'thinking' | 'speaking'
  const [commandStatus, setCommandStatus] = useState('IDLE'); // 'IDLE' | 'SUBMITTING' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'INTERRUPTED'
  const [interimTranscript, setInterimTranscript] = useState('');
  const [audioLevel, setAudioLevel] = useState(0);

  const [reminders, setReminders] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [notes, setNotes] = useState([]);
  const [messages, setMessages] = useState([
    {
      id: 'msg-1',
      sender: 'astra',
      text: 'Good morning! I am Astra, your desktop personal AI assistant. How can I help you today?',
      timestamp: '09:00 AM',
    },
  ]);
  const [settings, setSettings] = useState({
    voiceName: 'Aura',
    speechRate: 1.0,
    speechPitch: 1.0,
    wakeWord: true,
    soundEffects: true,
    autoSpeak: true,
    theme: 'dark',
    shaderIntensity: 1.0,
    orbColor: '#7c5cfc',
    llm_provider: 'mock',
    permissions_mode: 'NORMAL',
  });
  const [healthStatus, setHealthStatus] = useState({ status: 'HEALTHY', subsystems: {} });
  const [isBackendConnected, setIsBackendConnected] = useState(false);
  const [connectionState, setConnectionState] = useState(astraApi.connectionState);

  const [confirmationModal, setConfirmationModal] = useState({
    isOpen: false,
    title: '',
    description: '',
    itemDetails: null,
    onConfirm: null,
    onCancel: null,
    timer: 6,
  });

  const [toastMessage, setToastMessage] = useState(null);

  const showToast = useCallback((msg, icon = 'check_circle') => {
    setToastMessage({ text: msg, icon });
    setTimeout(() => setToastMessage(null), 3500);
  }, []);

  // Fetch initial data from Python ASTRA Engine
  const loadBackendData = useCallback(async () => {
    try {
      const [healthData, tasksData, autoData, memData, cfgData] = await Promise.all([
        astraApi.getHealth().catch(() => null),
        astraApi.getTasks().catch(() => []),
        astraApi.getAutomations().catch(() => []),
        astraApi.getMemories().catch(() => []),
        astraApi.getSettings().catch(() => null),
      ]);

      if (healthData) {
        setHealthStatus(healthData);
        setIsBackendConnected(true);
      }
      if (tasksData) setTasks(tasksData);
      if (autoData) setReminders(autoData);
      if (memData) setNotes(memData);
      if (cfgData) setSettings((prev) => ({ ...prev, ...cfgData }));
    } catch (e) {
      console.warn('[AppContext] Could not connect to Python ASTRA Engine:', e);
      setIsBackendConnected(false);
    }
  }, []);

  // Initialize WebSocket and backend connection on mount
  useEffect(() => {
    astraApi.initWebSocket();
    loadBackendData();

    // Listen to real-time events from Python ASTRA Engine
    const unbindConn = astraApi.on('connection_changed', (data) => {
      setIsBackendConnected(data.connected);
      setConnectionState(data.state);
      if (data.connected) {
        showToast('Connected to ASTRA Engine', 'cloud_done');
        loadBackendData();
      } else {
        showToast('ASTRA Engine Offline', 'cloud_off');
        setAssistantState('idle');
        setCommandStatus((prev) => {
          if (prev === 'PROCESSING' || prev === 'SUBMITTING') {
            const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            setMessages((msgs) => [
              ...msgs,
              {
                id: 'msg-' + Date.now(),
                sender: 'astra',
                text: 'Connection interrupted while processing your request. Reconnecting...',
                timestamp: timeStr,
              },
            ]);
            return 'INTERRUPTED';
          }
          return 'IDLE';
        });
      }
    });

    const unbindBrainStarted = astraApi.on('BRAIN_STARTED', (data) => {
      setAssistantState('thinking');
      setCommandStatus('PROCESSING');
      if (data.input) setInterimTranscript(`Processing: "${data.input}"`);
    });

    const unbindBrainCompleted = astraApi.on('BRAIN_COMPLETED', (data) => {
      setAssistantState('idle');
      setCommandStatus('COMPLETED');
      setInterimTranscript('');
      if (data.response) {
        const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const astraMsg = {
          id: 'msg-' + Date.now(),
          sender: 'astra',
          text: data.response,
          timestamp: timeStr,
          widgetType: data.widgetType,
          widgetData: data.widgetData,
        };
        setMessages((prev) => [...prev, astraMsg]);
      }
    });

    const unbindVoiceState = astraApi.on('VOICE_STATE_CHANGED', (data) => {
      if (data.state) setAssistantState(data.state);
    });

    const unbindHealth = astraApi.on('HEALTH_CHANGED', (data) => {
      if (data.data) setHealthStatus((prev) => ({ ...prev, subsystems: data.data }));
    });

    const unbindError = astraApi.on('ERROR_OCCURRED', (data) => {
      setAssistantState('idle');
      setCommandStatus('FAILED');
      const errMessage = (data.error && data.error.message) || data.message || 'Engine Error';
      showToast(errMessage, 'error');
    });

    return () => {
      unbindConn();
      unbindBrainStarted();
      unbindBrainCompleted();
      unbindVoiceState();
      unbindHealth();
      unbindError();
    };
  }, [loadBackendData, showToast]);

  // Hook local voice service callbacks
  useEffect(() => {
    voiceService.onAudioLevelChange = (lvl) => setAudioLevel(lvl);
    voiceService.onStateChange = (st) => setAssistantState(st);
  }, []);

  // Process User Command through Python Engine
  const processQuery = useCallback(async (queryText) => {
    if (!queryText || !queryText.trim()) return;

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const userMsg = {
      id: 'msg-' + Date.now(),
      sender: 'user',
      text: queryText,
      timestamp: timeStr,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInterimTranscript('');

    if (!isBackendConnected) {
      // Truthful offline notification - no fake local assistant brain
      setCommandStatus('FAILED');
      setAssistantState('idle');
      const astraMsg = {
        id: 'msg-' + (Date.now() + 1),
        sender: 'astra',
        text: 'ASTRA Engine is currently offline. Please ensure the Python backend server is running.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, astraMsg]);
      showToast('ASTRA Engine Offline', 'cloud_off');
      return;
    }

    setAssistantState('thinking');
    setCommandStatus('SUBMITTING');

    try {
      const reqId = generateRequestId();
      await astraApi.sendCommand(queryText, reqId);
      // Processing state will be updated by BRAIN_STARTED and BRAIN_COMPLETED WebSocket events
    } catch (err) {
      console.error('[AppContext] Error sending command:', err);
      setAssistantState('idle');
      setCommandStatus('FAILED');
      showToast(err.message || 'Error communicating with ASTRA Engine', 'error');
    }
  }, [isBackendConnected, showToast]);

  // Voice Listening trigger
  const startVoiceInput = useCallback(async () => {
    if (!isBackendConnected) {
      showToast('Voice input unavailable: ASTRA Engine is offline', 'cloud_off');
      return;
    }

    voiceService.stopSpeaking();
    setAssistantState('listening');
    setInterimTranscript('Listening...');

    try {
      await astraApi.triggerVoiceListen();
    } catch (e) {
      setAssistantState('idle');
      setInterimTranscript('');
      showToast('Error triggering voice listener: ' + (e.message || 'unavailable'), 'mic_off');
    }
  }, [isBackendConnected, showToast]);

  const stopVoiceInput = useCallback(() => {
    voiceService.stopListening();
    if (isBackendConnected) {
      astraApi.triggerVoiceStop().catch(() => {});
    }
    setAssistantState('idle');
    setInterimTranscript('');
  }, [isBackendConnected]);

  const speakText = useCallback((text) => {
    if (isBackendConnected) {
      astraApi.triggerVoiceSpeak(text).catch(() => {
        voiceService.speak(text, settings);
      });
    } else {
      voiceService.speak(text, settings);
    }
  }, [isBackendConnected, settings]);

  // Task Engine CRUD - Authoritative Backend Only
  const addTask = async (tsk) => {
    if (!isBackendConnected) {
      showToast('Cannot add task: ASTRA Engine is offline', 'cloud_off');
      return;
    }

    try {
      const newTsk = await astraApi.createTask(tsk.title, tsk.category);
      setTasks((prev) => [newTsk, ...prev]);
      showToast('Task submitted to ASTRA Task Engine');
      confetti({ particleCount: 20, spread: 45, origin: { y: 0.85 } });
    } catch (e) {
      showToast('Error creating task: ' + (e.message || 'Failed'), 'error');
    }
  };

  const toggleTask = (id) => {
    setTasks((prev) =>
      prev.map((t) => (t.id === id ? { ...t, completed: !t.completed } : t))
    );
  };

  const deleteTask = (id) => {
    setTasks((prev) => prev.filter((t) => t.id !== id));
    showToast('Task removed', 'delete');
  };

  // Automations CRUD - Authoritative Backend Only
  const addReminder = async (rem) => {
    if (!isBackendConnected) {
      showToast('Cannot create reminder: ASTRA Engine is offline', 'cloud_off');
      return;
    }

    try {
      const newRem = await astraApi.createAutomation(rem.title, rem.time || '09:00', rem.title);
      setReminders((prev) => [newRem, ...prev]);
      showToast('Automation scheduled in ASTRA Engine');
    } catch (e) {
      showToast('Error creating automation: ' + (e.message || 'Failed'), 'error');
    }
  };

  const toggleReminder = (id) => {
    setReminders((prev) =>
      prev.map((r) => (r.id === id ? { ...r, completed: !r.completed } : r))
    );
  };

  const deleteReminder = (id) => {
    setReminders((prev) => prev.filter((r) => r.id !== id));
    showToast('Reminder deleted', 'delete');
  };

  // Memory CRUD - Authoritative Backend Only
  const addNote = async (not) => {
    if (!isBackendConnected) {
      showToast('Cannot save note: ASTRA Engine is offline', 'cloud_off');
      return;
    }

    try {
      const newMem = await astraApi.addMemory(not.body || not.title);
      setNotes((prev) => [newMem, ...prev]);
      showToast('Fact remembered by ASTRA Memory Subsystem');
    } catch (e) {
      showToast('Error storing memory: ' + (e.message || 'Failed'), 'error');
    }
  };

  const deleteNote = (id) => {
    setNotes((prev) => prev.filter((n) => n.id !== id));
    showToast('Note removed', 'delete');
  };

  return (
    <AppContext.Provider
      value={{
        currentView,
        setCurrentView,
        assistantState,
        setAssistantState,
        commandStatus,
        setCommandStatus,
        interimTranscript,
        audioLevel,
        reminders,
        addReminder,
        toggleReminder,
        deleteReminder,
        tasks,
        addTask,
        toggleTask,
        deleteTask,
        notes,
        addNote,
        deleteNote,
        messages,
        settings,
        setSettings,
        healthStatus,
        isBackendConnected,
        connectionState,
        processQuery,
        startVoiceInput,
        stopVoiceInput,
        speakText,
        confirmationModal,
        setConfirmationModal,
        toastMessage,
        showToast,
        loadBackendData,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => useContext(AppContext);
