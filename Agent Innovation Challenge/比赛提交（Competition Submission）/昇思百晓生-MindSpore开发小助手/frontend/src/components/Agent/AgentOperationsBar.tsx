import { ENV_CONFIG } from '@/config/environment'
import { Button, TextField, Tooltip } from '@mui/material'
import { Play, Square, BrushCleaning, Upload } from 'lucide-react'
import { useRef, useState} from 'react'
import { useScopedTranslation } from '@/i18n'


interface AgentOperationsBarProps {
  value: string
  onChange: (value: string) => void
  onSend: (attachment?: string) => void
  onCancel?: () => void
  onClearChat?: () => void
  disabled?: boolean
  placeholder?: string
  inputDisabled?: boolean
  isProcessing?: boolean
  onInputFocusChange?: (focused: boolean) => void
  uploadFile?: string
  uploadFileUrl?: string
}

const AgentOperationsBar = ({
  value,
  onChange,
  onSend,
  onCancel,
  onClearChat,
  disabled = false,
  placeholder,
  inputDisabled = false,
  isProcessing = false,
  onInputFocusChange,
}: AgentOperationsBarProps) => {
  const { t } = useScopedTranslation('agents.agentEditor.previewDebug.operationsBar')
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [uploadFile, setUploadFile] = useState<string>("");
  const [uploadFileUrl, setUploadFileUrl] = useState<string>("");
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      // 检查是否为ZIP文件
      if (file.type === 'application/zip' || file.name.toLowerCase().endsWith('.zip')
      || file.name.toLowerCase().endsWith('.png') || file.name.toLowerCase().endsWith('.jpg')
      || file.name.toLowerCase().endsWith('.jpeg')) {
        try {
          // 创建FormData对象用于上传文件
          const formData = new FormData();
          formData.append('file', file);

          // 发送POST请求到服务器
          if  (ENV_CONFIG.UPLOAD_SERVER_URL) {
            var upload_server_url = ENV_CONFIG.UPLOAD_SERVER_URL
          } else {
            var upload_server = "127.0.0.1"
            if(typeof window !== 'undefined') {
               upload_server = window.location.hostname
            }
            var upload_server_url = "http://" + upload_server + ":8185/demo/upload"  
          }

          console.log('Upload URL:', upload_server_url);
          const response = await fetch(upload_server_url, {
            method: 'POST',
            body: formData,
          });

          if (response.ok) {
            const result = await response.json();
            console.log('File uploaded successfully:', result);
            // 通过回调函数更新父组件状态
            setUploadFile(file.name)
            setUploadFileUrl(result.torch_file_url)
            // 可以在这里处理服务器返回的结果
          } else {
            console.error('File upload failed:', response.status);
            alert('文件上传失败');
            setUploadFileUrl("");
          }
          event.target.value = ''; // 清空input值，以便可以选择同一文件
        } catch (error) {
          console.error('Error uploading file:', error);
          alert('上传过程中发生错误');
          setUploadFileUrl("");
        }
      } else {
        alert('请选择一个ZIP文件');
        // 清空input值，以便可以选择同一文件
        event.target.value = '';
        setUploadFileUrl("");
      }
    }
  };

  return (
    <div className="bg-white rounded-xl p-3 border border-gray-200 shadow-sm">
      <div className="flex items-center space-x-3">
        <Tooltip title={t('tooltips.clearChat')} placement="top">
          <Button
            variant="text"
            onClick={onClearChat ? onClearChat : undefined}
            size="small"
            sx={{
              borderRadius: '12px',
              textTransform: 'none',
              color: '#6B7280',
              padding: '4px 4px',
              minWidth: 'unset',
              width: '32px',
              height: '32px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              '&:hover': {
                backgroundColor: '#F3F4F6',
                color: '#374151',
              },
            }}
          >
            <BrushCleaning className="w-4 h-4" />
          </Button>
        </Tooltip>

        <TextField
          fullWidth
          value={value}
          onChange={e => {
            // 如果输入被禁用，阻止任何更改
            if (inputDisabled) return
            onChange(e.target.value)
          }}
          placeholder={placeholder || t('placeholders.inputMessage')}
          onFocus={() => onInputFocusChange?.(true)}
          onBlur={() => onInputFocusChange?.(false)}
          onKeyPress={e => {
            if (disabled || inputDisabled) return
            if (e.key === 'Enter') {
              onSend(uploadFileUrl)
              setUploadFile("")
              setUploadFileUrl("")
            }
          }}
          size="small"
          className="flex-1"
          sx={{
            '& .MuiOutlinedInput-root': {
              borderRadius: '12px',
              '&:hover fieldset': {
                borderColor: '#3B82F6',
              },
              // 当禁用时添加额外的视觉提示
              '&.Mui-disabled fieldset': {
                borderColor: '#D1D5DB',
              },
            },
          }}
          disabled={inputDisabled}
          InputProps={{
            style: {
              backgroundColor: inputDisabled ? '#F5F5F5' : 'white',
              cursor: inputDisabled ? 'not-allowed' : 'text',
            },
            readOnly: inputDisabled, // 使用 readOnly 作为额外的保护
          }}
          inputProps={{ 'data-agent-chat-input': 'true' }}
          inputRef={inputRef}
        />
        
        <Tooltip title="上传文件" placement="top">
        <Button
          variant="text"
          component="label"  // 让 Button 表现为 label 标签
          startIcon={<Upload className="w-4 h-4" />}
          className="flex items-center space-x-3"
          size="small"
          sx={{
            borderRadius: '12px',
            borderColor: '#D1D5DB',
            color: '#4B5563',
            '&:hover': {
              borderColor: '#3B82F6',
              backgroundColor: '#F0F9FF',
            },
          }}
        >
          {uploadFile}
          <input
            type="file"
            hidden
            accept=".zip;*.png,image/jpeg"
            onChange={handleFileUpload}
          />
        </Button>
        </Tooltip>

        {!isProcessing && (
          <Button
            variant="contained"
            startIcon={<Play className="w-4 h-4" />}
            onClick={() => {
              onSend(uploadFileUrl)
              if (!disabled && !inputDisabled) {
                inputRef.current?.focus()
              }
              setUploadFile("")
              setUploadFileUrl("")
            }}
            disabled={disabled}
            className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 shadow-sm px-4 rounded-xl"
            size="small"
            sx={{
              borderRadius: '12px',
              textTransform: 'none',
              fontWeight: 600,
            }}
          >
            {t('buttons.send')}
          </Button>
        )}
        {isProcessing && (
          <Button
            variant="contained"
            color="error"
            startIcon={<Square className="w-4 h-4" />}
            onClick={() => {
              onCancel?.()
              if (!inputDisabled) {
                inputRef.current?.focus()
              }
            }}
            disabled={!onCancel}
            className="bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-700 hover:to-rose-700 shadow-sm px-4 rounded-xl"
            size="small"
            sx={{
              borderRadius: '12px',
              textTransform: 'none',
              fontWeight: 600,
            }}
          >
            {t('buttons.cancel')}
          </Button>
        )}
      </div>
    </div>
  )
}

export default AgentOperationsBar
