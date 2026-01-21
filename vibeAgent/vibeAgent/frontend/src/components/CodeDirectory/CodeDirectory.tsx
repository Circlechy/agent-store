import { useMemo, useState, useEffect } from 'react'
import { Tree, Tabs, Button, Space, Typography, message, Spin } from 'antd'
import { FolderOutlined, FileOutlined, BranchesOutlined, DownloadOutlined, PlayCircleOutlined } from '@ant-design/icons'
import type { DataNode } from 'antd/es/tree'
import Editor from '@monaco-editor/react'
import FileViewer from '../FileViewer/FileViewer'
import WorkflowDiagram from '../WorkflowDiagram/WorkflowDiagram'

interface CodeDirectoryProps {
  files?: FileTreeItem[]
  workflow?: any
  workflowDirectory?: string  // 工作流目录路径，用于从服务器读取文件
  agentMode?: 'agent' | 'workflow' | 'multi_agent'
  onTabChange?: (activeKey: string) => void  // 外部控制tab切换的回调
  defaultActiveTab?: string  // 默认激活的tab
  isBuildCompleted?: boolean  // 是否所有代码生成完成
  onTestRun?: () => void  // 试运行回调
}

export interface FileTreeItem {
  name: string
  path: string
  type: 'file' | 'directory'
  content?: string
  children?: FileTreeItem[]
}

function CodeDirectory({ files = [], workflow, workflowDirectory, agentMode = 'workflow', onTabChange, defaultActiveTab, isBuildCompleted = false, onTestRun }: CodeDirectoryProps) {
  const [selectedFile, setSelectedFile] = useState<FileTreeItem | null>(null)
  const [viewerVisible, setViewerVisible] = useState(false)
  const [activeTab, setActiveTab] = useState<string>(defaultActiveTab || 'files')
  const [isDownloading, setIsDownloading] = useState(false)
  const [loadingFile, setLoadingFile] = useState(false)
  const [previewContent, setPreviewContent] = useState<string>('')

  // 当外部传入的defaultActiveTab变化时，同步更新内部状态
  useEffect(() => {
    if (defaultActiveTab) {
      setActiveTab(defaultActiveTab)
    }
  }, [defaultActiveTab])

  // 获取 workflow_builder.py 的内容
  const workflowBuilderFile = files.find(f => f.name === 'workflow_builder.py')
  const workflowBuilderCode = workflowBuilderFile?.content || ''

  const testRunButton = onTestRun ? (
    <Button
      size="small"
      type={isBuildCompleted ? 'primary' : 'default'}
      icon={<PlayCircleOutlined />}
      onClick={onTestRun}
      disabled={!isBuildCompleted}
      style={{
        background: isBuildCompleted ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' : undefined,
        border: isBuildCompleted ? 'none' : undefined,
      }}
    >
      试运行
    </Button>
  ) : null

  // 当 workflowBuilderCode 更新或切换到 diagram 标签时，触发流程图刷新
  // 使用一个 key 来强制重新渲染 WorkflowDiagram 组件
  const [diagramRefreshKey, setDiagramRefreshKey] = useState(0)
  useEffect(() => {
    // 当切换到流程图标签页且有 workflowBuilderCode 时，触发刷新
    if (activeTab === 'diagram' && workflowBuilderCode) {
      console.log('CodeDirectory: 触发流程图刷新', {
        hasCode: !!workflowBuilderCode,
        codeLength: workflowBuilderCode.length,
        activeTab
      })
      // 立即触发刷新，不延迟
      setDiagramRefreshKey((prev) => prev + 1)
    }
  }, [workflowBuilderCode, activeTab])

  const fileList = useMemo(() => files.filter((f) => f.type === 'file'), [files])

  // 在 Agent 和 Multi-Agent 模式下，如果当前在流程图标签页，自动切换回代码文件标签页
  useEffect(() => {
    if ((agentMode === 'agent' || agentMode === 'multi_agent') && activeTab === 'diagram') {
      setActiveTab('files')
    }
  }, [agentMode, activeTab])

  // 将文件列表转换为树形结构
  const buildTree = (items: FileTreeItem[]): DataNode[] => {
    if (items.length === 0) return []

    const tree: DataNode[] = []
    const pathMap = new Map<string, DataNode>()

    items.forEach((item) => {
      const parts = item.path.split(/[/\\]/).filter(Boolean)
      let currentPath = ''

      parts.forEach((part, index) => {
        const parentPath = currentPath
        currentPath = currentPath ? `${currentPath}/${part}` : part
        const isFile = index === parts.length - 1 && item.type === 'file'

        if (!pathMap.has(currentPath)) {
          const node: DataNode = {
            title: (
              <span>
                {isFile ? <FileOutlined style={{ marginRight: '8px' }} /> : <FolderOutlined style={{ marginRight: '8px' }} />}
                {part}
              </span>
            ),
            key: currentPath,
            isLeaf: isFile,
            children: isFile ? undefined : [],
          }

          if (parentPath && pathMap.has(parentPath)) {
            const parent = pathMap.get(parentPath)!
            if (parent.children) {
              parent.children.push(node)
            }
          } else {
            tree.push(node)
          }

          pathMap.set(currentPath, node)
        }
      })
    })

    return tree
  }

  const treeData = buildTree(files)

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  const handleDownloadAll = async () => {
    if (!fileList.length) {
      message.warning('暂无可下载的代码文件')
      return
    }

    setIsDownloading(true)
    try {
      const { zipSync, strToU8 } = await import('fflate')

      // 尽可能补齐文件内容（如果 content 为空且提供了 workflowDirectory）
      const { incrementalBuildAPI } = await import('../../services/api')
      const fileEntries: Record<string, Uint8Array> = {}

      for (const f of fileList) {
        let content = f.content
        if ((!content || content.length === 0) && workflowDirectory) {
          try {
            const result: any = await incrementalBuildAPI.getFiles({
              workflow_dir: workflowDirectory,
              file_name: f.name,
            })
            if (result?.success && typeof result.content === 'string') {
              content = result.content
            }
          } catch (e) {
            // 如果拉取失败，继续用空内容占位，避免整个下载失败
            console.warn('读取文件内容失败:', f.name, e)
          }
        }

        const zipPath = (f.path || f.name).replace(/\\/g, '/')
        fileEntries[zipPath] = strToU8(content ?? '')
      }

      const zipped = zipSync(fileEntries, { level: 6 })
      // TS/DOM 类型兼容：显式拷贝到新的 Uint8Array（其 buffer 为标准 ArrayBuffer）
      const safeArrayBuffer = new Uint8Array(zipped).buffer
      const blob = new Blob([safeArrayBuffer], { type: 'application/zip' })
      downloadBlob(blob, 'generated_code.zip')
      message.success('下载已开始')
    } catch (e: any) {
      console.error('下载失败:', e)
      message.error(`下载失败: ${e?.message || '未知错误'}`)
    } finally {
      setIsDownloading(false)
    }
  }

  const handleSelect = async (selectedKeys: React.Key[]) => {
    if (selectedKeys.length === 0) {
      setSelectedFile(null)
      setPreviewContent('')
      return
    }
    
    const selectedPath = selectedKeys[0] as string
    const findFile = (items: FileTreeItem[], path: string): FileTreeItem | null => {
      for (const item of items) {
        if (item.path === path && item.type === 'file') {
          return item
        }
        if (item.children) {
          const found = findFile(item.children, path)
          if (found) return found
        }
      }
      return null
    }
    
    const file = findFile(files, selectedPath)
    if (file && file.type === 'file') {
      setSelectedFile(file)

      // 如果文件内容为空，尝试从服务器读取
      if (!file.content && workflowDirectory) {
        setLoadingFile(true)
        try {
          const { incrementalBuildAPI } = await import('../../services/api')
          const result: any = await incrementalBuildAPI.getFiles({
            workflow_dir: workflowDirectory,
            file_name: file.name,
          })
          if (result?.success && result.content) {
            setPreviewContent(result.content)
            // 更新文件内容（用于下载等功能）
            const updatedFile = { ...file, content: result.content }
            setSelectedFile(updatedFile)
          } else {
            setPreviewContent('')
          }
        } catch (error) {
          console.error('读取文件内容失败:', error)
          setPreviewContent('')
          message.error('读取文件内容失败')
        } finally {
          setLoadingFile(false)
        }
      } else {
        setPreviewContent(file.content || '')
      }
    }
  }

  // 当文件列表更新时，自动选择最新生成的文件并在右侧预览
  useEffect(() => {
    if (fileList.length > 0) {
      const lastFile = fileList[fileList.length - 1]
      setSelectedFile(lastFile)
      setPreviewContent(lastFile.content || '')
    } else {
      setSelectedFile(null)
      setPreviewContent('')
    }
  }, [fileList])

  // 获取文件语言类型
  const getFileLanguage = (fileName: string): string => {
    if (fileName.endsWith('.py')) return 'python'
    if (fileName.endsWith('.yaml') || fileName.endsWith('.yml')) return 'yaml'
    if (fileName.endsWith('.json')) return 'json'
    if (fileName.endsWith('.txt')) return 'plaintext'
    if (fileName.endsWith('Dockerfile')) return 'dockerfile'
    if (fileName.endsWith('.js') || fileName.endsWith('.jsx')) return 'javascript'
    if (fileName.endsWith('.ts') || fileName.endsWith('.tsx')) return 'typescript'
    if (fileName.endsWith('.md')) return 'markdown'
    return 'plaintext'
  }

  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        // 中部区域保持白色主卡片，由外层页面提供浅灰蓝背景
        background: '#fff',
        // 使用 hidden 确保容器不会超出父容器高度
        overflow: 'hidden',
      }}
    >
      <Tabs
        activeKey={activeTab}
        onChange={(key) => {
          setActiveTab(key)
          if (onTabChange) {
            onTabChange(key)
          }
        }}
        tabBarExtraContent={{
          right: (
            <div style={{ display: 'flex', alignItems: 'center', paddingRight: 12 }}>
              {testRunButton}
            </div>
          ),
        }}
        items={[
          {
            key: 'files',
            label: (
              <span>
                <FileOutlined />
                代码文件
              </span>
            ),
            children: (
              <div style={{ height: 'calc(100vh - 200px)', display: 'flex', flexDirection: 'row', overflow: 'hidden' }}>
                {/* 左侧：文件树 */}
                <div
                  style={{
                    width: '280px',
                    borderRight: '1px solid rgba(148,163,184,0.3)',
                    display: 'flex',
                    flexDirection: 'column',
                    overflow: 'hidden',
                  }}
                >
                  {/* 标头 + 下载按钮 */}
                  <div
                    style={{
                      padding: '12px 16px',
                      borderBottom: '2px solid transparent',
                      borderImage: 'linear-gradient(to right, #667eea, #764ba2) 1',
                      background: 'linear-gradient(to right, rgba(102,126,234,0.06), rgba(118,75,162,0.06))',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 12,
                    }}
                  >
                    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
                      <Typography.Title
                        level={5}
                        style={{
                          margin: 0,
                          fontSize: 14,
                          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                          WebkitBackgroundClip: 'text',
                          WebkitTextFillColor: 'transparent',
                          backgroundClip: 'text',
                        }}
                      >
                        代码文件
                      </Typography.Title>
                      <Typography.Text type="secondary" style={{ fontSize: 11, marginTop: 2 }}>
                        共 {fileList.length} 个文件
                      </Typography.Text>
                    </div>
                    <Space>
                      <Button
                        size="small"
                        icon={<DownloadOutlined />}
                        onClick={handleDownloadAll}
                        loading={isDownloading}
                        disabled={!fileList.length}
                      >
                        下载全部
                      </Button>
                    </Space>
                  </div>

                  {/* 文件树列表 */}
                  <div style={{ flex: 1, overflow: 'auto', padding: '12px' }}>
                    {treeData.length > 0 ? (
                      <div
                        style={{
                          background: 'linear-gradient(135deg, rgba(248,250,252,0.95) 0%, rgba(239,246,255,0.95) 100%)',
                          borderRadius: 8,
                          padding: 10,
                          border: '1px solid rgba(148,163,184,0.5)',
                        }}
                      >
                        <Tree
                          defaultExpandAll
                          onSelect={handleSelect}
                          treeData={treeData}
                          style={{ background: 'transparent' }}
                        />
                      </div>
                    ) : (
                      <div
                        style={{
                          textAlign: 'center',
                          color: '#999',
                          padding: '40px 20px',
                          borderRadius: 8,
                          border: '1px dashed #d9d9d9',
                          background: '#fafafa',
                        }}
                      >
                        <div style={{ fontSize: 14, marginBottom: 8 }}>暂无代码文件</div>
                        <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                          运行一次构建后，这里会展示自动生成的代码文件。
                        </Typography.Text>
                      </div>
                    )}
                  </div>
                </div>

                {/* 右侧：代码预览区域 */}
                <div
                  style={{
                    flex: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    overflow: 'hidden',
                    background: '#fff',
                    minHeight: 0,
                  }}
                >
                  {selectedFile ? (
                    <>
                      {/* 预览区域标头 */}
                      <div
                        style={{
                          padding: '12px 16px',
                          borderBottom: '2px solid transparent',
                          borderImage: 'linear-gradient(to right, #667eea, #764ba2) 1',
                          background: 'linear-gradient(to right, rgba(102,126,234,0.06), rgba(118,75,162,0.06))',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <FileOutlined style={{ color: '#3b82f6' }} />
                          <Typography.Text strong style={{ fontSize: 14, color: '#111827' }}>
                            {selectedFile.name}
                          </Typography.Text>
                          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                            {selectedFile.path !== selectedFile.name ? `(${selectedFile.path})` : ''}
                          </Typography.Text>
                        </div>
                        <Space>
                          <Button
                            size="small"
                            icon={<DownloadOutlined />}
                            onClick={() => {
                              const blob = new Blob([previewContent || selectedFile.content || ''], {
                                type: 'text/plain;charset=utf-8',
                              })
                              const url = URL.createObjectURL(blob)
                              const a = document.createElement('a')
                              a.href = url
                              a.download = selectedFile.name || 'file.txt'
                              document.body.appendChild(a)
                              a.click()
                              a.remove()
                              URL.revokeObjectURL(url)
                            }}
                            disabled={!previewContent && !selectedFile.content}
                          >
                            下载
                          </Button>
                          <Button
                            size="small"
                            onClick={() => {
                              setViewerVisible(true)
                            }}
                          >
                            全屏查看
                          </Button>
                        </Space>
                      </div>

                      {/* 代码编辑器 */}
                      <div style={{ flex: 1, position: 'relative', minHeight: '500px', overflow: 'auto' }}>
                        {loadingFile ? (
                          <div
                            style={{
                              position: 'absolute',
                              top: 0,
                              left: 0,
                              right: 0,
                              bottom: 0,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              background: 'rgba(255, 255, 255, 0.8)',
                              zIndex: 10,
                            }}
                          >
                            <Spin size="large" tip="正在加载文件内容..." />
                          </div>
                        ) : (
                          <Editor
                            height="100%"
                            defaultLanguage={getFileLanguage(selectedFile.name)}
                            value={previewContent || selectedFile.content || ''}
                            theme="vs-dark"
                            options={{
                              readOnly: true,
                              minimap: { enabled: true },
                              fontSize: 14,
                              wordWrap: 'on',
                              scrollBeyondLastLine: false,
                              automaticLayout: true,
                            }}
                          />
                        )}
                      </div>
                    </>
                  ) : (
                    <div
                      style={{
                        flex: 1,
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#999',
                        padding: '40px',
                      }}
                    >
                      <FileOutlined style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }} />
                      <Typography.Title level={4} type="secondary" style={{ margin: 0, marginBottom: 8 }}>
                        选择文件以预览代码
                      </Typography.Title>
                      <Typography.Text type="secondary" style={{ fontSize: 14, textAlign: 'center', maxWidth: 400 }}>
                        在左侧文件树中点击任意文件，即可在此处查看完整代码内容。支持语法高亮、代码搜索等功能。
                      </Typography.Text>
                    </div>
                  )}
                </div>
              </div>
            ),
          },
          // Agent 和 Multi-Agent 模式下不显示流程图标签页
          ...(agentMode === 'workflow' ? [{
            key: 'diagram',
            label: (
              <span>
                <BranchesOutlined />
                流程图
              </span>
            ),
            children: workflowBuilderCode ? (
              <div style={{ height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                {/* 关键：为流程图区域提供可滚动容器，避免外层 flex/overflow:hidden 吞掉滚动条 */}
                <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
                  <WorkflowDiagram
                    workflowBuilderCode={workflowBuilderCode}
                    workflow={workflow}
                    style={{ border: 'none', height: '100%' }}
                    key={`diagram-${diagramRefreshKey}-${workflowBuilderCode?.substring(0, 100)}`} // 添加 key 确保文件更新时重新渲染
                    isBuildCompleted={isBuildCompleted}
                    onTestRun={onTestRun}
                  />
                </div>
              </div>
            ) : (
              <div
                style={{
                  height: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#999',
                }}
              >
                等待生成 workflow_builder.py 文件...
              </div>
            ),
          }] : []),
        ]}
        style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
        tabBarStyle={{ margin: 0, padding: '0 16px', flexShrink: 0 }}
      />

      {selectedFile && (
        <FileViewer
          visible={viewerVisible}
          fileName={selectedFile.name}
          content={selectedFile.content || ''}
          onClose={() => {
            setViewerVisible(false)
            setSelectedFile(null)
          }}
        />
      )}
    </div>
  )
}

export default CodeDirectory

