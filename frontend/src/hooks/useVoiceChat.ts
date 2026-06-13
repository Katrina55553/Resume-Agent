import { useState, useRef, useCallback, useEffect } from 'react';

interface UseVoiceChatOptions {
  lang?: string;
  onResult?: (text: string) => void;
  onTtsEnd?: () => void;
}

export function useVoiceChat(options: UseVoiceChatOptions = {}) {
  const { lang = 'zh-CN', onResult, onTtsEnd } = options;

  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [isSupported] = useState(() => {
    const hasAPI = !!(window.SpeechRecognition || window.webkitSpeechRecognition);
    const isSecure = window.isSecureContext;
    return hasAPI && isSecure;
  });

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const ttsEndCallbackRef = useRef(onTtsEnd);

  useEffect(() => {
    ttsEndCallbackRef.current = onTtsEnd;
  }, [onTtsEnd]);

  const startListening = useCallback(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    const recognition = new SpeechRecognition();
    recognition.lang = lang;
    recognition.continuous = false;
    recognition.interimResults = true;

    recognition.onstart = () => {
      setIsListening(true);
      setTranscript('');
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = '';
      let final = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const t = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          final += t;
        } else {
          interim += t;
        }
      }
      setTranscript(final || interim);
      if (final && onResult) {
        onResult(final);
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      console.error('[Voice] 语音识别错误:', event.error, event.message);
      setIsListening(false);
      if (event.error === 'not-allowed') {
        alert('请允许浏览器使用麦克风权限');
      } else if (event.error === 'network') {
        alert('语音识别需要网络连接，且必须通过 HTTPS 访问');
      }
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;
    recognition.start();
  }, [lang, onResult]);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  const speak = useCallback((text: string) => {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang;
    utterance.rate = 1.0;

    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => {
      setIsSpeaking(false);
      ttsEndCallbackRef.current?.();
    };
    utterance.onerror = () => setIsSpeaking(false);

    window.speechSynthesis.speak(utterance);
  }, [lang]);

  const stopSpeaking = useCallback(() => {
    window.speechSynthesis?.cancel();
    setIsSpeaking(false);
  }, []);

  const toggleVoice = useCallback(() => {
    setVoiceEnabled((v) => {
      if (v) {
        stopListening();
        stopSpeaking();
      }
      return !v;
    });
  }, [stopListening, stopSpeaking]);

  return {
    isListening,
    transcript,
    isSpeaking,
    voiceEnabled,
    isSupported,
    startListening,
    stopListening,
    speak,
    stopSpeaking,
    toggleVoice,
  };
}
