import { useState, useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';
import apiClient from '../api/client';
import type { ChatMessage, ChatRequest, ChatResponse } from '../types';

/**
 * useChat — Custom hook for managing chat state and API communication.
 *
 * Uses TanStack Query's useMutation to handle the POST request to
 * the Django backend. Manages the full message array lifecycle:
 *   1. User sends message -> appended immediately (optimistic)
 *   2. Bot typing indicator shown
 *   3. API response received -> bot message appended with optional widget
 *   4. Error handling with user-friendly fallback message
 */
export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'bot',
      content:
        'Bienvenido a **It\'s Coming**. Soy tu analista quant deportivo. ' +
        'Pregunta sobre cualquier partido de NBA, MLB o futbol y te dare ' +
        'mi proyeccion basada en redes neuronales, Elo y metricas avanzadas.',
      timestamp: new Date(),
    },
  ]);

  const [isTyping, setIsTyping] = useState(false);

  // --- Mutation: POST /api/v1/chat/ ---
  const mutation = useMutation({
    mutationFn: async (request: ChatRequest): Promise<ChatResponse> => {
      const { data } = await apiClient.post<ChatResponse>(
        '/api/v1/chat/',
        request,
      );
      return data;
    },

    onMutate: () => {
      setIsTyping(true);
    },

    onSuccess: (data) => {
      const botMessage: ChatMessage = {
        id: `bot-${Date.now()}`,
        role: 'bot',
        content: data.reply,
        widget: data.widget,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, botMessage]);
      setIsTyping(false);
    },

    onError: (error) => {
      console.error('Chat API error:', error);
      const errorMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        role: 'bot',
        content:
          'Error de conexion con el servidor. Verifica que el backend ' +
          'de Django este corriendo en `localhost:8001`.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
      setIsTyping(false);
    },
  });

  // --- Send message handler ---
  const sendMessage = useCallback(
    (content: string) => {
      const trimmed = content.trim();
      if (!trimmed || mutation.isPending) return;

      // 1. Append user message immediately (optimistic)
      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: trimmed,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMessage]);

      // 2. Fire API request
      mutation.mutate({ message: trimmed });
    },
    [mutation],
  );

  return {
    messages,
    isTyping,
    sendMessage,
    isLoading: mutation.isPending,
  };
}
