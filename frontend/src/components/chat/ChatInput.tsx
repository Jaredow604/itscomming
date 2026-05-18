import { useState, type KeyboardEvent } from 'react';
import { Send, Loader2 } from 'lucide-react';

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
}

/**
 * ChatInput — Bottom-anchored input bar with send button.
 *
 * Supports Enter key submission and disabled state during loading.
 * The send button shows a spinner when the API is processing.
 */
export default function ChatInput({ onSend, isLoading }: ChatInputProps) {
  const [input, setInput] = useState('');

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;
    onSend(trimmed);
    setInput('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-slate-200/60 dark:border-white/10
                    bg-white/80 dark:bg-surface-900/80 backdrop-blur-xl">
      <div className="max-w-3xl mx-auto px-4 py-3">
        <div className="flex items-end gap-3">
          <div className="flex-1 relative">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Pregunta sobre cualquier partido..."
              disabled={isLoading}
              rows={1}
              className="w-full resize-none rounded-xl
                         px-4 py-3 pr-12
                         bg-slate-100 dark:bg-white/5
                         border border-slate-200/60 dark:border-white/10
                         text-slate-800 dark:text-white
                         placeholder:text-slate-400 dark:placeholder:text-slate-500
                         focus:outline-none focus:ring-2 focus:ring-brand-500/40
                         focus:border-brand-500/40
                         transition-all duration-200
                         text-sm leading-relaxed
                         disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ minHeight: '46px', maxHeight: '120px' }}
            />
          </div>

          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="flex-shrink-0 p-3 rounded-xl
                       bg-brand-500 hover:bg-brand-600
                       disabled:bg-slate-300 dark:disabled:bg-slate-700
                       disabled:cursor-not-allowed
                       text-white shadow-md shadow-brand-500/25
                       hover:shadow-lg hover:shadow-brand-500/30
                       transition-all duration-200
                       focus:outline-none focus:ring-2 focus:ring-brand-500/40"
            aria-label="Enviar mensaje"
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>

        <p className="text-[10px] text-slate-400 dark:text-slate-600 text-center mt-2">
          Powered by PyTorch &bull; Elo &bull; Pythagorean Expectation
        </p>
      </div>
    </div>
  );
}
