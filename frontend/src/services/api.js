/**
 * api.js
 * ───────
 * Funzioni per comunicare con il backend FastAPI
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

/**
 * Invia query al backend e ottiene risposta
 * @param {string} query - Domanda dell'utente
 * @returns {Promise<{answer: string, sources: string[]}>}
 */
export const chatWithPDF = async (query) => {
    try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                query: query,
                context_count: 3,
            }),
        });

        if (!response.ok) {
            throw new Error(`Backend error: ${response.status}`);
        }

        const data = await response.json();
        return data; // {answer, sources}
    } catch (error) {
        console.error("Chat error:", error);
        throw error;
    }
};

/**
 * Health check per verificare se backend è online
 * @returns {Promise<boolean>}
 */
export const checkBackendHealth = async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        return response.ok;
    } catch {
        return false;
    }
};
