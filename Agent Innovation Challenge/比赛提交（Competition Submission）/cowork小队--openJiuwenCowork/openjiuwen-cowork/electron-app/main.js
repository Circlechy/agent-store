const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const http = require('http');

let mainWindow;
let pythonProcess = null;
const API_BASE_URL = 'http://127.0.0.1:5001';

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    },
    title: 'OpenJiuwen - AI File Assistant',
    titleBarStyle: 'hiddenInset',
    frame: true
  });

  mainWindow.loadFile('index.html');

  // Open DevTools in development mode
  if (process.argv.includes('--dev')) {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// IPC handlers
ipcMain.handle('select-directory', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory']
  });
  if (!result.canceled && result.filePaths.length > 0) {
    return result.filePaths[0];
  }
  return null;
});

ipcMain.handle('list-directory', async (event, directoryPath) => {
  try {
    const response = await makeAPIRequest('/list-directory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ directory_path: directoryPath })
    });
    return response;
  } catch (error) {
    throw error;
  }
});

ipcMain.handle('execute-query', async (event, query, currentDirectory) => {
  try {
    const response = await makeAPIRequest('/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, current_directory: currentDirectory })
    });
    return response;
  } catch (error) {
    throw error;
  }
});

ipcMain.handle('get-file-content', async (event, filePath) => {
  try {
    const response = await makeAPIRequest('/read-file', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_path: filePath })
    });
    return response;
  } catch (error) {
    throw error;
  }
});

// Helper function to make API requests
function makeAPIRequest(path, options) {
  return new Promise((resolve, reject) => {
    const url = new URL(API_BASE_URL + path);
    const requestOptions = {
      hostname: url.hostname,
      port: url.port,
      path: url.pathname,
      method: options.method || 'GET',
      headers: options.headers || {}
    };

    const req = http.request(requestOptions, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(parsed);
          } else {
            reject(new Error(parsed.error || 'API request failed'));
          }
        } catch (e) {
          reject(new Error('Invalid response from server'));
        }
      });
    });

    req.on('error', reject);
    if (options.body) {
      req.write(options.body);
    }
    req.end();
  });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});




/**
 * 2 4 1 5 3
 * 
 * j = 2, i = 1
 * 
 * 2 1 4 5 3 
 * 
 * 2 1 3 5 4
 * 
 * i = 
 * 
 * 
 * 实现思路：
 * 1. 找一个pivot like arr[right]
 * 2. start an index like barrier i = low - 1
 * 3. travel from left to right
 * 4. try to swap every element that is smaller than the pivot, to the barrier
 * 5. 2 4 1 5 3 -> 2 1 4 5 3 -> 2 1 3 5 4
 * 
 * 
 * 
 * core: whenever you find a element smaller than the pivot, move the barrier ++, swap the
 * element to the barrier. when the travel finished , the i means all the elements to the left of I
 * will smaller than the pivot. 
 * 
 * so swap(arr, i + 1, right)
 * 
 *
 * 
 * 
 * 
 * 
 * 
 * 
 */