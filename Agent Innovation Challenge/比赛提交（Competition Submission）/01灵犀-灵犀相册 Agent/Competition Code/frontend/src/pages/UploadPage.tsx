import React, { useState, useEffect } from 'react';
import {
  Upload,
  Button,
  Input,
  Tabs,
  Card,
  List,
  Typography,
  message,
  Progress,
  Space,
  Form,
  Checkbox,
  Tag,
  Image,
} from 'antd';
import {
  InboxOutlined,
  LinkOutlined,
  CloudUploadOutlined,
  DeleteOutlined,
  FileImageOutlined,
} from '@ant-design/icons';
import type { UploadFile, UploadProps } from 'antd/es/upload/interface';
import { uploadImage, listImages, ImageListItem } from '../api/storage';

const { Dragger } = Upload;
const { Title, Text } = Typography;
const { TabPane } = Tabs;

export const UploadPage: React.FC = () => {
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [autoIndex, setAutoIndex] = useState(true);
  const [tags, setTags] = useState<string[]>([]);
  const [description, setDescription] = useState('');
  const [tagInput, setTagInput] = useState('');
  const [historyList, setHistoryList] = useState<ImageListItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // URL Upload State
  const [urlLoading, setUrlLoading] = useState(false);
  const [form] = Form.useForm();

  // Fetch history on mount
  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    setLoadingHistory(true);
    try {
      const res = await listImages(1, 10);
      if (res && res.data) {
        setHistoryList(res.data);
      }
    } catch (error) {
      console.error('Failed to fetch history:', error);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleUpload = async (options: any) => {
    const { file, onSuccess, onError, onProgress } = options;
    
    try {
      // Create a fake file object for AntD if needed, but we pass the raw file
      const response = await uploadImage(
        file,
        autoIndex,
        tags,
        description,
        (percent) => {
          onProgress({ percent });
        }
      );
      
      message.success(`${file.name} 上传成功`);
      onSuccess(response);
      fetchHistory(); // Refresh history
    } catch (err: any) {
      message.error(`${file.name} 上传失败: ${err.message}`);
      onError(err);
    }
  };

  const props: UploadProps = {
    name: 'file',
    multiple: true,
    fileList,
    listType: 'picture-card',
    customRequest: handleUpload,
    onChange(info) {
      const { status } = info.file;
      
      // Update file list state
      setFileList(info.fileList);

      if (status === 'done') {
        // handled in customRequest onSuccess
      } else if (status === 'error') {
        // handled in customRequest onError
      }
    },
    onDrop(e) {
      console.log('Dropped files', e.dataTransfer.files);
    },
  };

  const handleUrlUpload = async (values: { url: string; tags?: string; description?: string }) => {
    setUrlLoading(true);
    try {
        // Convert URL to File object (simplified for demo, ideally backend handles URL upload directly or we proxy)
        // Since the current API expects a File object, we need to fetch the blob.
        // NOTE: This might fail due to CORS if the image is on a different domain without CORS headers.
        // A better approach is to have a backend endpoint that accepts image_url.
        // For now, we will try to fetch it if possible, or warn the user.
        
        // However, the previous implementation did fetch(url).blob(), so we assume it works or uses a proxy.
        const response = await fetch(values.url);
        if (!response.ok) throw new Error('无法获取图片');
        const blob = await response.blob();
        const fileName = values.url.split('/').pop() || 'image.jpg';
        const file = new File([blob], fileName, { type: blob.type });

        const uploadTags = values.tags ? values.tags.split(',').map(t => t.trim()) : [];
        
        await uploadImage(file, autoIndex, uploadTags, values.description || '');
        message.success('URL 图片上传成功');
        form.resetFields();
        fetchHistory();
    } catch (error: any) {
      message.error(`URL 上传失败: ${error.message}`);
    } finally {
      setUrlLoading(false);
    }
  };

  const handleTagInputConfirm = () => {
    if (tagInput && tags.indexOf(tagInput) === -1) {
      setTags([...tags, tagInput]);
    }
    setTagInput('');
  };

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <Title level={2}>上传图片</Title>
      
      <Card style={{ marginBottom: 24 }}>
        <Tabs defaultActiveKey="local">
          <TabPane tab={<span><InboxOutlined />本地上传</span>} key="local">
             <div style={{ marginBottom: 16 }}>
                <Space direction="vertical" style={{ width: '100%' }}>
                    <div style={{ marginBottom: 8 }}>
                        <Text strong>全局设置 (应用于当前批次): </Text>
                        <Checkbox checked={autoIndex} onChange={e => setAutoIndex(e.target.checked)}>
                            自动索引到向量库
                        </Checkbox>
                    </div>
                    <Space wrap>
                        <Input 
                            placeholder="添加标签 (回车确认)" 
                            value={tagInput}
                            onChange={e => setTagInput(e.target.value)}
                            onPressEnter={handleTagInputConfirm}
                            style={{ width: 200 }}
                        />
                        {tags.map(tag => (
                            <Tag key={tag} closable onClose={() => setTags(tags.filter(t => t !== tag))}>
                                {tag}
                            </Tag>
                        ))}
                    </Space>
                    <Input.TextArea 
                        placeholder="添加描述..." 
                        value={description}
                        onChange={e => setDescription(e.target.value)}
                        rows={2}
                    />
                </Space>
             </div>

            <Dragger {...props} height={200}>
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
              <p className="ant-upload-hint">
                支持单次或批量上传。严禁上传敏感数据。
              </p>
            </Dragger>
          </TabPane>
          
          <TabPane tab={<span><LinkOutlined />URL 上传</span>} key="url">
            <Form form={form} layout="vertical" onFinish={handleUrlUpload}>
                <Form.Item name="url" label="图片链接" rules={[{ required: true, message: '请输入图片链接' }, { type: 'url', message: '请输入有效的 URL' }]}>
                    <Input prefix={<LinkOutlined />} placeholder="https://example.com/image.jpg" />
                </Form.Item>
                <Form.Item name="tags" label="标签 (逗号分隔)">
                    <Input placeholder="tag1, tag2" />
                </Form.Item>
                <Form.Item name="description" label="描述">
                    <Input.TextArea rows={2} />
                </Form.Item>
                <Form.Item>
                    <Button type="primary" htmlType="submit" loading={urlLoading} icon={<CloudUploadOutlined />}>
                        开始上传
                    </Button>
                </Form.Item>
            </Form>
          </TabPane>
        </Tabs>
      </Card>

      <Card title="最近上传" extra={<Button type="link" onClick={fetchHistory}>刷新</Button>}>
        <List
            grid={{ gutter: 16, xs: 1, sm: 2, md: 3, lg: 4, xl: 5, xxl: 5 }}
            dataSource={historyList}
            loading={loadingHistory}
            renderItem={item => (
                <List.Item>
                    <Card
                        cover={
                            <div style={{ height: 150, overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f0f2f5' }}>
                                <Image
                                    alt={item.filename}
                                    src={item.url}
                                    style={{ objectFit: 'cover', height: '100%', width: '100%' }}
                                    preview={{ src: item.url }}
                                />
                            </div>
                        }
                        actions={[
                            <Button type="text" icon={<DeleteOutlined />} danger size="small">删除</Button>
                        ]}
                    >
                        <Card.Meta
                            title={item.filename}
                            description={
                                <Space direction="vertical" size={0}>
                                    <Text type="secondary" style={{ fontSize: 12 }}>{new Date(item.created_at).toLocaleString()}</Text>
                                    <Text type="secondary" style={{ fontSize: 12 }}>{(item.file_size / 1024).toFixed(1)} KB</Text>
                                </Space>
                            }
                        />
                    </Card>
                </List.Item>
            )}
        />
      </Card>
    </div>
  );
};
