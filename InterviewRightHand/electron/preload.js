const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('irh', {
  getSettings: () => ipcRenderer.invoke('settings:get'),
  setSettings: (patch) => ipcRenderer.invoke('settings:set', patch),
  getListening: () => ipcRenderer.invoke('listening:get'),
  setListening: (value) => ipcRenderer.invoke('listening:set', value),
  minimize: () => ipcRenderer.invoke('window:minimize'),
  close: () => ipcRenderer.invoke('window:close'),
  listAudioSources: () => ipcRenderer.invoke('audio:list-sources'),
  askManual: (text) => ipcRenderer.invoke('question:manual', text),
  sendPcmChunk: (payload) => ipcRenderer.send('audio:pcm-chunk', payload),
  on: (channel, handler) => {
    const valid = [
      'transcript:partial',
      'transcript:final',
      'listening:changed',
      'answer:start',
      'answer:delta',
      'answer:done',
      'answer:error',
    ];
    if (!valid.includes(channel)) return () => {};
    const wrapped = (_event, data) => handler(data);
    ipcRenderer.on(channel, wrapped);
    return () => ipcRenderer.removeListener(channel, wrapped);
  },
});
