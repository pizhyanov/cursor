/**
 * Audio bridge: receives PCM/transcript events from renderer capture
 * and applies simple energy VAD / endpointing for interviewer channel.
 * Answers are never stored here.
 */

const SILENCE_MS = 900;
const MIN_QUESTION_CHARS = 12;

function createAudioBridge({ onPartialTranscript, onFinalQuestion, getSettings }) {
  let running = false;
  let lastPartial = { interviewer: '', you: '' };
  let silenceTimer = null;
  let pendingInterviewer = '';

  function clearSilence() {
    if (silenceTimer) {
      clearTimeout(silenceTimer);
      silenceTimer = null;
    }
  }

  function scheduleEndpoint() {
    clearSilence();
    silenceTimer = setTimeout(() => {
      const text = pendingInterviewer.trim();
      pendingInterviewer = '';
      if (text.length >= MIN_QUESTION_CHARS) {
        onFinalQuestion?.({ role: 'interviewer', text });
      }
    }, SILENCE_MS);
  }

  return {
    async start() {
      running = true;
      lastPartial = { interviewer: '', you: '' };
      pendingInterviewer = '';
    },

    async stop() {
      running = false;
      clearSilence();
      pendingInterviewer = '';
    },

    isRunning() {
      return running;
    },

    /**
     * Renderer sends either:
     * { type: 'transcript', role, text, isFinal }
     * or raw pcm metadata (reserved for future local STT).
     */
    pushPcmChunk(payload) {
      if (!running || !payload) return;
      getSettings?.();

      if (payload.type === 'transcript') {
        const role = payload.role === 'you' ? 'you' : 'interviewer';
        const text = String(payload.text || '').trim();
        if (!text) return;

        if (!payload.isFinal) {
          lastPartial[role] = text;
          onPartialTranscript?.({ role, text, isFinal: false });
          if (role === 'interviewer') {
            pendingInterviewer = text;
            scheduleEndpoint();
          }
          return;
        }

        lastPartial[role] = text;
        onPartialTranscript?.({ role, text, isFinal: true });
        if (role === 'interviewer') {
          clearSilence();
          pendingInterviewer = '';
          if (text.length >= MIN_QUESTION_CHARS) {
            onFinalQuestion?.({ role: 'interviewer', text });
          }
        }
      }
    },
  };
}

module.exports = { createAudioBridge };
