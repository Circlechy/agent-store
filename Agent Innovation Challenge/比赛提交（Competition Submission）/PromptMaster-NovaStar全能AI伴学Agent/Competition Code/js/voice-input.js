// 语音输入控制器（录音 + 后端ASR）
class VoiceInputController {
    constructor(options = {}) {
        this.lang = options.lang || 'zh-CN';
        this.isListening = false;
        this._cancelled = false;
        this.supported = !!(navigator.mediaDevices && window.MediaRecorder);
        this.mediaRecorder = null;
        this.stream = null;
        this.audioChunks = [];
        this.audioContext = null;
        this.analyser = null;
        this.dataArray = null;
        this.silenceThreshold = options.silenceThreshold || 0.015;
        this.silenceDurationMs = options.silenceDurationMs || 1200;
        this.maxRecordMs = options.maxRecordMs || 15000;
        this._speechDetected = false;
        this._silenceStart = null;
        this._recordStart = null;
        this._monitorRaf = null;
        this._initWebSpeechFallback();
    }

    _initWebSpeechFallback() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            this.webSpeech = null;
            return;
        }
        this.webSpeech = new SpeechRecognition();
        this.webSpeech.lang = this.lang;
        this.webSpeech.interimResults = true;
        this.webSpeech.continuous = false;
        this.webSpeech.onstart = () => {
            this.isListening = true;
            document.dispatchEvent(new CustomEvent('voice-input-start'));
        };
        this.webSpeech.onresult = (event) => {
            let transcript = '';
            let isFinal = false;
            for (let i = event.resultIndex; i < event.results.length; i += 1) {
                const result = event.results[i];
                transcript += result[0].transcript;
                if (result.isFinal) {
                    isFinal = true;
                }
            }
            if (transcript.trim()) {
                document.dispatchEvent(new CustomEvent('voice-input-result', {
                    detail: { transcript: transcript.trim(), isFinal }
                }));
            }
        };
        this.webSpeech.onerror = (event) => {
            this.isListening = false;
            document.dispatchEvent(new CustomEvent('voice-input-error', {
                detail: { error: event.error || 'unknown' }
            }));
        };
        this.webSpeech.onend = () => {
            const wasListening = this.isListening;
            this.isListening = false;
            document.dispatchEvent(new CustomEvent('voice-input-end', {
                detail: { wasListening }
            }));
        };
    }

    async start() {
        if (this.isListening) {
            return;
        }
        if (!this.supported) {
            if (this.webSpeech) {
                this.webSpeech.start();
                return;
            }
            document.dispatchEvent(new CustomEvent('voice-input-error', {
                detail: { error: 'not_supported' }
            }));
            return;
        }
        try {
            this._resetState();
            this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this._setupAnalyser(this.stream);
            this._startRecorder(this.stream);
            this.isListening = true;
            document.dispatchEvent(new CustomEvent('voice-input-start', {
                detail: { stream: this.stream }
            }));
            this._monitorSilence();
        } catch (error) {
            this._cleanup();
            this.isListening = false;
            document.dispatchEvent(new CustomEvent('voice-input-error', {
                detail: { error: error.message || 'mic_permission_denied' }
            }));
        }
    }

    stop() {
        if (this.webSpeech && this.isListening && !this.mediaRecorder) {
            this.webSpeech.stop();
            return;
        }
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            this.mediaRecorder.stop();
        }
        this._stopMonitoring();
    }

    cancel() {
        this._cancelled = true;
        this.stop();
    }

    _setupAnalyser(stream) {
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = this.audioContext.createMediaStreamSource(stream);
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 2048;
            source.connect(this.analyser);
            this.dataArray = new Uint8Array(this.analyser.fftSize);
        } catch (error) {
            console.warn('[VoiceInput] AudioContext not supported:', error);
            this.analyser = null;
        }
    }

    _startRecorder(stream) {
        try {
            this.audioChunks = [];
            this.mediaRecorder = new MediaRecorder(stream);
        } catch (error) {
            document.dispatchEvent(new CustomEvent('voice-input-error', {
                detail: { error: 'recorder_init_failed' }
            }));
            return;
        }
        this.mediaRecorder.ondataavailable = (event) => {
            if (event.data && event.data.size > 0) {
                this.audioChunks.push(event.data);
            }
        };
        this.mediaRecorder.onstop = async () => {
            const wasListening = this.isListening;
            this.isListening = false;
            this._stopMonitoring();
            const blob = new Blob(this.audioChunks, { type: this.mediaRecorder.mimeType || 'audio/webm' });
            this._cleanup();
            document.dispatchEvent(new CustomEvent('voice-input-end', {
                detail: { wasListening }
            }));
            if (this._cancelled) {
                document.dispatchEvent(new CustomEvent('voice-input-cancelled'));
                return;
            }
            if (blob.size === 0) {
                document.dispatchEvent(new CustomEvent('voice-input-error', {
                    detail: { error: 'empty_audio' }
                }));
                return;
            }
            try {
                document.dispatchEvent(new CustomEvent('voice-input-transcribing'));
                const transcript = await this._transcribeAudio(blob);
                if (transcript && transcript.trim()) {
                    document.dispatchEvent(new CustomEvent('voice-input-result', {
                        detail: { transcript: transcript.trim(), isFinal: true }
                    }));
                    document.dispatchEvent(new CustomEvent('voice-input-complete'));
                } else {
                    document.dispatchEvent(new CustomEvent('voice-input-error', {
                        detail: { error: 'empty_transcript' }
                    }));
                }
            } catch (error) {
                document.dispatchEvent(new CustomEvent('voice-input-error', {
                    detail: { error: error.message || 'transcribe_failed' }
                }));
            }
        };
        this.mediaRecorder.start();
        this._recordStart = performance.now();
    }

    _monitorSilence() {
        if (!this.analyser || !this.dataArray) {
            return;
        }
        const tick = () => {
            if (!this.isListening || !this.analyser) {
                this._monitorRaf = null;
                return;
            }
            this.analyser.getByteTimeDomainData(this.dataArray);
            let sumSquares = 0;
            for (let i = 0; i < this.dataArray.length; i += 1) {
                const normalized = (this.dataArray[i] - 128) / 128;
                sumSquares += normalized * normalized;
            }
            const rms = Math.sqrt(sumSquares / this.dataArray.length);
            const now = performance.now();
            if (rms > this.silenceThreshold) {
                this._speechDetected = true;
                this._silenceStart = null;
            } else if (this._speechDetected) {
                if (!this._silenceStart) {
                    this._silenceStart = now;
                } else if (now - this._silenceStart > this.silenceDurationMs) {
                    this.stop();
                    return;
                }
            }
            if (this._recordStart && now - this._recordStart > this.maxRecordMs) {
                this.stop();
                return;
            }
            this._monitorRaf = requestAnimationFrame(tick);
        };
        this._monitorRaf = requestAnimationFrame(tick);
    }

    _stopMonitoring() {
        if (this._monitorRaf) {
            cancelAnimationFrame(this._monitorRaf);
            this._monitorRaf = null;
        }
        if (this.analyser) {
            this.analyser.disconnect();
            this.analyser = null;
        }
        if (this.audioContext) {
            this.audioContext.close().catch(() => {});
            this.audioContext = null;
        }
    }

    _resetState() {
        this._speechDetected = false;
        this._silenceStart = null;
        this._recordStart = null;
        this._cancelled = false;
    }

    _cleanup() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        this.mediaRecorder = null;
        this.audioChunks = [];
        this._stopMonitoring();
    }

    async _transcribeAudio(blob) {
        const audioBase64 = await this._blobToBase64(blob);
        const apiBase = this._getApiBase();
        const response = await fetch(`${apiBase}/voice/transcribe`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                audio_base64: audioBase64,
                language: this.lang
            })
        });
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        const data = await response.json();
        const payload = data.data || data;
        return payload.text || '';
    }

    _blobToBase64(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.onerror = () => reject(new Error('read_failed'));
            reader.readAsDataURL(blob);
        });
    }

    _getApiBase() {
        if (window.apiClient && window.apiClient.apiBase) {
            return window.apiClient.apiBase;
        }
        const urlParams = new URLSearchParams(window.location.search);
        const port = urlParams.get('port') || localStorage.getItem('api_port') || '8000';
        return `http://localhost:${port}/api`;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.voiceInput = new VoiceInputController();
});
