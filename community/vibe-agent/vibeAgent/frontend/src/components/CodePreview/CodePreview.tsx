import { useState } from 'react'
import { Tabs } from 'antd'
import Editor from '@monaco-editor/react'

interface CodePreviewProps {
  workflow?: any
}

function CodePreview({ workflow }: CodePreviewProps) {
  const [activeTab, setActiveTab] = useState('main')

  // TODO: 从workflow中获取生成的代码
  const codeFiles = {
    main: workflow?.code || '# 代码将在这里显示',
    requirements: workflow?.requirements || '# requirements.txt',
    dockerfile: workflow?.dockerfile || '# Dockerfile',
  }

  const tabItems = [
    {
      key: 'main',
      label: '主代码',
      children: (
        <Editor
          height="500px"
          defaultLanguage="python"
          value={codeFiles.main}
          theme="vs-dark"
          options={{
            readOnly: true,
            minimap: { enabled: false },
          }}
        />
      ),
    },
    {
      key: 'requirements',
      label: 'requirements.txt',
      children: (
        <Editor
          height="500px"
          defaultLanguage="plaintext"
          value={codeFiles.requirements}
          theme="vs-dark"
          options={{
            readOnly: true,
            minimap: { enabled: false },
          }}
        />
      ),
    },
    {
      key: 'dockerfile',
      label: 'Dockerfile',
      children: (
        <Editor
          height="500px"
          defaultLanguage="dockerfile"
          value={codeFiles.dockerfile}
          theme="vs-dark"
          options={{
            readOnly: true,
            minimap: { enabled: false },
          }}
        />
      ),
    },
  ]

  return (
    <Tabs
      activeKey={activeTab}
      onChange={setActiveTab}
      items={tabItems}
    />
  )
}

export default CodePreview

