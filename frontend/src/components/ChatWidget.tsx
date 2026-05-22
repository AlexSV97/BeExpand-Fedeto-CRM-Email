/**
 * ChatWidget — widget flotante de onboarding contextual.
 *
 * Burbuja en la esquina inferior derecha que abre un panel de chat.
 * Usa el mismo modelo Hermes 3 del backend con contexto del sistema.
 * Mantiene la conversación por sesión (conversation_id en localStorage).
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { sendChatMessage, type ChatResponse } from '../services/api'

// ── Iconos inline ──

function ChatBubbleIcon() {
  return (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

function SendIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  )
}

// ── Tipos ──

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const WELCOME_MESSAGE: Message = {
  role: 'assistant',
  content: '¡Hola! Soy el asistente de BeConnect. Puedo ayudarte a entender el dashboard, las clasificaciones de correos, o consultar las estadísticas actuales del sistema. ¿En qué puedo ayudarte?',
}

const LS_CONVERSATION_KEY = 'beconnect_chat_conv'

// ── Componente principal ──

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Recuperar conversation_id de localStorage
  const [conversationId, setConversationId] = useState<string | null>(() => {
    return localStorage.getItem(LS_CONVERSATION_KEY)
  })

  // Auto-scroll al último mensaje
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  // Focus en el input al abrir
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 300)
    }
  }, [isOpen])

  const handleSend = useCallback(async () => {
    const text = input.trim()
    if (!text || loading) return

    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setLoading(true)

    try {
      const res: ChatResponse = await sendChatMessage({
        message: text,
        conversation_id: conversationId,
      })

      // Guardar conversation_id para la próxima vez
      if (res.conversation_id) {
        setConversationId(res.conversation_id)
        localStorage.setItem(LS_CONVERSATION_KEY, res.conversation_id)
      }

      setMessages((prev) => [...prev, { role: 'assistant', content: res.response }])
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Lo siento, no pude conectar con el servicio. Inténtalo de nuevo.',
        },
      ])
    } finally {
      setLoading(false)
    }
  }, [input, loading, conversationId])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend],
  )

  const handleReset = useCallback(() => {
    setMessages([WELCOME_MESSAGE])
    setConversationId(null)
    localStorage.removeItem(LS_CONVERSATION_KEY)
  }, [])

  return (
    <>
      {/* Botón flotante */}
      <div className="fixed bottom-6 right-6 z-50">
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => setIsOpen(!isOpen)}
          className="w-12 h-12 rounded-full bg-foreground text-background shadow-lg shadow-foreground/20 flex items-center justify-center cursor-pointer hover:opacity-90 transition-opacity"
          aria-label={isOpen ? 'Cerrar chat' : 'Abrir chat'}
        >
          {isOpen ? <CloseIcon /> : <ChatBubbleIcon />}
        </motion.button>
      </div>

      {/* Panel de chat */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
            className="fixed bottom-20 right-6 z-50 w-[360px] h-[520px] rounded-2xl shadow-2xl flex flex-col overflow-hidden"
            style={{
              backgroundColor: 'var(--card)',
              border: '1px solid var(--border)',
            }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-4 py-3 border-b shrink-0"
              style={{ borderColor: 'var(--border)' }}
            >
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-full bg-gradient-to-br from-chart-1 to-chart-2 flex items-center justify-center">
                  <span className="text-white font-bold text-xs">Bc</span>
                </div>
                <div>
                  <span className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
                    Asistente
                  </span>
                  <div className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-success" />
                    <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                      Online
                    </span>
                  </div>
                </div>
              </div>
              <button
                onClick={handleReset}
                className="text-xs px-2 py-1 rounded-md transition-colors cursor-pointer"
                style={{
                  color: 'var(--muted-foreground)',
                  backgroundColor: 'var(--muted)',
                }}
                title="Nueva conversación"
              >
                Nueva
              </button>
            </div>

            {/* Messages */}
            <div
              className="flex-1 overflow-y-auto px-4 py-3 space-y-3"
              style={{ backgroundColor: 'var(--background)' }}
            >
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-foreground text-background rounded-br-md'
                        : 'rounded-bl-md'
                    }`}
                    style={
                      msg.role === 'assistant'
                        ? {
                            backgroundColor: 'var(--muted)',
                            color: 'var(--foreground)',
                          }
                        : undefined
                    }
                  >
                    {msg.content}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex justify-start">
                  <div
                    className="rounded-2xl rounded-bl-md px-3.5 py-2.5 text-sm"
                    style={{
                      backgroundColor: 'var(--muted)',
                      color: 'var(--muted-foreground)',
                    }}
                  >
                    <span className="inline-flex gap-1">
                      <span className="animate-bounce" style={{ animationDelay: '0ms' }}>·</span>
                      <span className="animate-bounce" style={{ animationDelay: '150ms' }}>·</span>
                      <span className="animate-bounce" style={{ animationDelay: '300ms' }}>·</span>
                    </span>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div
              className="px-4 py-3 border-t shrink-0"
              style={{ borderColor: 'var(--border)', backgroundColor: 'var(--card)' }}
            >
              <div className="flex items-center gap-2">
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Escribe tu mensaje..."
                  disabled={loading}
                  className="flex-1 text-sm px-3 py-2 rounded-xl outline-none transition-colors"
                  style={{
                    backgroundColor: 'var(--muted)',
                    color: 'var(--foreground)',
                  }}
                />
                <motion.button
                  whileTap={{ scale: 0.9 }}
                  onClick={handleSend}
                  disabled={loading || !input.trim()}
                  className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 cursor-pointer transition-opacity disabled:opacity-40"
                  style={{
                    backgroundColor: 'var(--foreground)',
                    color: 'var(--background)',
                  }}
                >
                  <SendIcon />
                </motion.button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
