/**
 * MessageBubble.jsx
 * ───────────────────
 * Componente che renderizza un messaggio singolo (utente o assistant)
 */

export function MessageBubble({ message, isUser }) {
    return (
        <div className={`message-bubble ${isUser ? "user" : "assistant"}`}>
            {/* Testo principale */}
            <div className="message-text">
                {message.text}
            </div>

            {/* Sources (solo per risposte) */}
            {!isUser && message.sources && message.sources.length > 0 && (
                <div className="message-sources">
                    <small>
                        📚 Fonti: {message.sources.join(", ")}
                    </small>
                </div>
            )}
        </div>
    );
}
