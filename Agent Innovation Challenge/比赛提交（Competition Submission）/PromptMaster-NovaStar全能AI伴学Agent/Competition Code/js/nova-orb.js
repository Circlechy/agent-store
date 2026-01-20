// Nova Orb 灵动球控制
class NovaOrb {
    constructor(orbElement, statusElement, transcriptElement) {
        this.orb = orbElement;
        this.status = statusElement;
        this.transcript = transcriptElement;
        this.currentState = 'idle'; // idle, listening, thinking, speaking
        this.audioContext = null;
        this.analyser = null;
        this.dataArray = null;
        this.animationFrame = null;
        this.transcriptTimer = null;
        
        this.init();
    }

    init() {
        // 点击Orb开始交互
        this.orb.addEventListener('click', () => {
            this.startListening();
        });

        // 监听语音输入事件，同步状态
        document.addEventListener('voice-input-start', (event) => {
            this.setTranscript('');
            this.setState('listening');
            const stream = event.detail && event.detail.stream;
            if (stream) {
                this.startVisualization(stream);
            }
        });
        document.addEventListener('voice-input-end', () => {
            if (this.currentState === 'listening') {
                this.setState('thinking');
            }
            this.stopVisualization();
        });
        document.addEventListener('voice-input-result', (event) => {
            const detail = event.detail || {};
            if (detail.isFinal && detail.transcript) {
                this.setTranscript(detail.transcript);
            }
        });
        document.addEventListener('voice-input-error', () => {
            if (this.currentState !== 'idle') {
                this.setState('idle');
            }
            this.stopVisualization();
        });

        // 初始化音频上下文（用于语音可视化）
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        } catch (e) {
            console.warn('AudioContext not supported');
        }
    }

    setState(state) {
        this.currentState = state;
        this.orb.className = 'nova-orb ' + state;
        
        const statusTexts = {
            'idle': '点击开始对话',
            'listening': '正在聆听...',
            'thinking': '思考中...',
            'speaking': '正在回答...'
        };
        
        if (this.status) {
            this.status.textContent = statusTexts[state] || statusTexts['idle'];
        }
    }

    setTranscript(text) {
        if (this.transcript) {
            this.transcript.textContent = text || '';
        }
        if (this.transcriptTimer) {
            clearTimeout(this.transcriptTimer);
            this.transcriptTimer = null;
        }
        if (text) {
            this.transcriptTimer = setTimeout(() => {
                if (this.transcript) {
                    this.transcript.textContent = '';
                }
                if (this.currentState === 'idle') {
                    this.setState('idle');
                }
            }, 4000);
        }
    }

    startListening() {
        if (window.voiceInput && window.voiceInput.supported) {
            window.voiceInput.start();
            return;
        }
        this._simulateListening();
    }

    _simulateListening() {
        this.setState('listening');

        // 模拟语音识别
        setTimeout(() => {
            this.setState('thinking');

            // 模拟思考过程
            setTimeout(() => {
                this.setState('speaking');

                // 模拟回答完成
                setTimeout(() => {
                    this.setState('idle');
                }, 3000);
            }, 2000);
        }, 2000);
    }

    // 根据音频数据更新Orb动画
    updateWithAudio(audioData) {
        if (!audioData || audioData.length === 0) return;
        
        const average = audioData.reduce((a, b) => a + b) / audioData.length;
        const scale = 1 + (average / 255) * 0.2;
        
        const core = this.orb.querySelector('.orb-core');
        if (core) {
            core.style.transform = `translate(-50%, -50%) scale(${scale})`;
        }
    }

    // 开始语音可视化
    startVisualization(stream) {
        if (!this.audioContext) return;
        
        const source = this.audioContext.createMediaStreamSource(stream);
        this.analyser = this.audioContext.createAnalyser();
        this.analyser.fftSize = 256;
        source.connect(this.analyser);
        
        const bufferLength = this.analyser.frequencyBinCount;
        this.dataArray = new Uint8Array(bufferLength);
        
        const update = () => {
            if (this.currentState !== 'listening') {
                this.animationFrame = null;
                return;
            }
            
            this.analyser.getByteFrequencyData(this.dataArray);
            this.updateWithAudio(this.dataArray);
            
            this.animationFrame = requestAnimationFrame(update);
        };
        
        update();
    }

    // 停止语音可视化
    stopVisualization() {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
            this.animationFrame = null;
        }
        
        const core = this.orb.querySelector('.orb-core');
        if (core) {
            core.style.transform = 'translate(-50%, -50%) scale(1)';
        }
    }
}

// 初始化Nova Orb
document.addEventListener('DOMContentLoaded', () => {
    const orbElement = document.getElementById('novaOrb');
    const statusElement = document.getElementById('orbStatus');
    const transcriptElement = document.getElementById('orbTranscript');
    
    if (orbElement && statusElement) {
        window.novaOrb = new NovaOrb(orbElement, statusElement, transcriptElement);
    }
});