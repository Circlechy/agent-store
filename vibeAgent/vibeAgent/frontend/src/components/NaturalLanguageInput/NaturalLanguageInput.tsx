import { Input, Button, Space } from 'antd'
import { SendOutlined } from '@ant-design/icons'

const { TextArea } = Input

interface NaturalLanguageInputProps {
  value: string
  onChange: (value: string) => void
  onGenerate: () => void
  loading?: boolean
}

function NaturalLanguageInput({
  value,
  onChange,
  onGenerate,
  loading = false,
}: NaturalLanguageInputProps) {
  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <TextArea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="请描述您想要创建的工作流，例如：创建一个数据处理工作流，从CSV文件读取数据，进行数据清洗，然后保存到数据库..."
        rows={6}
        style={{ fontSize: '16px' }}
      />
      <div style={{ textAlign: 'right' }}>
        <Button
          type="primary"
          size="large"
          icon={<SendOutlined />}
          onClick={onGenerate}
          loading={loading}
          disabled={!value.trim()}
        >
          生成工作流
        </Button>
      </div>
    </Space>
  )
}

export default NaturalLanguageInput

