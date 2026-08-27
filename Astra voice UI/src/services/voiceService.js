// Voice, Speech & Audio Analyzer Service for Astra Voice Assistant

class VoiceService {
  constructor() {
    this.recognition = null;
    this.synth = typeof window !== 'undefined' ? window.speechSynthesis : null;
    this.audioContext = null;
    this.analyser = null;
    this.microphone = null;
    this.dataArray = null;
    this.isListening = false;
    this.isSpeaking = false;
    this.audioLevel = 0;
    this.onAudioLevelChange = null;
    this.onSpeechResult = null;
    this.onSpeechEnd = null;
    this.onStateChange = null;
    this.animFrame = null;
  }

  async initAudioAnalyzer() {
    try {
      if (!this.audioContext) {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        this.audioContext = new AudioContext();
      }

      if (this.audioContext.state === 'suspended') {
        await this.audioContext.resume();
      }

      if (!this.microphone && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        this.analyser = this.audioContext.createAnalyser();
        this.analyser.fftSize = 256;
        this.analyser.smoothingTimeConstant = 0.8;
        this.microphone = this.audioContext.createMediaStreamSource(stream);
        this.microphone.connect(this.analyser);
        this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
      }

      this.startAudioLoop();
    } catch (err) {
      console.warn('Microphone audio context access error or permission denied:', err);
    }
  }

  startAudioLoop() {
    if (this.animFrame) cancelAnimationFrame(this.animFrame);
    
    const update = () => {
      if (this.analyser && this.dataArray && this.isListening) {
        this.analyser.getByteFrequencyData(this.dataArray);
        let sum = 0;
        for (let i = 0; i < this.dataArray.length; i++) {
          sum += this.dataArray[i];
        }
        const avg = sum / this.dataArray.length;
        this.audioLevel = Math.min(1.0, avg / 128);
      } else if (this.isSpeaking) {
        this.audioLevel = 0.4 + 0.3 * Math.sin(Date.now() * 0.01) + 0.15 * Math.cos(Date.now() * 0.02);
      } else {
        this.audioLevel = 0.05 * Math.sin(Date.now() * 0.002);
      }

      if (this.onAudioLevelChange) {
        this.onAudioLevelChange(this.audioLevel);
      }

      this.animFrame = requestAnimationFrame(update);
    };

    update();
  }

  startListening({ onInterim, onFinal, onError }) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      if (onError) onError('Speech recognition is not supported in this browser. You can type prompts directly.');
      return false;
    }

    try {
      this.initAudioAnalyzer();
      this.recognition = new SpeechRecognition();
      this.recognition.continuous = false;
      this.recognition.interimResults = true;
      this.recognition.lang = 'en-US';

      this.recognition.onstart = () => {
        this.isListening = true;
        if (this.onStateChange) this.onStateChange('listening');
      };

      this.recognition.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          } else {
            interimTranscript += event.results[i][0].transcript;
          }
        }

        if (interimTranscript && onInterim) {
          onInterim(interimTranscript);
        }

        if (finalTranscript && onFinal) {
          onFinal(finalTranscript);
        }
      };

      this.recognition.onerror = (event) => {
        console.warn('Speech recognition error:', event.error);
        this.isListening = false;
        if (onError) onError(event.error);
        if (this.onStateChange) this.onStateChange('idle');
      };

      this.recognition.onend = () => {
        this.isListening = false;
        if (this.onSpeechEnd) this.onSpeechEnd();
        if (this.onStateChange) this.onStateChange('idle');
      };

      this.recognition.start();
      return true;
    } catch (e) {
      console.error('Failed to start speech recognition:', e);
      this.isListening = false;
      return false;
    }
  }

  stopListening() {
    if (this.recognition) {
      try {
        this.recognition.stop();
      } catch (e) {}
      this.isListening = false;
    }
  }

  speak(text, { voiceName = 'Aura', pitch = 1.0, rate = 1.0, onStart, onEnd } = {}) {
    if (!this.synth) return;

    this.stopSpeaking();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.pitch = pitch;
    utterance.rate = rate;

    const voices = this.synth.getVoices();
    if (voices.length > 0) {
      const preferred = voices.find(v => 
        (voiceName === 'Aura' && (v.name.includes('Google') || v.name.includes('Natural') || v.name.includes('Samantha') || v.name.includes('Zira'))) ||
        (voiceName === 'Breeze' && (v.name.includes('David') || v.name.includes('Guy') || v.name.includes('Male'))) ||
        (voiceName === 'Cove' && (v.name.includes('Jenny') || v.name.includes('Female') || v.name.includes('Victoria'))) ||
        v.lang.startsWith('en')
      );
      if (preferred) utterance.voice = preferred;
    }

    utterance.onstart = () => {
      this.isSpeaking = true;
      if (this.onStateChange) this.onStateChange('speaking');
      if (onStart) onStart();
    };

    utterance.onend = () => {
      this.isSpeaking = false;
      if (this.onStateChange) this.onStateChange('idle');
      if (onEnd) onEnd();
    };

    utterance.onerror = () => {
      this.isSpeaking = false;
      if (this.onStateChange) this.onStateChange('idle');
      if (onEnd) onEnd();
    };

    this.synth.speak(utterance);
  }

  stopSpeaking() {
    if (this.synth && this.synth.speaking) {
      this.synth.cancel();
      this.isSpeaking = false;
      if (this.onStateChange) this.onStateChange('idle');
    }
  }

  getAvailableVoices() {
    if (!this.synth) return [];
    return this.synth.getVoices();
  }
}

export const voiceService = new VoiceService();

export function parseVoiceIntent(query) {
  const q = query.toLowerCase().trim();

  if (q.includes('remind me') || q.startsWith('reminder') || q.includes('set a reminder')) {
    let reminderText = 'Review deliverable';
    let timeText = 'Today at 5:00 PM';

    const match = q.match(/remind me to (.*?) (at|on|in|by|tomorrow|tonight)/i);
    if (match) {
      reminderText = match[1].trim();
      const timeMatch = q.substring(q.indexOf(match[2])).trim();
      timeText = timeMatch.charAt(0).toUpperCase() + timeMatch.slice(1);
    } else {
      const generic = q.replace(/remind me to |set a reminder to |remind me /i, '').trim();
      if (generic) reminderText = generic;
    }

    return {
      type: 'REMINDER_CREATE',
      data: {
        title: reminderText.charAt(0).toUpperCase() + reminderText.slice(1),
        time: timeText,
        category: 'Personal'
      },
      response: `I have prepared a reminder to "${reminderText}" for ${timeText}.`,
      requiresConfirmation: true,
      confirmPrompt: `Set reminder: "${reminderText}" for ${timeText}?`
    };
  }

  if (q.startsWith('add task') || q.startsWith('create task') || q.includes('to my tasks') || q.startsWith('add todo')) {
    const taskText = q.replace(/add task |create task |to my tasks|add todo /gi, '').trim() || 'Review design assets';
    return {
      type: 'TASK_CREATE',
      data: {
        title: taskText.charAt(0).toUpperCase() + taskText.slice(1),
        category: 'Work',
        completed: false
      },
      response: `Added "${taskText}" to your tasks list.`,
      requiresConfirmation: false
    };
  }

  if (q.includes('take a note') || q.includes('create note') || q.startsWith('note:') || q.includes('write this down')) {
    const noteBody = q.replace(/take a note |create note |note: |write this down /gi, '').trim() || 'Voice memo captured via Astra.';
    return {
      type: 'NOTE_CREATE',
      data: {
        title: 'Voice Note',
        body: noteBody.charAt(0).toUpperCase() + noteBody.slice(1),
        tags: ['Voice', 'Ambient']
      },
      response: `Saved your note: "${noteBody}".`,
      requiresConfirmation: false
    };
  }

  if (q.includes('weather') || q.includes('temperature') || q.includes('rain today')) {
    return {
      type: 'WEATHER',
      data: {
        location: 'San Francisco, CA',
        temp: '68?F',
        condition: 'Partly Cloudy',
        humidity: '48%',
        wind: '11 mph',
        forecast: [
          { day: 'Now', temp: '68?', icon: 'partly_cloudy_day' },
          { day: '3 PM', temp: '71?', icon: 'sunny' },
          { day: '6 PM', temp: '65?', icon: 'partly_cloudy_day' },
          { day: '9 PM', temp: '58?', icon: 'clear_night' }
        ]
      },
      response: 'It is currently 68?F and partly cloudy with gentle breezes in San Francisco.',
      requiresConfirmation: false
    };
  }

  if (q.includes('agenda') || q.includes('schedule') || q.includes('what do i have today') || q.includes('my day')) {
    return {
      type: 'SCHEDULE',
      data: {
        events: [
          { time: '10:00 AM', title: 'Product & Design Sync', room: 'Virtual Meet' },
          { time: '02:00 PM', title: 'Astra Voice AI Evaluation', room: 'Studio 4' },
          { time: '04:30 PM', title: 'Architecture Review', room: 'Conference B' }
        ]
      },
      response: 'You have 3 scheduled events today. Next up is Product & Design Sync at 10:00 AM.',
      requiresConfirmation: false
    };
  }

  if (q.includes('open reminders') || q.includes('show reminders')) {
    return {
      type: 'NAVIGATE',
      targetView: 'reminders',
      response: 'Opening your reminders overview.',
      requiresConfirmation: false
    };
  }

  if (q.includes('open tasks') || q.includes('open notes') || q.includes('show tasks')) {
    return {
      type: 'NAVIGATE',
      targetView: 'tasks',
      response: 'Navigating to Tasks and Notes.',
      requiresConfirmation: false
    };
  }

  if (q.includes('open settings') || q.includes('configure voice')) {
    return {
      type: 'NAVIGATE',
      targetView: 'settings',
      response: 'Here are your Astra settings and voice preferences.',
      requiresConfirmation: false
    };
  }

  const genericResponses = [
    {
      keywords: ['who are you', 'what are you', 'introduce yourself'],
      reply: 'I am Astra, your calm and intelligent ambient voice companion designed for effortless multi-tasking.'
    },
    {
      keywords: ['how are you', 'how do you feel'],
      reply: 'I am operating smoothly, focused and ready to assist you.'
    },
    {
      keywords: ['thank you', 'thanks'],
      reply: 'You are very welcome! Let me know whenever you need anything else.'
    },
    {
      keywords: ['joke', 'tell me a joke', 'funny'],
      reply: 'Why do programmers prefer dark mode? Because light attracts bugs!'
    }
  ];

  for (const item of genericResponses) {
    if (item.keywords.some(k => q.includes(k))) {
      return {
        type: 'CHAT',
        response: item.reply,
        requiresConfirmation: false
      };
    }
  }

  return {
    type: 'CHAT',
    response: `I analyzed: "${query}". I can help manage reminders, organize tasks, take notes, or check your schedule.`,
    requiresConfirmation: false
  };
}
