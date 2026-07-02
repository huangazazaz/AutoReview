import { useState, useCallback, useEffect, useRef } from 'react'
import { useApp } from '@/hooks/useApp'
import { useCachedStrategies } from '@/hooks/useCachedStrategies'
import { api } from '@/api/client'
import { PageHeader } from '@/components/UI'
import ChatMessages from '@/components/ChatMessages'
import ChatSessionList from '@/components/ChatSessionList'
import ChatInput from '@/components/ChatInput'
import { MAX_DATE } from '@/utils/date'
import type { ChatMessage, ChatSession, StrategyResult } from '@/types'

export default function AIStrategy() {
  const { showToast, showLoading: showGlobalLoading, hideLoading } = useApp()
  const { refresh: refreshStrategies } = useCachedStrategies()

  const [symbol, setSymbol] = useState('600522')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string>()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [sending, setSending] = useState(false)
  const [nextId, setNextId] = useState(1)
  const [exampleFillText, setExampleFillText] = useState('')

  // Load active session on mount
  const initialLoadDone = useRef(false)
  useEffect(() => {
    if (initialLoadDone.current) return
    initialLoadDone.current = true
    const savedId = localStorage.getItem('ai_chat_active_session')
    if (savedId) {
      loadSession(savedId)
    }
  }, [])

  // 默认日期：最近1年（数据截止 MAX_DATE）
  useEffect(() => {
    const d = new Date(MAX_DATE)
    d.setFullYear(d.getFullYear() - 1)
    setStartDate(d.toISOString().slice(0, 10))
    setEndDate(MAX_DATE)
  }, [])

  const loadSession = useCallback(async (sessionId: string) => {
    try {
      const data = await api.getChatHistory(sessionId)
      setActiveSessionId(sessionId)
      setMessages(data.messages.map((m, i) => ({
        ...m,
        id: i + 1,
        codeExpanded: false,
      })))
      setNextId(data.messages.length + 1)
      // Add to sessions list if not present
      setSessions(prev => {
        if (prev.find(s => s.session_id === sessionId)) return prev
        return [data.session, ...prev]
      })
      localStorage.setItem('ai_chat_active_session', sessionId)
    } catch {
      localStorage.removeItem('ai_chat_active_session')
      setActiveSessionId(undefined)
      setMessages([])
    }
  }, [])

  const handleSend = useCallback(async (text: string) => {
    if (sending) return

    const userMsg: ChatMessage = {
      id: nextId,
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMsg])
    setNextId(n => n + 1)

    setSending(true)
    showGlobalLoading('AI 正在思考...')
    try {
      const result = await api.chat({
        session_id: activeSessionId,
        prompt: text,
        symbol,
        start: startDate || undefined,
        end: endDate || undefined,
      })

      const newSessionId = result.session_id
      if (!activeSessionId) {
        setActiveSessionId(newSessionId)
        localStorage.setItem('ai_chat_active_session', newSessionId)
        // Add to sessions list
        setSessions(prev => {
          if (prev.find(s => s.session_id === newSessionId)) return prev
          return [{
            session_id: newSessionId,
            title: text.length > 50 ? text.slice(0, 50) : text,
            created_at: new Date().toISOString(),
            last_active: new Date().toISOString(),
            message_count: 2,
          }, ...prev]
        })
      }

      const aiMsg: ChatMessage = {
        id: nextId + 1,
        role: 'assistant',
        content: result.message.content,
        timestamp: result.message.timestamp,
        strategy: result.strategy,
        backtest: result.backtest,
        codeExpanded: false,
      }
      setMessages(prev => [...prev, aiMsg])
      setNextId(n => n + 2)

      // Update session in list
      setSessions(prev => prev.map(s =>
        s.session_id === newSessionId
          ? { ...s, last_active: new Date().toISOString(), message_count: s.message_count + 2 }
          : s
      ))
    } catch (err) {
      showToast('发送失败: ' + (err as Error).message, 'error')
    } finally {
      setSending(false)
      hideLoading()
    }
  }, [sending, activeSessionId, symbol, startDate, endDate, nextId])

  const handleNewSession = useCallback(() => {
    setActiveSessionId(undefined)
    setMessages([])
    setNextId(1)
    localStorage.removeItem('ai_chat_active_session')
  }, [])

  const handlePromptFill = useCallback((text: string) => {
    handleNewSession()
    setExampleFillText(text)
  }, [handleNewSession])

  const handleSelectSession = useCallback((sessionId: string) => {
    if (sessionId === activeSessionId) return
    loadSession(sessionId)
  }, [activeSessionId, loadSession])

  const handleDeleteSession = useCallback(async (sessionId: string) => {
    try {
      await api.deleteChat(sessionId)
      setSessions(prev => prev.filter(s => s.session_id !== sessionId))
      if (sessionId === activeSessionId) {
        handleNewSession()
      }
      showToast('会话已删除', 'info')
    } catch {
      showToast('删除失败', 'error')
    }
  }, [activeSessionId, handleNewSession])

  const handleSave = useCallback(async (strategy: StrategyResult) => {
    showGlobalLoading('正在保存策略...')
    try {
      const res = await api.saveStrategy({
        name: strategy.name,
        python_code: strategy.python_code,
        yaml_code: strategy.yaml_code,
      })
      if (res.error) showToast(res.error, 'error')
      else {
        showToast(`策略 ${res.name} 已保存`, 'info')
        refreshStrategies()
      }
    } catch (err) {
      showToast('保存失败: ' + (err as Error).message, 'error')
    } finally { hideLoading() }
  }, [refreshStrategies])

  const handleDelete = useCallback(async (name: string) => {
    showGlobalLoading('正在删除策略...')
    try {
      const res = await api.deleteStrategy(name)
      if (res.error) showToast(res.error, 'error')
      else {
        showToast(`策略 ${res.name} 已删除`, 'info')
        refreshStrategies()
      }
    } catch (err) {
      showToast('删除失败: ' + (err as Error).message, 'error')
    } finally { hideLoading() }
  }, [refreshStrategies])

  const handleCodeExpand = useCallback((messageId: number) => {
    setMessages(prev => prev.map(m =>
      m.id === messageId ? { ...m, codeExpanded: !m.codeExpanded } : m
    ))
  }, [])

  const handleCopy = useCallback(async (code: string) => {
    try {
      await navigator.clipboard.writeText(code)
      showToast('已复制代码', 'info')
    } catch {
      // clipboard write failed; silently ignore
    }
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)' }}>
      <div className="page-hero" style={{ marginBottom: 0 }}>
        <PageHeader
          title="AI 策略工坊"
          subtitle="用自然语言描述交易想法，AI 自动生成策略、回测验证，支持多轮对话修改优化"
        />
      </div>

      <div style={{ display: 'flex', gap: 16, flex: 1, minHeight: 0, marginTop: 16 }}>
        {/* 左侧：会话列表 */}
        <ChatSessionList
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelect={handleSelectSession}
          onNew={handleNewSession}
          onDelete={handleDeleteSession}
        />

        {/* 右侧：对话区 */}
        <div className="card card-accent" style={{
          flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0,
          borderTop: '2px solid rgba(59,130,246,0.3)',
        }}>
          <div className="card-body" style={{
            flex: 1, overflow: 'auto', padding: '16px 20px',
          }}>
            <ChatMessages
              messages={messages}
              sending={sending}
              onCodeExpand={handleCodeExpand}
              onSave={handleSave}
              onDelete={handleDelete}
              onCopy={handleCopy}
            />
          </div>
        </div>
      </div>

      {/* 底部输入区 */}
      <div style={{ marginTop: 12 }}>
        <ChatInput
          symbol={symbol}
          startDate={startDate}
          endDate={endDate}
          onSymbolChange={setSymbol}
          onStartDateChange={setStartDate}
          onEndDateChange={setEndDate}
          onSend={handleSend}
          disabled={sending}
          fillText={exampleFillText}
          onFillConsumed={() => setExampleFillText('')}
        />
      </div>
    </div>
  )
}
