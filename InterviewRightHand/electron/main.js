require('./load-env').loadEnvFile();

const {
  app,
  BrowserWindow,
  globalShortcut,
  ipcMain,
  desktopCapturer,
  session,
} = require('electron');
const path = require('path');
const StoreModule = require('electron-store');
const Store = StoreModule.default || StoreModule;
const { answerQuestion } = require('./llm');
const { retrieveKnowledge } = require('./knowledge');
const { enqueueQuestion, flushQuestionQueue } = require('./question-bank/sync');
const { createAudioBridge } = require('./audio/bridge');

const isDev = !app.isPackaged;
const store = new Store({
  name: 'settings',
  defaults: {
    openaiApiKey: process.env.OPENAI_API_KEY || '',
    openaiBaseUrl: process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1',
    openaiChatModel: process.env.OPENAI_CHAT_MODEL || 'gpt-4o-mini',
    openaiTranscribeModel:
      process.env.OPENAI_TRANSCRIBE_MODEL || 'gpt-4o-mini-transcribe',
    githubToken: process.env.GITHUB_TOKEN || '',
    githubRepo: process.env.GITHUB_REPO || 'pizhyanov/cursor',
    githubQuestionBankPath:
      process.env.GITHUB_QUESTION_BANK_PATH ||
      'InterviewRightHand/question-bank/inbox',
    sendQuestionsToRepo: true,
    stack: 'Creatio / BPMSoft, C#, .NET, JS, Angular, SQL, IIS, RabbitMQ, cache, Git',
    language: 'ru',
    opacity: 0.92,
    installId: '',
  },
});

let mainWindow = null;
let listening = false;
const audioBridge = createAudioBridge({
  getSettings: () => store.store,
  onPartialTranscript: (payload) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('transcript:partial', payload);
    }
  },
  onFinalQuestion: async (payload) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('transcript:final', payload);
    }
    if (payload.role === 'interviewer' && payload.text?.trim()) {
      void handleInterviewerQuestion(payload.text.trim());
    }
  },
});

function ensureInstallId() {
  if (!store.get('installId')) {
    const { v4: uuidv4 } = require('uuid');
    store.set('installId', uuidv4());
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 520,
    height: 640,
    minWidth: 380,
    minHeight: 420,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: false,
    resizable: true,
    hasShadow: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.setContentProtection(true);
  mainWindow.setAlwaysOnTop(true, 'screen-saver');

  const opacity = Number(store.get('opacity')) || 0.92;
  mainWindow.setOpacity(opacity);

  if (isDev) {
    mainWindow.loadURL('http://127.0.0.1:5173');
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function registerShortcuts() {
  globalShortcut.register('CommandOrControl+Shift+Space', async () => {
    listening = !listening;
    if (listening) {
      await audioBridge.start();
    } else {
      await audioBridge.stop();
    }
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('listening:changed', listening);
    }
  });

  globalShortcut.register('CommandOrControl+Shift+H', () => {
    if (!mainWindow) return;
    if (mainWindow.isVisible()) mainWindow.hide();
    else mainWindow.show();
  });

  globalShortcut.register('CommandOrControl+Shift+Up', () => {
    if (!mainWindow) return;
    const next = Math.min(1, (mainWindow.getOpacity() || 0.92) + 0.05);
    mainWindow.setOpacity(next);
    store.set('opacity', next);
  });

  globalShortcut.register('CommandOrControl+Shift+Down', () => {
    if (!mainWindow) return;
    const next = Math.max(0.35, (mainWindow.getOpacity() || 0.92) - 0.05);
    mainWindow.setOpacity(next);
    store.set('opacity', next);
  });
}

async function handleInterviewerQuestion(questionText) {
  const settings = store.store;

  if (settings.sendQuestionsToRepo) {
    void enqueueQuestion(
      {
        text: questionText,
        stack: settings.stack,
        installId: settings.installId,
        appVersion: app.getVersion(),
      },
      settings
    ).then(() => flushQuestionQueue(settings));
  }

  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('answer:start', { question: questionText });
  }

  try {
    const chunks = retrieveKnowledge(questionText);
    const stream = answerQuestion({
      question: questionText,
      knowledgeChunks: chunks,
      settings,
    });

    for await (const event of stream) {
      if (!mainWindow || mainWindow.isDestroyed()) break;
      mainWindow.webContents.send('answer:delta', event);
    }

    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('answer:done', { question: questionText });
    }
  } catch (error) {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('answer:error', {
        message: error?.message || String(error),
      });
    }
  }
}

function wireIpc() {
  ipcMain.handle('settings:get', () => store.store);
  ipcMain.handle('settings:set', (_e, patch) => {
    store.set(patch);
    if (typeof patch.opacity === 'number' && mainWindow) {
      mainWindow.setOpacity(patch.opacity);
    }
    return store.store;
  });

  ipcMain.handle('listening:get', () => listening);
  ipcMain.handle('listening:set', async (_e, value) => {
    listening = Boolean(value);
    if (listening) await audioBridge.start();
    else await audioBridge.stop();
    return listening;
  });

  ipcMain.handle('window:minimize', () => mainWindow?.minimize());
  ipcMain.handle('window:close', () => mainWindow?.close());

  ipcMain.handle('audio:list-sources', async () => {
    const sources = await desktopCapturer.getSources({
      types: ['screen', 'window'],
      fetchWindowIcons: false,
    });
    return sources.map((s) => ({ id: s.id, name: s.name }));
  });

  // Renderer may capture loopback via getDisplayMedia; main grants permission.
  session.defaultSession.setDisplayMediaRequestHandler((_request, callback) => {
    desktopCapturer.getSources({ types: ['screen'] }).then((sources) => {
      if (sources[0]) {
        callback({ video: sources[0], audio: 'loopback' });
      } else {
        callback({});
      }
    });
  });

  ipcMain.handle('question:manual', async (_e, text) => {
    const q = String(text || '').trim();
    if (!q) return { ok: false };
    await handleInterviewerQuestion(q);
    return { ok: true };
  });

  ipcMain.on('audio:pcm-chunk', (_e, payload) => {
    audioBridge.pushPcmChunk(payload);
  });
}

app.whenReady().then(() => {
  ensureInstallId();
  wireIpc();
  createWindow();
  registerShortcuts();
  void flushQuestionQueue(store.store);
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
  void audioBridge.stop();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
