// ============ 乘客管理 ============

function uploadAvatar(seat) {
    currentEditingSeat = seat;
    document.getElementById('modal-seat-name').textContent = seat === 'driver' ? '主驾' : '副驾';
    document.getElementById('input-passenger-name').value = passengers[seat].name || '';
    
    const previewImg = document.getElementById('preview-avatar');
    const placeholder = document.getElementById('upload-placeholder');
    
    if (passengers[seat].avatar) {
        previewImg.src = passengers[seat].avatar;
        previewImg.style.display = 'block';
        placeholder.style.display = 'none';
    } else {
        previewImg.style.display = 'none';
        placeholder.style.display = 'flex';
    }
    
    document.getElementById('avatar-modal').style.display = 'flex';
}

function closeAvatarModal() {
    document.getElementById('avatar-modal').style.display = 'none';
    currentEditingSeat = null;
}

function initAvatarUpload() {
    document.getElementById('avatar-input').addEventListener('change', e => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = ev => {
                const previewImg = document.getElementById('preview-avatar');
                const placeholder = document.getElementById('upload-placeholder');
                previewImg.src = ev.target.result;
                previewImg.style.display = 'block';
                placeholder.style.display = 'none';
            };
            reader.readAsDataURL(file);
        }
    });
}

async function savePassengerInfo() {
    if (!currentEditingSeat) return;
    
    const previewImg = document.getElementById('preview-avatar');
    const name = document.getElementById('input-passenger-name').value.trim() || 
        (currentEditingSeat === 'driver' ? '主驾驶员' : '副驾乘客');
    const avatarData = previewImg.style.display !== 'none' ? previewImg.src : '';
    
    passengers[currentEditingSeat].name = name;
    passengers[currentEditingSeat].avatar = avatarData || null;
    
    updatePassengerUI(currentEditingSeat);
    localStorage.setItem('passengers', JSON.stringify(passengers));
    
    // 如果修改的是当前说话者，更新显示
    if (currentEditingSeat === currentSpeaker) {
        updateSpeakerDisplay();
    }
    
    try {
        // 头像只存在 localStorage，不发送到后端（避免文件过大）
        if (passengers[currentEditingSeat].id) {
            // 已有 ID，只更新名字
            await fetch(`/api/passengers/${passengers[currentEditingSeat].id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ updates: { name } })
            });
        } else {
            // 没有 ID，先检查是否已存在同名乘客
            const listResponse = await fetch('/api/passengers');
            const listData = await listResponse.json();
            
            let existingProfile = null;
            if (listData.success && listData.passengers) {
                existingProfile = listData.passengers.find(p => p.name === name);
            }
            
            if (existingProfile) {
                // 找到同名乘客，复用其 ID
                passengers[currentEditingSeat].id = existingProfile.id;
            } else {
                // 不存在同名乘客，创建新的（不传头像）
                const response = await fetch('/api/passengers', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name })
                });
                
                const data = await response.json();
                if (data.success && data.profile) {
                    passengers[currentEditingSeat].id = data.profile.id;
                }
            }
            
            // 设置座位乘客
            await fetch('/api/passengers/seat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ seat: currentEditingSeat, passenger_id: passengers[currentEditingSeat].id })
            });
        }
        
        // 头像只存在 localStorage
        localStorage.setItem('passengers', JSON.stringify(passengers));
        showToast('乘客信息已保存', 'success');
    } catch (error) {
        console.error('保存乘客信息失败:', error);
        showToast('保存失败', 'error');
    }
    
    closeAvatarModal();
}

function updatePassengerUI(seat) {
    const info = passengers[seat];
    const avatarImg = document.getElementById(`${seat}-avatar`);
    const placeholder = document.getElementById(`${seat}-placeholder`);
    const nameEl = document.getElementById(`${seat}-name`);
    
    if (info.avatar) {
        avatarImg.src = info.avatar;
        avatarImg.style.display = 'block';
        placeholder.style.display = 'none';
    } else {
        avatarImg.style.display = 'none';
        placeholder.style.display = 'flex';
    }
    
    nameEl.textContent = info.name;
}

function loadPassengerInfo() {
    const saved = localStorage.getItem('passengers');
    if (saved) {
        const parsed = JSON.parse(saved);
        passengers.driver = { ...passengers.driver, ...parsed.driver };
        passengers.passenger = { ...passengers.passenger, ...parsed.passenger };
        updatePassengerUI('driver');
        updatePassengerUI('passenger');
    }
    // 更新说话者显示（显示实际名字）
    updateSpeakerDisplay();
}
