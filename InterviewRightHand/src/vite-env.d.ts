/// <reference types="vite/client" />

export type IrhSettings = {
  openaiApiKey: string;
  openaiBaseUrl: string;
  openaiChatModel: string;
  openaiTranscribeModel: string;
  githubToken: string;
  githubRepo: string;
  githubQuestionBankPath: string;
  sendQuestionsToRepo: boolean;
  stack: string;
  language: string;
  opacity: number;
  installId: string;
};

export type TranscriptPayload = {
  role: 'interviewer' | 'you';
  text: string;
  isFinal?: boolean;
};

export type AnswerDelta = {
  section: string;
  text?: string;
  brief?: string;
  detailed?: string;
};

declare global {
  interface Window {
    irh: {
      getSettings: () => Promise<IrhSettings>;
      setSettings: (patch: Partial<IrhSettings>) => Promise<IrhSettings>;
      getListening: () => Promise<boolean>;
      setListening: (value: boolean) => Promise<boolean>;
      minimize: () => Promise<void>;
      close: () => Promise<void>;
      listAudioSources: () => Promise<{ id: string; name: string }[]>;
      askManual: (text: string) => Promise<{ ok: boolean }>;
      sendPcmChunk: (payload: unknown) => void;
      on: (channel: string, handler: (data: unknown) => void) => () => void;
    };
  }
}

export {};
