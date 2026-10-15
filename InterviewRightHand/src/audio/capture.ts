/**
 * Captures system loopback (via getDisplayMedia audio: loopback on Windows)
 * and microphone. Uses Web Speech API for low-latency RU/EN transcripts in MVP.
 * Chunks are sent to main as transcripts only — never answers.
 */

type Role = 'interviewer' | 'you';

type CaptureHandlers = {
  onTranscript: (payload: {
    role: Role;
    text: string;
    isFinal: boolean;
  }) => void;
  onError?: (message: string) => void;
};

type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: any) => void) | null;
  onerror: ((event: any) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

function getSpeechRecognition(): (new () => SpeechRecognitionLike) | null {
  const w = window as any;
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export class DualCapture {
  private micStream: MediaStream | null = null;
  private loopStream: MediaStream | null = null;
  private micRec: SpeechRecognitionLike | null = null;
  private loopRec: SpeechRecognitionLike | null = null;
  private running = false;
  private lang = 'ru-RU';

  constructor(private handlers: CaptureHandlers) {}

  setLang(language: string) {
    this.lang = language === 'en' ? 'en-US' : 'ru-RU';
  }

  async start() {
    if (this.running) return;
    this.running = true;

    try {
      this.micStream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: false,
      });
    } catch (e: any) {
      this.handlers.onError?.(
        `Микрофон недоступен: ${e?.message || e}. Проверьте разрешения Windows.`
      );
    }

    try {
      // Electron displayMedia handler supplies loopback audio on Windows.
      this.loopStream = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: true,
      } as any);
      // We only need audio; stop video tracks to reduce load.
      this.loopStream.getVideoTracks().forEach((t) => t.stop());
    } catch (e: any) {
      this.handlers.onError?.(
        `Системный звук недоступен: ${e?.message || e}. Можно вводить вопрос вручную.`
      );
    }

    this.micRec = this.startRecognizer('you');
    this.loopRec = this.startRecognizer('interviewer');
  }

  private startRecognizer(role: Role): SpeechRecognitionLike | null {
    const Ctor = getSpeechRecognition();
    if (!Ctor) {
      this.handlers.onError?.(
        'Web Speech API недоступен в этой среде. Используйте ручной ввод вопроса.'
      );
      return null;
    }
    const rec = new Ctor();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = this.lang;
    rec.onresult = (event: any) => {
      let interim = '';
      let finalText = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const r = event.results[i];
        if (r.isFinal) finalText += r[0].transcript;
        else interim += r[0].transcript;
      }
      if (interim) {
        this.handlers.onTranscript({ role, text: interim, isFinal: false });
      }
      if (finalText) {
        this.handlers.onTranscript({
          role,
          text: finalText.trim(),
          isFinal: true,
        });
      }
    };
    rec.onerror = (event: any) => {
      if (event?.error === 'no-speech' || event?.error === 'aborted') return;
      this.handlers.onError?.(`STT (${role}): ${event?.error || 'error'}`);
    };
    rec.onend = () => {
      if (this.running) {
        try {
          rec.start();
        } catch {
          /* ignore restart races */
        }
      }
    };
    try {
      rec.start();
    } catch (e: any) {
      this.handlers.onError?.(`Не удалось стартовать STT (${role}): ${e?.message || e}`);
    }
    return rec;
  }

  async stop() {
    this.running = false;
    try {
      this.micRec?.stop();
    } catch {
      /* ignore */
    }
    try {
      this.loopRec?.stop();
    } catch {
      /* ignore */
    }
    this.micRec = null;
    this.loopRec = null;
    this.micStream?.getTracks().forEach((t) => t.stop());
    this.loopStream?.getTracks().forEach((t) => t.stop());
    this.micStream = null;
    this.loopStream = null;
  }
}
