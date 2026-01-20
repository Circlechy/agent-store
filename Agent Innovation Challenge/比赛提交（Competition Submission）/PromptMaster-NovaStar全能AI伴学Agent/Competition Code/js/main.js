// 主控制文件
class AppController {
    constructor() {
        this.currentScene = 'learning'; // learning or story
        this.voiceTargets = {
            story: {
                buttonId: 'storyVoiceBtn',
                inputId: 'storyTheme',
                submitId: 'generateStoryBtn',
                modalId: 'storyModal',
                statusId: 'storyVoiceStatus',
                actionsId: 'storyVoiceActions',
                confirmId: 'storyVoiceConfirmBtn',
                retryId: 'storyVoiceRetryBtn',
            },
            qa: {
                buttonId: 'qaVoiceBtn',
                inputId: 'qaQuestion',
                submitId: 'askQuestionBtn',
                modalId: 'qaModal',
                statusId: 'qaVoiceStatus',
                actionsId: 'qaVoiceActions',
                confirmId: 'qaVoiceConfirmBtn',
                retryId: 'qaVoiceRetryBtn',
            },
        };
        this._modalVoiceStatusTimers = {};
        this.init();
    }

    init() {
        console.log('[AppController] 开始初始化...');
        this.setupQuickActions();
        this.setupTextInput();
        this.setupVoiceControls();
        this.setupModals();
        this.setupModalVoiceInput();
        this.setupChatControls();
        console.log('[AppController] 初始化完成');
    }


    // 设置快速功能入口
    setupQuickActions() {
        // 使用事件委托，确保动态内容也能响应
        const quickActionsContainers = document.querySelectorAll('.quick-actions');
        console.log('[setupQuickActions] 找到快速操作容器数量:', quickActionsContainers.length);
        if (quickActionsContainers.length) {
            quickActionsContainers.forEach((container, index) => {
                console.log(`[setupQuickActions] 为容器 ${index} 绑定事件`);
                container.addEventListener('click', (e) => {
                    console.log('[setupQuickActions] 容器被点击，目标:', e.target);
                    const actionBtn = e.target.closest('.action-btn');
                    if (actionBtn) {
                        e.preventDefault();
                        e.stopPropagation();
                        const action = actionBtn.dataset.action;
                        console.log('[setupQuickActions] Action button clicked:', action);
                        if (action) {
                            this.handleQuickAction(action);
                        } else {
                            console.warn('[setupQuickActions] 按钮没有 data-action 属性');
                        }
                    } else {
                        console.log('[setupQuickActions] 点击的不是 action-btn');
                    }
                });
            });
        } else {
            console.warn('[setupQuickActions] 没有找到快速操作容器！');
        }
    }

    // 处理快速操作（添加防抖机制）
    handleQuickAction(action) {
        console.log('handleQuickAction called with:', action);
        if (!action) {
            console.error('No action provided');
            return;
        }
        
        // 防抖：如果正在处理，忽略新的请求
        if (this._processingAction) {
            console.log('Action already processing, ignoring duplicate click');
            return;
        }
        
        this._processingAction = true;
        
        // 500ms后重置处理标志
        setTimeout(() => {
            this._processingAction = false;
        }, 500);
        
        // 记录互动数据
        if (window.activityTracker) {
            let category = 'general';
            let interest = null;
            
            switch (action) {
                case 'daily-idiom':
                    category = 'learning';
                    interest = 'idiom';
                    break;
                case 'story':
                    category = 'story';
                    interest = 'story';
                    break;
                case 'learn-chinese':
                    category = 'learning';
                    interest = 'chinese';
                    break;
                case 'qa-question':
                    category = 'learning';
                    interest = 'science';
                    break;
            }
            
            window.activityTracker.recordInteraction(action, category, { interest });
        }
        
        switch (action) {
            case 'daily-idiom':
                console.log('Showing daily idiom');
                this.openDailyIdiomModal();
                break;
            case 'story':
                console.log('Opening story modal');
                this.openStoryModal();
                break;
            case 'learn-chinese':
                console.log('Opening Chinese learning modal');
                this.openChineseModal();
                break;
            case 'qa-question':
                console.log('Opening QA modal');
                this.openQAModal();
                break;
            default:
                console.warn('Unknown action:', action);
        }
    }

    // 获取成语池
    getIdiomPool() {
        return [
            '画蛇添足', '刻舟求剑', '守株待兔', '拔苗助长', '井底之蛙', '狐假虎威', '亡羊补牢', '对牛弹琴',
            '画饼充饥', '叶公好龙', '掩耳盗铃', '滥竽充数', '黔驴技穷', '郑人买履', '杯弓蛇影', '买椟还珠',
            '愚公移山', '鹬蚌相争', '塞翁失马', '杞人忧天', '自相矛盾', '螳螂捕蝉', '囫囵吞枣', '走马观花',
            '水滴石穿', '亡戟得矛', '抱薪救火', '杀鸡儆猴', '指鹿为马', '惊弓之鸟', '卧薪尝胆', '三顾茅庐',
            '闻鸡起舞', '程门立雪', '破釜沉舟', '四面楚歌', '草木皆兵', '纸上谈兵', '完璧归赵', '负荆请罪',
            '洛阳纸贵', '毛遂自荐', '老马识途', '田忌赛马', '围魏救赵', '指桑骂槐', '一鼓作气', '一诺千金',
            '百步穿杨', '胸有成竹', '对症下药', '熟能生巧', '呕心沥血', '画龙点睛', '入木三分', '高山流水',
            '东施效颦', '南辕北辙', '凿壁偷光', '悬梁刺股', '囊萤映雪', '半途而废', '百发百中', '不耻下问',
            '大公无私', '奉公守法', '废寝忘食', '脚踏实地', '勤能补拙', '勤学好问', '望梅止渴', '乐不思蜀',
            '煮豆燃萁', '才高八斗', '东山再起', '江郎才尽', '洛阳才子', '请君入瓮', '口蜜腹剑', '桃李满天下',
            '黄袍加身', '开卷有益', '刮目相看', '鞠躬尽瘁', '乐此不疲', '初出茅庐', '单刀赴会', '舌战群儒',
            '神机妙算', '万事俱备，只欠东风', '下笔成章', '手不释卷', '大器晚成', '东山之志', '凤毛麟角', '后生可畏',
            '过门不入', '乘风破浪', '同舟共济', '众志成城'
        ];
    }

    // 打开每日成语九宫格
    openDailyIdiomModal() {
        const storyModal = document.getElementById('storyModal');
        const chineseModal = document.getElementById('chineseModal');
        if (storyModal) storyModal.classList.remove('active');
        if (chineseModal) chineseModal.classList.remove('active');

        const idiomModal = document.getElementById('idiomModal');
        if (idiomModal) {
            idiomModal.classList.add('active');
        }
        this.generateIdiomGrid();
    }

    // 显示成语故事
    async showIdiomStory(idiom) {
        if (!idiom) return;
        this.openStoryModal({ mode: 'idiom' });

        const storyModal = document.getElementById('storyModal');
        const titleEl = document.querySelector('#storyModal h2');
        const themeInput = document.getElementById('storyTheme');
        const generateBtn = document.getElementById('generateStoryBtn');
        const storyContent = document.getElementById('storyContent');
        const voiceActions = document.getElementById('storyVoiceActions');

        if (storyModal) storyModal.dataset.mode = 'idiom';
        if (titleEl) titleEl.textContent = '成语故事';
        if (themeInput) {
            themeInput.value = idiom;
            themeInput.placeholder = '今日成语，比如：卧薪尝胆';
            themeInput.style.display = 'none';
        }
        if (generateBtn) {
            generateBtn.innerHTML = '<i class="fas fa-magic"></i> 生成成语故事';
            generateBtn.style.display = 'none';
        }
            this.setModalVoiceControlsVisible('story', false);
        if (voiceActions) {
            voiceActions.classList.add('hidden');
        }
        if (window.voiceInputTarget === 'story') {
            window.voiceInputTarget = null;
            if (window.voiceInput) {
                window.voiceInput.cancel();
            }
        }
        if (storyContent) {
            storyContent.textContent = '正在生成成语故事...';
        }

        if (window.activityTracker) {
            window.activityTracker.recordInteraction('idiom', 'learning', { interest: 'idiom' });
        }

        if (window.agentSystem) {
            try {
                const story = await window.agentSystem.generateIdiomStory(idiom);
                console.log('[main] 生成的成语故事:', story);
                if (story && story.content && typeof story.content === 'object') {
                    if (story.content.title && story.content.paragraphs) {
                        window.agentSystem.displayStoryContent(story.content, storyContent);
                    } else if (story.content.text) {
                        storyContent.innerHTML = `<div class="story-text">${story.content.text.replace(/\n/g, '<br>')}</div>`;
                    } else {
                        storyContent.textContent = JSON.stringify(story.content);
                    }
                } else {
                    storyContent.textContent = '生成成语故事失败，请稍后再试。';
                }
            } catch (error) {
                console.error('[main] 生成成语故事失败:', error);
                storyContent.textContent = error.message || '生成成语故事失败，请稍后再试。';
            }
        }
    }

    // 打开故事模态框
    openStoryModal(options = {}) {
        const mode = options.mode || 'story';
        const chineseModal = document.getElementById('chineseModal');
        const idiomModal = document.getElementById('idiomModal');
        if (chineseModal) {
            chineseModal.classList.remove('active');
        }
        if (idiomModal) {
            idiomModal.classList.remove('active');
        }
        const modal = document.getElementById('storyModal');
        if (modal) {
            modal.classList.add('active');
            modal.dataset.mode = mode;
        }

        const titleEl = document.querySelector('#storyModal h2');
        const themeInput = document.getElementById('storyTheme');
        const generateBtn = document.getElementById('generateStoryBtn');
        if (mode === 'story') {
            if (titleEl) titleEl.textContent = '生成睡前故事';
            if (themeInput) {
                themeInput.placeholder = '输入故事主题，比如：小兔子、太空冒险...';
                themeInput.style.display = '';
            }
            if (generateBtn) {
                generateBtn.innerHTML = '<i class="fas fa-magic"></i> 生成故事';
                generateBtn.style.display = '';
            }
            this.setModalVoiceControlsVisible('story', true);
        }
    }

    setModalVoiceControlsVisible(targetKey, visible) {
        const target = this.voiceTargets ? this.voiceTargets[targetKey] : null;
        if (!target) return;
        const voiceBtn = document.getElementById(target.buttonId);
        const voiceStatus = document.getElementById(target.statusId);
        const voiceActions = document.getElementById(target.actionsId);
        const shouldHide = !visible;

        if (voiceBtn) {
            voiceBtn.classList.toggle('hidden', shouldHide);
        }
        if (voiceStatus) {
            voiceStatus.classList.toggle('hidden', shouldHide);
            if (visible) {
                voiceStatus.textContent = '准备语音输入';
                voiceStatus.classList.remove('is-recording');
            }
        }
        if (voiceActions) {
            voiceActions.classList.toggle('hidden', true);
        }
    }

    // 打开汉字学习模态框
    openChineseModal() {
        const storyModal = document.getElementById('storyModal');
        const idiomModal = document.getElementById('idiomModal');
        if (storyModal) {
            storyModal.classList.remove('active');
        }
        if (idiomModal) {
            idiomModal.classList.remove('active');
        }
        const modal = document.getElementById('chineseModal');
        if (modal) {
            modal.classList.add('active');
        }
        this.generateChineseGrid();
    }

    // 打开汉字学习内容模态框
    openLearningModal(character) {
        const learningModal = document.getElementById('learningModal');
        const learningTitle = document.getElementById('learningTitle');
        const learningContent = document.getElementById('learningContent');
        if (learningTitle) {
            learningTitle.textContent = character ? `汉字学习：${character}` : '汉字学习';
        }
        if (learningContent) {
            learningContent.textContent = '正在准备讲解内容...';
        }
        if (learningModal) {
            learningModal.classList.add('active');
        }
    }

    // 打开十万个为什么模态框
    openQAModal() {
        const storyModal = document.getElementById('storyModal');
        const chineseModal = document.getElementById('chineseModal');
        const learningModal = document.getElementById('learningModal');
        if (storyModal) storyModal.classList.remove('active');
        if (chineseModal) chineseModal.classList.remove('active');
        if (learningModal) learningModal.classList.remove('active');
        
        const qaModal = document.getElementById('qaModal');
        if (qaModal) {
            qaModal.classList.add('active');
            // 清空之前的内容
            const qaContent = document.getElementById('qaContent');
            const qaQuestion = document.getElementById('qaQuestion');
            if (qaContent) qaContent.innerHTML = '';
            if (qaQuestion) qaQuestion.value = '';
        }
        this.setModalVoiceControlsVisible('qa', true);
    }

    // 生成汉字九宫格
    generateChineseGrid() {
        const grid = document.getElementById('chineseGrid');
        if (!grid) return;

        const pool = [
            '水', '火', '木', '土', '金', '山', '田', '日', '月',
            '风', '雨', '云', '星', '海', '河', '花', '草', '鱼',
            '鸟', '树', '石', '人', '口', '手', '足', '心', '目',
            '耳', '鼻', '光', '电', '春', '夏', '秋', '冬', '雪',
            '猫', '狗', '牛', '羊', '鸡', '鸭', '鹅', '猪', '鼠',
            '明', '亮', '黑', '白', '红', '绿', '蓝', '紫', '黄',
            '渠', '道', '桥', '路', '车', '船',
        ];

        const selected = this.pickGridItems(pool, 9, this._lastChineseSet);

        grid.innerHTML = '';
        for (let i = 0; i < selected.length; i++) {
            const cell = document.createElement('div');
            cell.className = 'chinese-cell';
            cell.textContent = selected[i];
            grid.appendChild(cell);
        }

        this._lastChineseSet = new Set(selected);
    }

    // 生成成语九宫格
    generateIdiomGrid() {
        const grid = document.getElementById('idiomGrid');
        if (!grid) return;

        const pool = this.getIdiomPool();
        const selected = this.pickGridItems(pool, 9, this._lastIdiomSet);

        grid.innerHTML = '';
        selected.forEach((idiom) => {
            const cell = document.createElement('div');
            cell.className = 'idiom-cell';
            cell.textContent = idiom;
            grid.appendChild(cell);
        });

        this._lastIdiomSet = new Set(selected);
    }

    // 从池中选取指定数量，尽量避免与上一组重复
    pickGridItems(pool, count, lastSet) {
        if (!Array.isArray(pool) || pool.length === 0) return [];
        const maxTries = 20;
        let selected = [];

        for (let attempt = 0; attempt < maxTries; attempt++) {
            const shuffled = [...pool];
            for (let i = shuffled.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
            }
            const candidate = shuffled.slice(0, count);
            if (!lastSet || lastSet.size === 0) {
                selected = candidate;
                break;
            }
            const hasOverlap = candidate.some((item) => lastSet.has(item));
            if (!hasOverlap) {
                selected = candidate;
                break;
            }
            selected = candidate;
        }

        return selected;
    }

    // 设置文本输入
    setupTextInput() {
        const textInput = document.getElementById('chatInput');
        const sendBtn = document.getElementById('chatSendBtn');
        const voiceBtn = document.getElementById('chatVoiceBtn');
        
        console.log('[setupTextInput] 查找元素:', {
            textInput: !!textInput,
            sendBtn: !!sendBtn,
            voiceBtn: !!voiceBtn
        });
        
        if (textInput && sendBtn) {
            if (textInput.dataset.bound === 'true') {
                return;
            }
            textInput.dataset.bound = 'true';
            sendBtn.dataset.bound = 'true';
            const sendMessage = () => {
                const text = textInput.value.trim();
                console.log('[setupTextInput] 发送消息:', text);
                if (text && window.agentSystem) {
                    // 记录文本互动
                    if (window.activityTracker) {
                        window.activityTracker.recordInteraction('text', 'general', { interest: 'general' });
                    }
                    window.agentSystem.processUserInput(text);
                    textInput.value = '';
                } else {
                    console.warn('[setupTextInput] 无法发送消息:', {
                        hasText: !!text,
                        hasAgentSystem: !!window.agentSystem
                    });
                }
            };
            
            sendBtn.addEventListener('click', sendMessage);
            console.log('[setupTextInput] 发送按钮事件已绑定');
            
            textInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    sendMessage();
                }
            });
            console.log('[setupTextInput] 输入框事件已绑定');
        } else {
            console.error('[setupTextInput] 缺少必要的元素！', {
                textInput: !!textInput,
                sendBtn: !!sendBtn
            });
        }

        if (voiceBtn) {
            if (voiceBtn.dataset.bound === 'true') {
                return;
            }
            voiceBtn.dataset.bound = 'true';
            voiceBtn.addEventListener('click', () => {
                if (window.novaOrb) {
                    window.novaOrb.startListening();
                }
            });
            console.log('[setupTextInput] 语音按钮事件已绑定');
        }
    }

    setupVoiceControls() {
        const statusEl = document.getElementById('voiceStatusText');
        const cancelBtn = document.getElementById('voiceCancelBtn');
        const retryBtn = document.getElementById('voiceRetryBtn');

        const setStatus = (text) => {
            if (statusEl) {
                statusEl.textContent = text;
            }
        };

        const showCancel = (visible) => {
            if (cancelBtn) {
                cancelBtn.style.display = visible ? 'inline-flex' : 'none';
            }
        };

        const showRetry = (visible) => {
            if (retryBtn) {
                retryBtn.style.display = visible ? 'inline-flex' : 'none';
            }
        };

        setStatus('准备语音输入');
        showCancel(false);
        showRetry(false);

        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                if (window.voiceInput) {
                    window.voiceInput.cancel();
                }
            });
        }

        if (retryBtn) {
            retryBtn.addEventListener('click', () => {
                showRetry(false);
                if (window.novaOrb) {
                    window.novaOrb.startListening();
                }
            });
        }

        document.addEventListener('voice-input-start', () => {
            setStatus('录音中...松开后自动识别');
            showCancel(true);
            showRetry(false);
        });

        document.addEventListener('voice-input-transcribing', () => {
            setStatus('识别中...');
            showCancel(false);
            showRetry(false);
        });

        document.addEventListener('voice-input-result', (event) => {
            const detail = event.detail || {};
            if (detail.isFinal) {
                setStatus('识别完成');
                showCancel(false);
                showRetry(false);
                setTimeout(() => setStatus('准备语音输入'), 1500);
            }
        });

        document.addEventListener('voice-input-error', () => {
            setStatus('识别失败，请重试');
            showCancel(false);
            showRetry(true);
        });

        document.addEventListener('voice-input-cancelled', () => {
            setStatus('已取消录音');
            showCancel(false);
            showRetry(true);
        });
    }

    setupModalVoiceInput() {
        const targets = this.voiceTargets || {};
        Object.keys(targets).forEach((key) => {
            const target = targets[key];
            if (!target) return;
            const voiceBtn = document.getElementById(target.buttonId);
            const inputEl = document.getElementById(target.inputId);
            const statusEl = document.getElementById(target.statusId);
            const actionsEl = document.getElementById(target.actionsId);
            const confirmBtn = document.getElementById(target.confirmId);
            const retryBtn = document.getElementById(target.retryId);

            if (inputEl && inputEl.dataset.boundInputType !== 'true') {
                inputEl.dataset.boundInputType = 'true';
                inputEl.dataset.inputType = inputEl.dataset.inputType || 'text';
                inputEl.addEventListener('input', () => {
                    inputEl.dataset.inputType = 'text';
                    if (actionsEl) {
                        actionsEl.classList.add('hidden');
                    }
                });
            }

            if (voiceBtn) {
                if (voiceBtn.dataset.bound === 'true') {
                    return;
                }
                voiceBtn.dataset.bound = 'true';
                voiceBtn.addEventListener('click', () => {
                    window.voiceInputTarget = key;
                    if (window.novaOrb) {
                        window.novaOrb.startListening();
                    } else if (window.voiceInput) {
                        window.voiceInput.start();
                    }
                });
            }

            if (statusEl && statusEl.dataset.bound === 'true') {
                return;
            }
            if (statusEl) {
                statusEl.dataset.bound = 'true';
                statusEl.textContent = '准备语音输入';
            }

            if (actionsEl) {
                actionsEl.classList.add('hidden');
            }

            if (confirmBtn && confirmBtn.dataset.bound !== 'true') {
                confirmBtn.dataset.bound = 'true';
                confirmBtn.addEventListener('click', () => {
                    const submitBtn = document.getElementById(target.submitId);
                    if (submitBtn) {
                        submitBtn.click();
                    }
                    if (actionsEl) {
                        actionsEl.classList.add('hidden');
                    }
                    setModalStatus(key, '已确认，正在提交...', 1200);
                });
            }

            if (retryBtn && retryBtn.dataset.bound !== 'true') {
                retryBtn.dataset.bound = 'true';
                retryBtn.addEventListener('click', () => {
                    if (actionsEl) {
                        actionsEl.classList.add('hidden');
                    }
                    setModalStatus(key, '准备语音输入');
                    window.voiceInputTarget = key;
                    if (window.novaOrb) {
                        window.novaOrb.startListening();
                    } else if (window.voiceInput) {
                        window.voiceInput.start();
                    }
                });
            }
        });

        if (this._modalVoiceHandlersBound) {
            return;
        }
        this._modalVoiceHandlersBound = true;

        const setModalStatus = (targetKey, text, resetDelay = null) => {
            if (!targetKey) return;
            const target = this.voiceTargets ? this.voiceTargets[targetKey] : null;
            if (!target) return;
            const statusEl = document.getElementById(target.statusId);
            if (statusEl) {
                statusEl.textContent = text;
                statusEl.classList.remove('is-recording');
            }
            if (resetDelay != null) {
                if (this._modalVoiceStatusTimers[targetKey]) {
                    clearTimeout(this._modalVoiceStatusTimers[targetKey]);
                }
                this._modalVoiceStatusTimers[targetKey] = setTimeout(() => {
                    const resetEl = document.getElementById(target.statusId);
                    if (resetEl) {
                        resetEl.textContent = '准备语音输入';
                        resetEl.classList.remove('is-recording');
                    }
                }, resetDelay);
            }
        };

        document.addEventListener('voice-input-result', (event) => {
            const detail = event.detail || {};
            if (!detail.isFinal || !detail.transcript) return;
            const targetKey = window.voiceInputTarget;
            if (!targetKey) return;
            const target = this.voiceTargets ? this.voiceTargets[targetKey] : null;
            if (!target) {
                window.voiceInputTarget = null;
                return;
            }
            const modal = document.getElementById(target.modalId);
            if (modal && !modal.classList.contains('active')) {
                window.voiceInputTarget = null;
                return;
            }
            const inputEl = document.getElementById(target.inputId);
            if (inputEl) {
                inputEl.value = detail.transcript.trim();
                inputEl.dataset.inputType = 'voice';
            }
            const actionsEl = document.getElementById(target.actionsId);
            if (actionsEl) {
                actionsEl.classList.remove('hidden');
            }
            setModalStatus(targetKey, '识别完成，请确认', 1500);
        });

        document.addEventListener('voice-input-start', () => {
            if (!window.voiceInputTarget) return;
            setModalStatus(window.voiceInputTarget, '录音中...松开后自动识别');
            const target = this.voiceTargets ? this.voiceTargets[window.voiceInputTarget] : null;
            if (target) {
                const statusEl = document.getElementById(target.statusId);
                if (statusEl) {
                    statusEl.classList.add('is-recording');
                }
            }
        });

        document.addEventListener('voice-input-transcribing', () => {
            if (!window.voiceInputTarget) return;
            setModalStatus(window.voiceInputTarget, '识别中...');
        });

        document.addEventListener('voice-input-error', () => {
            if (!window.voiceInputTarget) return;
            setModalStatus(window.voiceInputTarget, '识别失败，请重试', 2000);
            const target = this.voiceTargets ? this.voiceTargets[window.voiceInputTarget] : null;
            if (target) {
                const actionsEl = document.getElementById(target.actionsId);
                if (actionsEl) {
                    actionsEl.classList.add('hidden');
                }
            }
        });

        document.addEventListener('voice-input-cancelled', () => {
            if (!window.voiceInputTarget) return;
            setModalStatus(window.voiceInputTarget, '已取消录音', 1500);
            const target = this.voiceTargets ? this.voiceTargets[window.voiceInputTarget] : null;
            if (target) {
                const actionsEl = document.getElementById(target.actionsId);
                if (actionsEl) {
                    actionsEl.classList.add('hidden');
                }
            }
        });

        const clearTarget = () => {
            if (window.voiceInputTarget) {
                window.voiceInputTarget = null;
            }
        };
        document.addEventListener('voice-input-error', clearTarget);
        document.addEventListener('voice-input-cancelled', clearTarget);
    }

    setupChatControls() {
        const clearBtn = document.getElementById('clearChatBtn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                if (window.agentSystem && window.agentSystem.clearHistory) {
                    window.agentSystem.clearHistory();
                }
            });
        }
    }

    // 设置模态框
    setupModals() {
        // 故事模态框
        const storyModal = document.getElementById('storyModal');
        const closeStoryBtn = document.getElementById('closeStoryModal');
        const generateStoryBtn = document.getElementById('generateStoryBtn');
        const chineseModal = document.getElementById('chineseModal');
        const closeChineseBtn = document.getElementById('closeChineseModal');
        const refreshChineseGridBtn = document.getElementById('refreshChineseGridBtn');
        const idiomModal = document.getElementById('idiomModal');
        const closeIdiomBtn = document.getElementById('closeIdiomModal');
        const refreshIdiomGridBtn = document.getElementById('refreshIdiomGridBtn');
        const learningModal = document.getElementById('learningModal');
        const closeLearningBtn = document.getElementById('closeLearningModal');
        const qaModal = document.getElementById('qaModal');
        const closeQABtn = document.getElementById('closeQAModal');
        const askQuestionBtn = document.getElementById('askQuestionBtn');
        
        if (closeStoryBtn) {
            closeStoryBtn.addEventListener('click', () => {
                if (storyModal) storyModal.classList.remove('active');
            });
        }
        
        if (generateStoryBtn) {
            generateStoryBtn.addEventListener('click', async () => {
                const themeInput = document.getElementById('storyTheme');
                const storyContent = document.getElementById('storyContent');
                const mode = storyModal?.dataset?.mode || 'story';
                
                if (themeInput && storyContent) {
                    const theme = themeInput.value.trim() || '小冒险';
                    const inputType = themeInput.dataset.inputType || 'text';
                    storyContent.textContent = mode === 'idiom' ? '正在生成成语故事...' : '正在生成故事...';
                    
                    if (window.activityTracker) {
                        if (mode === 'idiom') {
                            window.activityTracker.recordInteraction('idiom', 'learning', { interest: 'idiom' });
                        } else {
                            window.activityTracker.recordInteraction('story', 'story', { interest: 'story' });
                        }
                    }
                    
                    if (window.agentSystem) {
                        try {
                            const story = mode === 'idiom'
                                ? await window.agentSystem.generateIdiomStory(theme, { inputType })
                                : await window.agentSystem.generateStory(theme, { inputType });
                            console.log('[main] 生成的故事:', story);
                            
                            if (story && typeof story.content === 'object' && story.content !== null) {
                                if (story.content.title && story.content.paragraphs) {
                                    window.agentSystem.displayStoryContent(story.content, storyContent);
                                } else if (story.content.text) {
                                    storyContent.innerHTML = `<div class="story-text">${story.content.text.replace(/\n/g, '<br>')}</div>`;
                                } else {
                                    storyContent.textContent = JSON.stringify(story.content);
                                }
                            } else if (typeof story.content === 'string') {
                                storyContent.textContent = story.content;
                            } else {
                                storyContent.textContent = '生成内容失败，请检查控制台错误信息';
                            }
                            this.setModalVoiceControlsVisible('story', false);
                        } catch (error) {
                            console.error('[main] 生成故事失败:', error);
                            let errorMessage = error.message || '未知错误';
                            
                            if (error.message && error.message.includes('无法连接到后端服务器')) {
                                errorMessage = `无法连接到后端服务器\n\n请确保后端服务器正在运行：\n1. 打开终端\n2. 运行: python api_server.py\n3. 等待服务器启动完成后再试`;
                            }
                            
                            storyContent.innerHTML = `<div class="error-message" style="color: red; padding: 20px;">
                                <h3>生成失败</h3>
                                <p>${errorMessage.replace(/\n/g, '<br>')}</p>
                                <p style="font-size: 12px; margin-top: 10px;">详细错误信息请查看浏览器控制台（F12）</p>
                            </div>`;
                        }
                        themeInput.dataset.inputType = 'text';
                    }
                }
            });
        }

        if (closeChineseBtn) {
            closeChineseBtn.addEventListener('click', () => {
                if (chineseModal) chineseModal.classList.remove('active');
            });
        }

        if (refreshChineseGridBtn) {
            refreshChineseGridBtn.addEventListener('click', () => {
                this.generateChineseGrid();
            });
        }

        if (closeIdiomBtn) {
            closeIdiomBtn.addEventListener('click', () => {
                if (idiomModal) idiomModal.classList.remove('active');
            });
        }

        if (refreshIdiomGridBtn) {
            refreshIdiomGridBtn.addEventListener('click', () => {
                this.generateIdiomGrid();
            });
        }

        if (closeLearningBtn) {
            closeLearningBtn.addEventListener('click', () => {
                if (learningModal) learningModal.classList.remove('active');
            });
        }

        if (closeQABtn) {
            closeQABtn.addEventListener('click', () => {
                if (qaModal) qaModal.classList.remove('active');
            });
        }

        if (askQuestionBtn) {
            askQuestionBtn.addEventListener('click', async () => {
                const qaQuestion = document.getElementById('qaQuestion');
                const qaContent = document.getElementById('qaContent');
                
                if (qaQuestion && qaContent) {
                    const question = qaQuestion.value.trim();
                    if (!question) {
                        alert('请输入你的问题！');
                        return;
                    }
                    const inputType = qaQuestion.dataset.inputType || 'text';
                    
                    qaContent.innerHTML = '<div class="qa-loading">正在思考你的问题...</div>';
                    
                    try {
                        if (window.agentSystem && window.apiClient) {
                            // 将提问也同步到聊天框
                            if (window.chatUI) {
                                window.chatUI.addMessage({
                                    role: 'user',
                                    content: question,
                                    source: inputType
                                });
                            }
                            // 调用后端的 answer_question 接口
                            const result = await window.apiClient.answerQuestion(
                                question,
                                window.agentSystem.userId || 'default_user',
                                window.agentSystem.context || { age: 6 },
                                inputType
                            );

                            const answerText = result.answer_content || result.content || result.response || '（没有返回内容）';
                            const qaResponse = {
                                intent: 'qa',
                                content_type: 'qa',
                                lesson_type: 'qa',
                                content: {
                                    question: result.question || question,
                                    answer_content: typeof answerText === 'string' ? answerText : JSON.stringify(answerText),
                                    image: result.image || '',
                                    audio: result.audio || '',
                                },
                                handled_by: 'mentor',
                                agents: ['mentor'],
                            };
                            if (window.agentSystem) {
                                window.agentSystem.displayResponse(question, qaResponse, 'teacher');
                            } else {
                                this.displayQAContent(qaResponse.content, qaContent);
                            }
                        } else {
                            // 回退到主对话
                            if (window.agentSystem) {
                                const response = await window.agentSystem.processUserInput(question, {
                                    intent: 'qa',
                                    inputType,
                                });
                                this.displayQAContent(response, qaContent);
                            }
                        }
                    } catch (error) {
                        console.error('[main] 问答失败:', error);
                        qaContent.innerHTML = `<div class="qa-error">提问失败：${error.message || '未知错误'}</div>`;
                    } finally {
                        qaQuestion.dataset.inputType = 'text';
                    }
                }
            });
        }

        // 支持按 Enter 键提交问题
        const qaQuestion = document.getElementById('qaQuestion');
        if (qaQuestion) {
            qaQuestion.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && askQuestionBtn) {
                    askQuestionBtn.click();
                }
            });
        }

        // 汉字网格点击事件
        const chineseGrid = document.getElementById('chineseGrid');
        if (chineseGrid) {
            chineseGrid.addEventListener('click', (e) => {
                const cell = e.target.closest('.chinese-cell');
                if (!cell) return;
                const character = cell.textContent.trim();
                if (!character) return;
                const topic = character;
                this.openLearningModal(character);
                if (window.agentSystem) {
                    window.agentSystem.processUserInput(topic, {
                        intent: 'learning',
                        outputElementId: 'learningContent',
                    });
                }
            });
        }

        // 成语网格点击事件
        const idiomGrid = document.getElementById('idiomGrid');
        if (idiomGrid) {
            idiomGrid.addEventListener('click', (e) => {
                const cell = e.target.closest('.idiom-cell');
                if (!cell) return;
                const idiom = cell.textContent.trim();
                if (!idiom) return;
                this.showIdiomStory(idiom);
            });
        }
        
        // 点击背景关闭模态框
        [storyModal, chineseModal, idiomModal, learningModal, qaModal].forEach(modal => {
            if (modal) {
                modal.addEventListener('click', (e) => {
                    if (e.target === modal) {
                        modal.classList.remove('active');
                    }
                });
            }
        });
    }

    // 显示问答内容
    displayQAContent(result, container) {
        if (!container) return;
        
        const question = result.question || result.query || '';
        const answerContent = result.answer_content || result.content || result.response || '';
        const image = result.image || (result.content && result.content.image) || '';
        const audio = result.audio || (result.content && result.content.audio) || '';
        
        let html = `<div class="qa-result">`;
        
        // 显示语音 - 放在回答文本上方，居中
        if (audio && !audio.startsWith('[模拟')) {
            html += `<div class="story-audio-controls" style="display: flex; justify-content: center; align-items: center; gap: 10px; margin-top: 1rem; margin-bottom: 0.75rem; flex-wrap: wrap;">`;
            html += `<button id="qaPlayAudio" class="play-all-btn" style="padding: 7px 20px; font-size: 12px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 20px; cursor: pointer; box-shadow: 0 2px 4px rgba(102, 126, 234, 0.2); transition: all 0.2s ease; display: inline-flex; align-items: center; justify-content: center; gap: 6px; font-weight: 500; letter-spacing: 0.2px; white-space: nowrap;">`;
            html += `<i class="fas fa-play" style="font-size: 10px;"></i> 播放语音`;
            html += `</button>`;
            html += `<button id="qaStopAudio" class="stop-all-btn" style="padding: 7px 20px; font-size: 12px; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; border: none; border-radius: 20px; cursor: pointer; box-shadow: 0 2px 4px rgba(99, 102, 241, 0.2); transition: all 0.2s ease; display: none; align-items: center; justify-content: center; gap: 6px; font-weight: 500; letter-spacing: 0.2px; white-space: nowrap;">`;
            html += `<i class="fas fa-stop" style="font-size: 10px;"></i> 停止`;
            html += `</button>`;
            html += `</div>`;
            html += `<div id="qaAudioProgress" style="text-align: center; font-size: 11px; color: #6b7280; min-height: 14px; margin-bottom: 0.5rem;"></div>`;
            html += `<div class="qa-audio" style="display: none;">`;
            if (audio.startsWith('data:audio') || audio.startsWith('http')) {
                html += `<audio id="qaAudioPlayer"><source src="${audio}" type="audio/mpeg">您的浏览器不支持音频播放</audio>`;
            }
            html += `</div>`;
        }
        
        html += `<div class="qa-answer-display">${answerContent.replace(/\n/g, '<br>')}</div>`;
        
        // 显示图片
        if (image && !image.startsWith('[模拟')) {
            html += `<div class="qa-image">`;
            if (image.startsWith('data:image') || image.startsWith('http')) {
                html += `<img src="${image}" alt="问答配图" style="max-width: 100%; border-radius: 8px; margin-top: 10px;" />`;
            }
            html += `</div>`;
        }
        
        html += `</div>`;
        container.innerHTML = html;
        
        // 设置音频播放控制
        if (audio && !audio.startsWith('[模拟')) {
            this.setupQAAudioPlayback(container);
        }
        this.setModalVoiceControlsVisible('qa', false);
    }

    setupQAAudioPlayback(container) {
        const playBtn = container.querySelector('#qaPlayAudio');
        const stopBtn = container.querySelector('#qaStopAudio');
        const progressDiv = container.querySelector('#qaAudioProgress');
        const audioElement = container.querySelector('#qaAudioPlayer');
        
        if (!playBtn || !audioElement) return;
        
        playBtn.addEventListener('click', () => {
            audioElement.play().then(() => {
                playBtn.style.display = 'none';
                if (stopBtn) stopBtn.style.display = 'inline-flex';
                if (progressDiv) progressDiv.textContent = '正在播放...';
            }).catch(err => {
                console.error('播放音频失败:', err);
                if (progressDiv) progressDiv.textContent = '播放失败';
            });
        });
        
        if (stopBtn) {
            stopBtn.addEventListener('click', () => {
                audioElement.pause();
                audioElement.currentTime = 0;
                playBtn.style.display = 'inline-flex';
                stopBtn.style.display = 'none';
                if (progressDiv) progressDiv.textContent = '';
            });
        }
        
        audioElement.addEventListener('ended', () => {
            playBtn.style.display = 'inline-flex';
            if (stopBtn) stopBtn.style.display = 'none';
            if (progressDiv) {
                progressDiv.textContent = '播放完成';
                setTimeout(() => {
                    progressDiv.textContent = '';
                }, 2000);
            }
        });
        
        // Hover 效果
        playBtn.addEventListener('mouseenter', () => {
            playBtn.style.boxShadow = '0 4px 12px rgba(102, 126, 234, 0.35)';
            playBtn.style.transform = 'translateY(-1px)';
        });
        playBtn.addEventListener('mouseleave', () => {
            playBtn.style.boxShadow = '0 2px 4px rgba(102, 126, 234, 0.2)';
            playBtn.style.transform = 'translateY(0)';
        });
        if (stopBtn) {
            stopBtn.addEventListener('mouseenter', () => {
                stopBtn.style.boxShadow = '0 4px 12px rgba(99, 102, 241, 0.35)';
                stopBtn.style.transform = 'translateY(-1px)';
            });
            stopBtn.addEventListener('mouseleave', () => {
                stopBtn.style.boxShadow = '0 2px 4px rgba(99, 102, 241, 0.2)';
                stopBtn.style.transform = 'translateY(0)';
            });
        }
    }
}

// 初始化应用
document.addEventListener('DOMContentLoaded', () => {
    // 确保所有依赖都已加载
    let retryCount = 0;
    const MAX_RETRIES = 30; // 最多重试30次（3秒）
    
    const initApp = () => {
        if (window.__appInitialized) {
            return;
        }
        // 检查必要的依赖
        if (typeof AgentSystem === 'undefined') {
            retryCount++;
            if (retryCount < MAX_RETRIES) {
                console.warn('AgentSystem not loaded, retrying... (' + retryCount + '/' + MAX_RETRIES + ')');
                setTimeout(initApp, 100);
            } else {
                console.error('AgentSystem failed to load after ' + MAX_RETRIES + ' attempts');
            }
            return;
        }
        
        // 重置重试计数
        retryCount = 0;
        
        // 如果 agentSystem 还未初始化，先初始化它
        if (!window.agentSystem) {
            try {
                window.agentSystem = new AgentSystem();
                console.log('AgentSystem initialized in main.js');
            } catch (error) {
                console.error('Failed to initialize AgentSystem:', error);
            }
        }
        
        // 初始化主控制器
        if (!window.appController) {
            window.appController = new AppController();
        }
        window.__appInitialized = true;
        
        // 添加一些示例交互
        console.log('NovaStar AI 学习与情感陪伴 Agent 已启动');
        console.log('功能：语音交互、多Agent协作、生成式交互');
    };
    
    // 延迟一点初始化，确保所有脚本都已加载
    setTimeout(initApp, 50);
});