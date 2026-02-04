import { Modal, Button, Space } from 'antd'
import Editor from '@monaco-editor/react'

interface FileViewerProps {
  visible: boolean
  fileName: string
  content: string
  onClose: () => void
}

function FileViewer({ visible, fileName, content, onClose }: FileViewerProps) {
  const language = fileName.endsWith('.py')
    ? 'python'
    : fileName.endsWith('.yaml') || fileName.endsWith('.yml')
    ? 'yaml'
    : fileName.endsWith('.json')
    ? 'json'
    : fileName.endsWith('.txt')
    ? 'plaintext'
    : fileName.endsWith('Dockerfile')
    ? 'dockerfile'
    : 'plaintext'

  const handleDownload = () => {
    const blob = new Blob([content ?? ''], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName || 'file.txt'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  return (
    <Modal
      title={
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            // 预留出右上角关闭(X)图标的空间，避免按钮与其重叠
            paddingRight: 48,
          }}
        >
          <span style={{ fontWeight: 600 }}>{fileName}</span>
          <Space size="small">
            <Button size="small" onClick={handleDownload}>
              下载
            </Button>
          </Space>
        </div>
      }
      open={visible}
      onCancel={onClose}
      footer={null}
      width="80%"
      style={{ top: 20, zIndex: 1050 }}
      bodyStyle={{ padding: 0, height: '80vh' }}
      maskStyle={{ zIndex: 1040 }}
    >
      <Editor
        height="80vh"
        defaultLanguage={language}
        value={content}
        theme="vs-dark"
        options={{
          readOnly: true,
          minimap: { enabled: true },
          fontSize: 14,
          wordWrap: 'on',
        }}
      />
    </Modal>
  )
}

export default FileViewer

