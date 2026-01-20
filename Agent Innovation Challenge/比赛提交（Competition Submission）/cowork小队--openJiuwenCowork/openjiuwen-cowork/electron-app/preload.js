const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  selectDirectory: () => ipcRenderer.invoke('select-directory'),
  listDirectory: (path) => ipcRenderer.invoke('list-directory', path),
  executeQuery: (query, currentDirectory) => ipcRenderer.invoke('execute-query', query, currentDirectory),
  getFileContent: (filePath) => ipcRenderer.invoke('get-file-content', filePath)
});
