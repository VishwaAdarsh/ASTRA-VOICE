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
    const isQtWebEngine = typeof navigator !== 'undefined' && /QtWebEngine/i.test(navigator.userAgent);
    const SpeechRecognition = isQtWebEngine ? null : (window.SpeechRecognition || window.webkitSpeechRecognition);
    if (!SpeechRecognition) {
      if (onError) onError('Voice input is handled natively by ASTRA Python Engine. You can speak into your microphone or type prompts.');
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

