/**
 * ChatWindow.jsx
 * ────────────────
 * Componente principale: chat interface
 */

import { useState, useEffect, useRef } from "react";
import { chatWithPDF, checkBackendHealth } from "../services/api";
import { MessageBubble } from "./MessageBubble";

export function ChatWindow() {
    const [messages, setMessages] = useState([
        {
            id: 0,
            text: "👋 Ciao! Sono il tuo assistente AI per i PDF. Carica un documento e inizia a fare domande!",
            isUser: false,
            sources: [],
        },
    ]);

    const [inputValue, setInputValue] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [backendOnline, setBackendOnline] = useState(false);
    const messagesEndRef = useRef(null);

    // ────────────────────────────────────────
    // 1. CHECK BACKEND ALL'AVVIO
    // ────────────────────────────────────────

    useEffect(() => {
        const checkBackend = async () => {
            const isOnline = await checkBackendHealth();
            setBackendOnline(isOnline);

            if (!isOnline) {
                setMessages((prev) => [
                    ...prev,
                    {
                        id: Date.now(),
                        text: "❌ Backend non raggiungibile. Assicurati che il server FastAPI sia avviato su http://localhost:8000",
                        isUser: false,
                        sources: [],
                    },
                ]);
            }
        };

        checkBackend();
    }, []);

    // ────────────────────────────────────────
    // 2. AUTO-SCROLL A NUOVO MESSAGGIO
    // ────────────────────────────────────────

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    // ────────────────────────────────────────
    // 3. HANDLER INVIO MESSAGGIO
    // ────────────────────────────────────────

    const handleSendMessage = async () => {
        if (!inputValue.trim() || !backendOnline) return;

        // Aggiungi messaggio utente
        const userMessage = {
            id: Date.now(),
            text: inputValue,
            isUser: true,
            sources: [],
        };

        setMessages((prev) => [...prev, userMessage]);
        setInputValue("");
        setIsLoading(true);

        try {
            // Chiama backend
            const response = await chatWithPDF(inputValue);

            // Aggiungi risposta assistant
            const assistantMessage = {
                id: Date.now() + 1,
                text: response.answer,
                isUser: false,
                sources: response.sources || [],
            };

            setMessages((prev) => [...prev, assistantMessage]);
        } catch (error) {
            // Errore
            const errorMessage = {
                id: Date.now() + 1,
                text: `❌ Errore: ${error.message}`,
                isUser: false,
                sources: [],
            };

            setMessages((prev) => [...prev, errorMessage]);
        } finally {
            setIsLoading(false);
        }
    };

    // ────────────────────────────────────────
    // 4. HANDLER INVIO CON ENTER
    // ────────────────────────────────────────

    const handleKeyPress = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    };

    // ────────────────────────────────────────
    // 5. RENDER
    // ────────────────────────────────────────

    return (
        <div className="chat-window">
            {/* Header */}
            <div className="chat-header">
                <h1>📄 Chat with PDF</h1>
                <div className={`status-indicator ${backendOnline ? "online" : "offline"}`}>
                    {backendOnline ? "✓ Backend Online" : "✗ Backend Offline"}
                </div>
            </div>

            {/* Messaggi */}
            <div className="messages-container">
                {messages.map((msg) => (
                    <MessageBubble key={msg.id} message={msg} isUser={msg.isUser} />
                ))}
                {isLoading && (
                    <div className="message-bubble assistant loading">
                        <div className="typing-indicator">
                            <span></span>
                            <span></span>
                            <span></span>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="input-area">
                <textarea
                    className="message-input"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Scrivi una domanda... (Shift+Enter per newline)"
                    disabled={!backendOnline}
                />
                <button
                    className="send-button"
                    onClick={handleSendMessage}
                    disabled={!inputValue.trim() || !backendOnline || isLoading}
                >
                    {isLoading ? "⏳" : "📤"}
                </button>
            </div>
        </div>
    );
}
