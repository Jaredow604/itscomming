import MessageList from './MessageList';
import ChatInput from './ChatInput';
import { useChat } from '../../hooks/useChat';
import { useTheme } from '../../hooks/useTheme';

/**
 * ChatLayout — Central chat area within the dashboard.
 *
 * Structure (no header — TopNavbar handles that):
 *   ┌────────────────────────────┐
 *   │                            │
 *   │     MessageList            │  <- flex-grow, scrollable
 *   │                            │
 *   ├────────────────────────────┤
 *   │  ChatInput                 │  <- fixed height
 *   └────────────────────────────┘
 */
export default function ChatLayout() {
  const { messages, isTyping, sendMessage, isLoading } = useChat();
  const { isDark } = useTheme();

  return (
    <div className="flex-1 flex flex-col h-full">
      {/* ====== MESSAGES ====== */}
      <MessageList messages={messages} isTyping={isTyping} isDark={isDark} />

      {/* ====== INPUT ====== */}
      <ChatInput onSend={sendMessage} isLoading={isLoading} />
    </div>
  );
}
