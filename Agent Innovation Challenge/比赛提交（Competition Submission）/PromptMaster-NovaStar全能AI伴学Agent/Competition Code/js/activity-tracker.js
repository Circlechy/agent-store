// 活动数据跟踪器 - 记录儿童端的所有交互
class ActivityTracker {
    constructor() {
        this.storageKey = 'novastar_activity_data';
        this.init();
    }

    init() {
        // 确保数据结构存在
        if (!this.getData()) {
            this.resetData();
        }
    }

    // 获取所有数据
    getData() {
        try {
            const data = localStorage.getItem(this.storageKey);
            return data ? JSON.parse(data) : null;
        } catch (e) {
            console.error('Error reading activity data:', e);
            return null;
        }
    }

    // 保存数据
    saveData(data) {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(data));
        } catch (e) {
            console.error('Error saving activity data:', e);
        }
    }

    // 重置数据结构
    resetData() {
        const data = {
            interactions: [], // 所有互动记录
            interests: [], // 兴趣领域数组
            lastResetDate: this.getTodayDate()
        };
        this.saveData(data);
    }

    // 获取今天的日期字符串 (YYYY-MM-DD)
    getTodayDate() {
        const today = new Date();
        return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    }

    // 获取本周的开始日期
    getWeekStartDate() {
        const today = new Date();
        const day = today.getDay();
        const diff = today.getDate() - day + (day === 0 ? -6 : 1); // 周一为开始
        const monday = new Date(today);
        monday.setDate(diff);
        return `${monday.getFullYear()}-${String(monday.getMonth() + 1).padStart(2, '0')}-${String(monday.getDate()).padStart(2, '0')}`;
    }

    // 记录互动
    recordInteraction(type, category = 'general', metadata = {}) {
        const data = this.getData();
        if (!data) {
            this.resetData();
            return this.recordInteraction(type, category, metadata);
        }

        const today = this.getTodayDate();
        const interaction = {
            type: type, // 'idiom', 'story', 'game', 'learn', 'companion', 'text', 'voice'
            category: category, // 'learning', 'game', 'companion', 'story'
            interest: metadata.interest || null, // 兴趣领域，如 'math', 'language', 'science'
            gameType: metadata.gameType || null, // 游戏类型
            timestamp: Date.now(),
            date: today // 使用今天的日期
        };

        data.interactions.push(interaction);

        // 记录兴趣领域
        if (metadata.interest) {
            if (!data.interests) {
                data.interests = [];
            }
            if (!data.interests.includes(metadata.interest)) {
                data.interests.push(metadata.interest);
            }
        }

        this.saveData(data);
        
        // 统计今天已记录的互动次数
        const todayCount = data.interactions.filter(i => i.date === today).length;
        console.log(`[活动记录] 类型: ${type}, 日期: ${today}, 今日总互动: ${todayCount}`);
        console.log('Interaction recorded:', interaction);
    }

    // 获取本周的学习次数
    getWeeklyLearningCount() {
        const data = this.getData();
        if (!data || !data.interactions) return 0;

        const weekStart = this.getWeekStartDate();
        return data.interactions.filter(interaction => {
            return interaction.date >= weekStart && 
                   (interaction.category === 'learning' || 
                    interaction.type === 'idiom' || 
                    interaction.type === 'learn');
        }).length;
    }

    // 获取本周的活跃兴趣领域数量
    getWeeklyInterestCount() {
        const data = this.getData();
        if (!data || !data.interactions) return 0;

        const weekStart = this.getWeekStartDate();
        const interests = new Set();
        
        data.interactions.filter(interaction => {
            return interaction.date >= weekStart;
        }).forEach(interaction => {
            if (interaction.interest) {
                interests.add(interaction.interest);
            }
            // 根据类型推断兴趣
            if (interaction.type === 'idiom') {
                interests.add('idiom');
            } else if (interaction.type === 'story') {
                interests.add('story');
            } else if (interaction.type === 'game') {
                interests.add('game');
            } else if (interaction.type === 'learn') {
                interests.add('learning');
            } else if (interaction.type === 'companion') {
                interests.add('companion');
            }
        });

        return interests.size;
    }

    // 获取本周的互动次数
    getWeeklyInteractionCount() {
        const data = this.getData();
        if (!data || !data.interactions) return 0;

        const weekStart = this.getWeekStartDate();
        return data.interactions.filter(interaction => {
            return interaction.date >= weekStart;
        }).length;
    }

    // 获取本周的每日互动数据（从周一开始，返回数据和日期标签）
    getDailyInteractionData(days = 7) {
        const data = this.getData();
        const dateLabels = [];
        const dailyCounts = {};
        
        // 获取本周一的日期
        const today = new Date();
        const day = today.getDay();
        const diff = today.getDate() - day + (day === 0 ? -6 : 1); // 周一为开始
        const monday = new Date(today);
        monday.setDate(diff);
        
        // 从周一开始，初始化7天的数据
        for (let i = 0; i < days; i++) {
            const date = new Date(monday);
            date.setDate(monday.getDate() + i);
            const dateStr = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
            dailyCounts[dateStr] = 0;
            
            // 生成日期标签（月/日 星期）
            const weekdays = ['日', '一', '二', '三', '四', '五', '六'];
            const month = date.getMonth() + 1;
            const dayNum = date.getDate();
            const weekday = weekdays[date.getDay()];
            // 格式：月/日\n周X（换行显示，更清晰）
            dateLabels.push(`${month}/${dayNum}\n周${weekday}`);
        }

        // 统计每天的互动次数
        if (data && data.interactions) {
            data.interactions.forEach(interaction => {
                if (dailyCounts.hasOwnProperty(interaction.date)) {
                    dailyCounts[interaction.date]++;
                }
            });
        }

        // 转换为数组（按日期顺序）
        const dates = Object.keys(dailyCounts).sort();
        const values = dates.map(date => dailyCounts[date]);
        
        // 输出调试信息
        console.log('[图表数据] 本周每日互动次数:', dates.map((date, index) => `${dateLabels[index]}: ${values[index]}`).join(', '));
        
        return {
            values: values,
            labels: dateLabels,
            dates: dates
        };
    }

    // 获取过去7天的积极情绪数据（基于互动频率的简单计算）
    getDailyEmotionData(days = 7) {
        const interactionResult = this.getDailyInteractionData(days);
        const interactionData = interactionResult.values;
        
        // 基于真实互动数据计算情绪分数（0-10的评分系统）
        // 互动越多，情绪越积极
        const maxInteractions = Math.max(...interactionData, 1);
        
        return interactionData.map(count => {
            // 基础分数7（对应70%），根据互动次数增加
            // 如果当天有互动，分数会增加
            const baseScore = 7.0; // 基础积极情绪水平
            const interactionBonus = count > 0 ? Math.min((count / Math.max(maxInteractions, 1)) * 2, 2) : 0;
            // 转换为0-10的范围，然后显示为7-9之间
            const emotionScore = Math.min(Math.max(baseScore + interactionBonus, 7.0), 9.0);
            // 保留一位小数，然后转换为整数显示（图表用）
            return Math.round(emotionScore * 10) / 10;
        });
    }

    // 获取每天的详细数据（用于调试）
    getDailyDataSummary() {
        const data = this.getData();
        if (!data || !data.interactions) {
            return null;
        }

        const today = this.getTodayDate();
        const todayInteractions = data.interactions.filter(i => i.date === today);
        
        const interactionResult = this.getDailyInteractionData(7);
        
        return {
            totalInteractions: data.interactions.length,
            todayInteractions: todayInteractions.length,
            todayDate: today,
            weeklyData: interactionResult,
            allDates: [...new Set(data.interactions.map(i => i.date))].sort()
        };
    }

    // 导出数据到JSON文件
    exportToFile() {
        const data = this.getData();
        if (!data) {
            alert('没有可导出的数据');
            return;
        }

        const exportData = {
            exportDate: this.getTodayDate(),
            exportTime: new Date().toISOString(),
            totalInteractions: data.interactions ? data.interactions.length : 0,
            interactions: data.interactions || [],
            interests: data.interests || [],
            summary: {
                weeklyLearningCount: this.getWeeklyLearningCount(),
                weeklyInterestCount: this.getWeeklyInterestCount(),
                weeklyInteractionCount: this.getWeeklyInteractionCount()
            }
        };

        const jsonStr = JSON.stringify(exportData, null, 2);
        const blob = new Blob([jsonStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `novastar_data_${this.getTodayDate().replace(/-/g, '')}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        console.log('Data exported successfully');
    }

    // 清理旧数据（保留最近30天）
    cleanupOldData() {
        const data = this.getData();
        if (!data || !data.interactions) return;

        const thirtyDaysAgo = new Date();
        thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
        const cutoffDate = `${thirtyDaysAgo.getFullYear()}-${String(thirtyDaysAgo.getMonth() + 1).padStart(2, '0')}-${String(thirtyDaysAgo.getDate()).padStart(2, '0')}`;

        data.interactions = data.interactions.filter(interaction => {
            return interaction.date >= cutoffDate;
        });

        this.saveData(data);
    }
}

// 初始化全局活动跟踪器
if (typeof window !== 'undefined') {
    window.activityTracker = new ActivityTracker();
    
    // 定期清理旧数据（每天一次）
    const lastCleanup = localStorage.getItem('novastar_last_cleanup');
    const today = window.activityTracker.getTodayDate();
    if (lastCleanup !== today) {
        window.activityTracker.cleanupOldData();
        localStorage.setItem('novastar_last_cleanup', today);
    }
}
