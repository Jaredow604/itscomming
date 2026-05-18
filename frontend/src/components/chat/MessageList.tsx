import { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Bot, User } from 'lucide-react';
import DataWidgetBubble from '../widgets/DataWidgetBubble';
import type { ChatMessage } from '../../types';

interface MessageListProps {
  messages: ChatMessage[];
  isTyping: boolean;
  isDark: boolean;
}

/**
 * MessageList — Scrollable message feed with auto-scroll on new messages.
 *
 * Renders user bubbles (right-aligned, blue) and bot bubbles (left-aligned).
 * Bot messages can contain an optional DataWidgetBubble with charts.
 * Shows a typing indicator with animated dots when the API is processing.
 */
export default function MessageList({ messages, isTyping, isDark }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages or typing state change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      <div className="max-w-3xl mx-auto space-y-4">
        {messages.map((msg) => (
          <motion.div
            key={msg.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
            className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {/* Bot avatar */}
            {msg.role === 'bot' && (
              <div className="flex-shrink-0 mt-1">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-cyan-500
                                flex items-center justify-center shadow-md shadow-brand-500/20">
                  <Bot className="w-4 h-4 text-white" />
                </div>
              </div>
            )}

            {/* Message content */}
            <div className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
              <div className={msg.role === 'user' ? 'bubble-user' : 'bubble-bot'}>
                <p className="text-sm leading-relaxed whitespace-pre-wrap">
                  {msg.content}
                </p>
              </div>

              {/* Widget (only for bot messages with data) */}
              {msg.role === 'bot' && msg.widget && (
                <DataWidgetBubble widget={msg.widget} isDark={isDark} />
              )}

              {/* Timestamp */}
              <p className="text-[10px] text-slate-400 dark:text-slate-600 mt-1 px-1">
                {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </p>
            </div>

            {/* User avatar */}
            {msg.role === 'user' && (
              <div className="flex-shrink-0 mt-1">
                <div className="w-8 h-8 rounded-lg bg-slate-200 dark:bg-white/10
                                flex items-center justify-center">
                  <User className="w-4 h-4 text-slate-500 dark:text-slate-400" />
                </div>
              </div>
            )}
          </motion.div>
        ))}

        {/* Typing indicator */}
        {isTyping && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex gap-3 justify-start"
          >
            <div className="flex-shrink-0 mt-1">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-cyan-500
                              flex items-center justify-center shadow-md shadow-brand-500/20">
                <Bot className="w-4 h-4 text-white" />
              </div>
            </div>
            <div className="bubble-bot">
              <div className="flex items-center gap-1.5 py-1 px-1">
                <div className="typing-dot" style={{ animationDelay: '0s' }} />
                <div className="typing-dot" style={{ animationDelay: '0.16s' }} />
                <div className="typing-dot" style={{ animationDelay: '0.32s' }} />
              </div>
            </div>
          </motion.div>
        )}

        {/* Scroll anchor */}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
