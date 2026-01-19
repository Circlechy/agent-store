// ============ 状态轮询 ============

function getStateSignature(state) {
    const sig = {};
    for (const [key, value] of Object.entries(state)) {
        if (key === 'media') {
            sig.media = {
                playing: value.playing,
                track_name: value.track_name,
                volume: value.volume
            };
        } else if (key !== 'cameras') {
            sig[key] = value;
        }
    }
    return JSON.stringify(sig);
}

async function pollState() {
    try {
        const response = await fetch('/api/state');
        if (response.ok) {
            const newState = await response.json();
            const newSig = getStateSignature(newState);
            const oldSig = getStateSignature(currentState);
            
            if (newSig !== oldSig) {
                const changedComponents = [];
                for (const key of Object.keys(newState)) {
                    if (key === 'cameras') continue;
                    const newCompSig = key === 'media' 
                        ? JSON.stringify({playing: newState[key].playing, track_name: newState[key].track_name})
                        : JSON.stringify(newState[key]);
                    const oldCompSig = key === 'media'
                        ? JSON.stringify({playing: currentState[key]?.playing, track_name: currentState[key]?.track_name})
                        : JSON.stringify(currentState[key]);
                    
                    if (newCompSig !== oldCompSig) {
                        changedComponents.push(key);
                    }
                }
                
                currentState = newState;
                changedComponents.forEach(c => updateComponentUI(c, { preferState: c === 'vehicle' }));
                
                if (changedComponents.length === 1) {
                    showToast(`${getComponentName(changedComponents[0])} 已更新`, 'success');
                } else if (changedComponents.length > 1) {
                    showToast('设置已更新', 'success');
                }
            } else if (newState.media) {
                currentState.media = newState.media;
                updateMediaUI();
            }
        }
    } catch (error) {}
}

function getComponentName(component) {
    const names = {
        ac: '空调', windows: '车窗', seats: '座椅',
        lights: '氛围灯', media: '媒体', vehicle: '车辆', navigation: '导航'
    };
    return names[component] || component;
}
