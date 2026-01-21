import { useEffect, useRef, useState } from 'react'
import { Card, Spin, Typography, Button, Space, message } from 'antd'
import { ReloadOutlined, DownloadOutlined, PlayCircleOutlined } from '@ant-design/icons'
import { mermaidAPI } from '../../services/api'
import mermaid from 'mermaid'

const { Title } = Typography

interface WorkflowDiagramProps {
  workflowBuilderCode?: string
  workflow?: any
  style?: React.CSSProperties
  isBuildCompleted?: boolean  // 是否所有代码生成完成
  onTestRun?: () => void  // 试运行回调
}

function WorkflowDiagram({ workflowBuilderCode, workflow, style, isBuildCompleted = false, onTestRun }: WorkflowDiagramProps) {
  const diagramRef = useRef<HTMLDivElement>(null)
  const viewportRef = useRef<HTMLDivElement>(null)
  const [mermaidCode, setMermaidCode] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 画布平移/缩放（前端交互层，不影响 mermaid SVG 本身）
  const [scale, setScale] = useState(1)
  const [translate, setTranslate] = useState({ x: 0, y: 0 })
  const isPanningRef = useRef(false)
  const lastPointerRef = useRef<{ x: number; y: number } | null>(null)

  const resetView = () => {
    setScale(1)
    setTranslate({ x: 0, y: 0 })
  }

  useEffect(() => {
    if (workflowBuilderCode || workflow) {
      console.log('WorkflowDiagram: 检测到代码变化，重新生成流程图', {
        hasCode: !!workflowBuilderCode,
        codeLength: workflowBuilderCode?.length || 0,
        hasWorkflow: !!workflow,
        codePreview: workflowBuilderCode?.substring(0, 100)
      })
      // 延迟一下，确保组件完全挂载
      const timer = setTimeout(() => {
        generateDiagram()
      }, 100)
      return () => clearTimeout(timer)
    }
  }, [workflowBuilderCode, workflow])

  const generateDiagram = async () => {
    if (!workflowBuilderCode && !workflow) {
      console.log('WorkflowDiagram: 没有代码或工作流数据，跳过生成')
      return
    }

    setLoading(true)
    setError(null)

    try {
      let result
      if (workflowBuilderCode) {
        // 从代码生成
        console.log('WorkflowDiagram: 从代码生成流程图，代码长度:', workflowBuilderCode.length)
        result = await mermaidAPI.generateFromCode(workflowBuilderCode)
      } else if (workflow) {
        // 从工作流数据生成
        console.log('WorkflowDiagram: 从工作流数据生成流程图')
        result = await mermaidAPI.generateFromWorkflow(workflow)
      } else {
        return
      }

      const data = result as any
      console.log('WorkflowDiagram: API 返回结果', { success: data.success, hasMermaid: !!data.mermaid })
      
      if (data.success && data.mermaid) {
        setMermaidCode(data.mermaid)
        console.log('WorkflowDiagram: Mermaid 代码已设置，准备渲染', { mermaidLength: data.mermaid.length })
        // 延迟渲染，确保 DOM 已更新
        setTimeout(() => {
          renderMermaid()
        }, 100)
      } else {
        throw new Error(data.error || '生成流程图失败')
      }
    } catch (err: any) {
      console.error('生成流程图失败:', err)
      setError(err.message || '生成流程图失败')
      message.error('生成流程图失败: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // 初始化 mermaid（只初始化一次）
    if (!(window as any).mermaidInitialized) {
      mermaid.initialize({
        startOnLoad: false,
        theme: 'default',
        flowchart: {
          useMaxWidth: false,
          htmlLabels: true,
          curve: 'basis',
          nodeSpacing: 80,
          rankSpacing: 80,
          padding: 20,
        },
        securityLevel: 'loose',
      })
      ;(window as any).mermaidInitialized = true
    }
  }, [])

  const renderMermaid = async () => {
    if (!diagramRef.current || !mermaidCode) {
      console.log('WorkflowDiagram: 无法渲染，缺少容器或代码', {
        hasRef: !!diagramRef.current,
        hasCode: !!mermaidCode
      })
      return
    }

    try {
      console.log('WorkflowDiagram: 开始渲染 Mermaid', { mermaidCode })
      // 清空容器
      diagramRef.current.innerHTML = ''

      // 生成唯一ID
      const id = `mermaid-${Date.now()}`

      // 渲染流程图
      const { svg } = await mermaid.render(id, mermaidCode)
      diagramRef.current.innerHTML = svg
      console.log('WorkflowDiagram: Mermaid 渲染成功', { svgLength: svg.length })

      // 设置SVG样式，确保有合适的尺寸
      const svgElement = diagramRef.current.querySelector('svg')
      if (svgElement) {
        // 设置最小宽度和高度
        svgElement.style.minWidth = '800px'
        svgElement.style.minHeight = '500px'
        // 保持原有的宽高比，但确保足够大
        const viewBox = svgElement.getAttribute('viewBox')
        if (viewBox) {
          const [, , width, height] = viewBox.split(' ').map(Number)
          // 如果原始尺寸太小，放大SVG
          if (width < 800) {
            svgElement.style.width = '800px'
          }
          if (height < 500) {
            svgElement.style.height = '500px'
          }
        }
      }

      // 渲染完成后，重置视图
      setScale(1)
      setTranslate({ x: 0, y: 0 })
    } catch (err: any) {
      console.error('渲染 Mermaid 失败:', err)
      setError(err.message || '渲染流程图失败')
    }
  }

  const onPointerDown = (e: React.PointerEvent) => {
    // 只响应主键拖拽
    if (e.button !== 0) return
    // 必须在有流程图时才允许拖拽
    if (!mermaidCode) return

    isPanningRef.current = true
    lastPointerRef.current = { x: e.clientX, y: e.clientY }
    ;(e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId)
  }

  const onPointerMove = (e: React.PointerEvent) => {
    if (!isPanningRef.current || !lastPointerRef.current) return
    const dx = e.clientX - lastPointerRef.current.x
    const dy = e.clientY - lastPointerRef.current.y
    lastPointerRef.current = { x: e.clientX, y: e.clientY }
    setTranslate((prev) => ({ x: prev.x + dx, y: prev.y + dy }))
  }

  const endPan = (e: React.PointerEvent) => {
    if (!isPanningRef.current) return
    isPanningRef.current = false
    lastPointerRef.current = null
    try {
      ;(e.currentTarget as HTMLDivElement).releasePointerCapture(e.pointerId)
    } catch {
      // ignore
    }
  }

  const onWheel = (e: React.WheelEvent) => {
    // 为了不影响正常滚动：仅在按住 Ctrl/⌘ 时缩放
    if (!(e.ctrlKey || e.metaKey)) return
    e.preventDefault()

    const delta = -e.deltaY
    const zoomFactor = delta > 0 ? 1.08 : 0.92
    setScale((prev) => {
      const next = Math.min(4, Math.max(0.2, prev * zoomFactor))
      return next
    })
  }

  const handleDownload = () => {
    if (!diagramRef.current) {
      return
    }

    const svg = diagramRef.current.querySelector('svg')
    if (!svg) {
      message.warning('没有可下载的流程图')
      return
    }

    // 将 SVG 转换为图片
    const svgData = new XMLSerializer().serializeToString(svg)
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    const img = new Image()

    img.onload = () => {
      canvas.width = img.width
      canvas.height = img.height
      ctx?.drawImage(img, 0, 0)
      
      canvas.toBlob((blob) => {
        if (blob) {
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = 'workflow-diagram.png'
          a.click()
          URL.revokeObjectURL(url)
        }
      })
    }

    img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)))
  }

  if (!workflowBuilderCode && !workflow) {
    return (
      <Card style={style}>
        <div style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
          <Typography.Text type="secondary">等待生成工作流代码...</Typography.Text>
        </div>
      </Card>
    )
  }

  return (
    <Card
      style={style}
      headStyle={{
        borderBottom: '2px solid transparent',
        borderImage: 'linear-gradient(to right, #667eea, #764ba2) 1',
        background: 'linear-gradient(to right, rgba(102,126,234,0.06), rgba(118,75,162,0.06))',
      }}
      title={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Title
            level={5}
            style={{
              margin: 0,
              fontSize: 16,
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <span role="img" aria-label="workflow">
              🧩
            </span>
            工作流流程图
          </Title>
          <Space>
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={generateDiagram}
              loading={loading}
            >
              刷新
            </Button>
            {mermaidCode && (
              <Button size="small" onClick={resetView}>
                重置视图
              </Button>
            )}
            {mermaidCode && (
              <Button
                size="small"
                icon={<DownloadOutlined />}
                onClick={handleDownload}
              >
                下载
              </Button>
            )}
          </Space>
        </div>
      }
    >
      {loading && (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <Spin size="large" />
          <div style={{ marginTop: '16px', color: '#999' }}>正在生成流程图...</div>
        </div>
      )}

      {error && (
        <div style={{ padding: '20px', textAlign: 'center', color: '#ff4d4f' }}>
          <Typography.Text type="danger">{error}</Typography.Text>
        </div>
      )}

      {!loading && !error && (
        <div
          style={{
            width: '100%',
            minHeight: '600px',
            overflow: 'auto',
            background:
              'radial-gradient(circle at top, rgba(129,140,248,0.18), transparent 55%), #ffffff',
            padding: '16px 20px 20px 20px',
          }}
        >
          <div
            ref={viewportRef}
            style={{
              width: '100%',
              minHeight: '600px',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              cursor: mermaidCode ? (isPanningRef.current ? 'grabbing' : 'grab') : 'default',
              touchAction: 'none',
            }}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={endPan}
            onPointerCancel={endPan}
            onPointerLeave={endPan}
            onWheel={onWheel}
          >
            {!mermaidCode ? (
              <Typography.Text type="secondary">点击刷新按钮生成流程图</Typography.Text>
            ) : (
              <div
                style={{
                  transform: `translate(${translate.x}px, ${translate.y}px) scale(${scale})`,
                  transformOrigin: 'center center',
                  willChange: 'transform',
                }}
              >
                <div
                  ref={diagramRef}
                  style={{
                    width: 'auto',
                    minWidth: '800px',
                    minHeight: '500px',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                  }}
                />
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  )
}

export default WorkflowDiagram

