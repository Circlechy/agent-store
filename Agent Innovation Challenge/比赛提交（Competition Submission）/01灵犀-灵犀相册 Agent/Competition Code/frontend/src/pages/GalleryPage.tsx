import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Input,
  Radio,
  Empty,
  Spin,
  Pagination,
  Image,
  Card,
  Row,
  Col,
  Space,
  Typography,
  Tag,
  Button,
  message,
} from 'antd';
import {
  AppstoreOutlined,
  BarsOutlined,
  SearchOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { listImages } from '../api/storage';
import { searchByText } from '../api/search';
import type { ImageResult } from '../api/types';

const { Search } = Input;
const { Text } = Typography;

export const GalleryPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQuery = searchParams.get('q') || '';
  const initialTopK = parseInt(searchParams.get('top_k') || '10', 10);
  const [images, setImages] = useState<ImageResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(24);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [searchQuery, setSearchQuery] = useState(initialQuery);
  const [isSearching, setIsSearching] = useState(!!initialQuery);
  const [topK, setTopK] = useState(initialTopK);

  const fetchImages = useCallback(async (pageNum: number, size: number) => {
    console.log('Fetching images...', { pageNum, size });
    setLoading(true);
    try {
      const result = await listImages(pageNum, size, 'created_at', 'desc');
      console.log('Fetch result:', result);
      
      // Ensure result and result.data are valid
      const rawData = result && result.data ? result.data : [];
      
      const mappedImages: ImageResult[] = rawData.map(img => ({
        id: img.id,
        score: 1,
        metadata: {
          filename: img.filename,
          file_path: img.file_path,
          file_size: img.file_size,
          width: img.width,
          height: img.height,
          format: img.format,
          created_at: img.created_at,
          tags: [], 
        },
        preview_url: img.url,
      }));
      setImages(mappedImages);
      setTotal(result.total || 0);
    } catch (err: any) {
      console.error('Failed to fetch images:', err);
      // message.error(err.message || '加载图片失败'); // Don't show error toast on initial load failure if it's transient
      setImages([]); 
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSearch = useCallback(async (value: string, eventOrTopK?: any) => {
    if (!value.trim()) {
      setSearchQuery('');
      setIsSearching(false);
      setPage(1);
      // We don't fetch here because setting isSearching(false) will trigger Effect 2
      return;
    }

    setLoading(true);
    setIsSearching(true);
    setSearchQuery(value);
    
    // Determine Top K: use passed number if available, otherwise use state
    // Ant Design Search component passes an event object as the second argument
    const k = typeof eventOrTopK === 'number' ? eventOrTopK : topK;

    try {
      const result = await searchByText(value.trim(), k);
      setImages(result.data);
      setTotal(result.total);
      setPage(1);
    } catch (err: any) {
      message.error(err.message || '搜索失败');
    } finally {
      setLoading(false);
    }
  }, [topK]); 

  // Effect 1: Sync URL params with component state
  useEffect(() => {
    const queryParam = searchParams.get('q');
    const topKParam = searchParams.get('top_k');
    
    // Case 1: URL has a query
    if (queryParam) {
      const newTopK = topKParam ? parseInt(topKParam, 10) : 10;
      
      // Update topK state if URL has it
      if (newTopK !== topK) {
          setTopK(newTopK);
      }

      // If the current state matches the URL, we might have just mounted with initial state.
      // But we still need to fetch data because initial state setting doesn't trigger fetch.
      // Or if the URL changed (e.g. back button), we need to update state and fetch.
      
      if (queryParam !== searchQuery || newTopK !== topK) {
         // URL changed, update state and search
         setSearchQuery(queryParam);
         setTopK(newTopK);
         handleSearch(queryParam, newTopK);
      } else if (images.length === 0 && loading) {
         // Initial mount case or refresh: state matches URL, but no data yet.
         // Trigger search directly.
         handleSearch(queryParam, newTopK);
      }
    } else {
      // Case 2: URL has NO query
      // If we were searching, we need to reset.
      if (isSearching) {
        setIsSearching(false);
        setSearchQuery('');
        setPage(1);
        // Effect 2 will handle fetching default images when isSearching becomes false
      }
    }
  }, [searchParams]); // Depend ONLY on searchParams to avoid loops

  // Effect 2: Handle data fetching for non-search mode (View All)
  useEffect(() => {
    // Only fetch default images if we are NOT searching
    if (!isSearching) {
      fetchImages(page, pageSize);
    }
  }, [page, pageSize, isSearching]); // Removed fetchImages from deps to be safe, though useCallback handles it

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        
        {/* Header / Filter Bar */}
        <Card>
          <Row justify="space-between" align="middle" gutter={[16, 16]}>
            <Col xs={24} md={12}>
              <Search
                placeholder="搜索图片描述..."
                allowClear
                enterButton={<Button type="primary" icon={<SearchOutlined />}>搜索</Button>}
                size="large"
                onSearch={handleSearch}
                style={{ maxWidth: 500 }}
              />
            </Col>
            <Col xs={24} md={12} style={{ textAlign: 'right' }}>
              <Space>
                <Button 
                    icon={<ReloadOutlined />} 
                    onClick={() => {
                        setPage(1);
                        fetchImages(1, pageSize);
                    }}
                >
                    刷新
                </Button>
                <Radio.Group 
                    value={viewMode} 
                    onChange={e => setViewMode(e.target.value)}
                    buttonStyle="solid"
                >
                  <Radio.Button value="grid"><AppstoreOutlined /></Radio.Button>
                  <Radio.Button value="list"><BarsOutlined /></Radio.Button>
                </Radio.Group>
              </Space>
            </Col>
          </Row>
          
          {isSearching && (
             <div style={{ marginTop: 16 }}>
                <Text type="secondary">
                    找到 {total} 个结果 (关键词: "{searchQuery}")
                </Text>
                <Button type="link" onClick={() => {
                    setSearchQuery('');
                    handleSearch('');
                }}>清除搜索</Button>
             </div>
          )}
        </Card>

        {/* Content */}
        {loading ? (
          <div style={{ textAlign: 'center', padding: '50px 0' }}>
            <Spin size="large" tip="加载中..." />
          </div>
        ) : images.length === 0 ? (
          <Empty description="暂无图片，去上传一些吧" />
        ) : (
          <>
            <Image.PreviewGroup>
              {viewMode === 'grid' ? (
                <Row gutter={[16, 16]}>
                  {images.map(img => (
                    <Col xs={24} sm={12} md={8} lg={6} xl={4} key={img.id}>
                      <Card
                        hoverable
                        styles={{ body: { padding: 0 } }}
                        cover={
                          <div style={{ 
                            height: 200, 
                            overflow: 'hidden', 
                            display: 'flex', 
                            alignItems: 'center', 
                            justifyContent: 'center',
                            background: '#f5f5f5'
                          }}>
                            <Image
                              src={img.preview_url}
                              alt={img.metadata.filename}
                              style={{ objectFit: 'cover', width: '100%', height: '100%' }}
                              fallback="data:image/svg+xml;base64,..."
                            />
                          </div>
                        }
                      >
                        <div style={{ padding: 12 }}>
                           <Text ellipsis={{ tooltip: img.metadata.filename }} style={{ display: 'block', fontWeight: 500 }}>
                                {img.metadata.filename}
                           </Text>
                           <Space style={{ marginTop: 4, fontSize: 12 }} size={4}>
                                <Text type="secondary">
                                    {new Date(img.metadata.created_at).toLocaleDateString()}
                                </Text>
                                {img.metadata.format && <Tag>{img.metadata.format}</Tag>}
                           </Space>
                        </div>
                      </Card>
                    </Col>
                  ))}
                </Row>
              ) : (
                 <Space direction="vertical" style={{ width: '100%' }}>
                    {images.map(img => (
                        <Card key={img.id} styles={{ body: { padding: 12 } }}>
                            <Row gutter={16} align="middle">
                                <Col flex="100px">
                                    <Image
                                        src={img.preview_url}
                                        width={100}
                                        height={100}
                                        style={{ objectFit: 'cover', borderRadius: 4 }}
                                    />
                                </Col>
                                <Col flex="auto">
                                    <Text strong style={{ fontSize: 16 }}>{img.metadata.filename}</Text>
                                    <div style={{ marginTop: 8 }}>
                                        <Space size="large">
                                            <Text type="secondary">尺寸: {img.metadata.width} x {img.metadata.height}</Text>
                                            <Text type="secondary">大小: {((img.metadata.file_size || 0) / 1024).toFixed(1)} KB</Text>
                                            <Text type="secondary">上传时间: {new Date(img.metadata.created_at).toLocaleString()}</Text>
                                        </Space>
                                    </div>
                                    <div style={{ marginTop: 8 }}>
                                        {img.metadata.tags?.map(tag => <Tag key={tag}>{tag}</Tag>)}
                                    </div>
                                </Col>
                            </Row>
                        </Card>
                    ))}
                 </Space>
              )}
            </Image.PreviewGroup>

            {/* Pagination */}
            {!isSearching && (
                <div style={{ textAlign: 'center', marginTop: 32 }}>
                <Pagination
                    current={page}
                    total={total}
                    pageSize={pageSize}
                    onChange={(p, s) => {
                        setPage(p);
                        setPageSize(s);
                    }}
                    showSizeChanger
                    showQuickJumper
                    showTotal={(total) => `共 ${total} 条`}
                />
                </div>
            )}
          </>
        )}
      </Space>
    </div>
  );
};
