import { Alert, Collapse, Typography } from 'antd'
import { ExclamationCircleOutlined } from '@ant-design/icons'

const { Panel } = Collapse
const { Text, Paragraph } = Typography

interface ErrorDisplayProps {
  error: any
  title?: string
}

function ErrorDisplay({ error, title = '错误信息' }: ErrorDisplayProps) {
  const errorMessage = error?.message || error?.detail || error?.response?.data?.detail || '未知错误'
  const errorStatus = error?.status || error?.response?.status
  const errorData = error?.response?.data || error?.data || {}

  return (
    <Alert
      message={title}
      description={
        <div>
          <Paragraph>
            <Text strong>错误信息：</Text>
            <Text code>{errorMessage}</Text>
          </Paragraph>
          {errorStatus && (
            <Paragraph>
              <Text strong>状态码：</Text>
              <Text code>{errorStatus}</Text>
            </Paragraph>
          )}
          {Object.keys(errorData).length > 0 && (
            <Collapse size="small" style={{ marginTop: '8px' }}>
              <Panel header="详细错误信息" key="1">
                <pre style={{ fontSize: '12px', margin: 0 }}>
                  {JSON.stringify(errorData, null, 2)}
                </pre>
              </Panel>
            </Collapse>
          )}
        </div>
      }
      type="error"
      icon={<ExclamationCircleOutlined />}
      showIcon
      style={{ marginBottom: '16px' }}
    />
  )
}

export default ErrorDisplay

