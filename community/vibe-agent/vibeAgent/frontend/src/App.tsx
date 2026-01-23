import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Layout } from 'antd'
import WorkflowBuilderIncremental from './pages/WorkflowBuilderIncremental.tsx'
import './App.css'

const { Header } = Layout

function App() {
  return (
    <Router>
      <Layout style={{ minHeight: '100vh' }}>
        <Header style={{ 
          background: '#001529', 
          color: '#fff',
          display: 'flex',
          alignItems: 'center',
          padding: '0 24px',
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          zIndex: 1000,
        }}>
          <h1 style={{ color: '#fff', margin: 0, fontSize: '20px', fontWeight: 600 }}>Vibe Agent</h1>
        </Header>
        <Layout style={{ marginTop: '64px', height: 'calc(100vh - 64px)' }}>
          <Routes>
            <Route path="/" element={<WorkflowBuilderIncremental />} />
          </Routes>
        </Layout>
      </Layout>
    </Router>
  )
}

export default App

