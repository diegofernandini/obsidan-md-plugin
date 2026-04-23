import { ItemView, WorkspaceLeaf, TFile } from 'obsidian';
import * as React from 'react';
import * as ReactDOM from 'react-dom/client';

export const VIEW_TYPE_CHAT = "mi-ai-chat-view";

interface Message {
    role: 'user' | 'assistant';
    content: string;
    agent?: string;
}

export class ChatView extends ItemView {
    settings: any;
    root: ReactDOM.Root | null = null;

    constructor(leaf: WorkspaceLeaf, settings: any) {
        super(leaf);
        this.settings = settings;
    }

    getViewType() {
        return VIEW_TYPE_CHAT;
    }

    getDisplayText() {
        return "MI-AI Chat";
    }

    async onOpen() {
        this.root = ReactDOM.createRoot(this.contentEl);
        this.root.render(
            <ChatComponent app={this.app} settings={this.settings} />
        );
    }

    async onClose() {
        this.root?.unmount();
    }
}

const ChatComponent = ({ app, settings }: { app: any, settings: any }) => {
    const [messages, setMessages] = React.useState<Message[]>([]);
    const [input, setInput] = React.useState('');
    const [isLoading, setIsLoading] = React.useState(false);
    const [currentAgent, setCurrentAgent] = React.useState('Detective / Agente Extractor');
    const [currentMode, setCurrentMode] = React.useState('local');
    const scrollRef = React.useRef<HTMLDivElement>(null);

    React.useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    const handleSend = async () => {
        if (!input.trim() || isLoading) return;

        const originalInput = input.trim();
        const userMsg: Message = { role: 'user', content: originalInput };
        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setIsLoading(true);

        const assistantMsg: Message = { role: 'assistant', content: '', agent: currentAgent };
        setMessages(prev => [...prev, assistantMsg]);

        try {
            const activeFile = app.workspace.getActiveFile();
            let noteContent = "";
            if (activeFile instanceof TFile) {
                noteContent = await app.vault.read(activeFile);
            }

            let endpoint = `http://localhost:${settings.serverPort}/chat`;
            let body: any = {
                message: originalInput,
                vault_path: app.vault.adapter.getBasePath(),
                active_note_content: noteContent,
                agent_role: currentAgent,
                mode: currentMode
            };

            // Handle Slash Commands (override mode if necessary)
            if (originalInput.startsWith('/roadmap ')) {
                endpoint = `http://localhost:${settings.serverPort}/blueprint/roadmap`;
                body.message = originalInput.replace('/roadmap ', '');
            } else if (originalInput.startsWith('/synergy ')) {
                endpoint = `http://localhost:${settings.serverPort}/blueprint/synergy`;
                const topics = originalInput.replace('/synergy ', '').split(',').map(s => s.trim());
                body = { topics, vault_path: app.vault.adapter.getBasePath() };
            }

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (!response.body) return;

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullContent = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        
                        if (data.startsWith('LOG: ')) {
                            // Show logs as temporary status
                            setMessages(prev => {
                                const newMsgs = [...prev];
                                newMsgs[newMsgs.length - 1].content = `⏳ ${data.slice(5)}`;
                                return newMsgs;
                            });
                        } else if (data.startsWith('RESULT: ')) {
                            fullContent = data.slice(8);
                            setMessages(prev => {
                                const newMsgs = [...prev];
                                newMsgs[newMsgs.length - 1].content = fullContent;
                                return newMsgs;
                            });
                        } else if (data.startsWith('TRANSCRIPT: ')) {
                            // Optionally handle transcript
                        } else {
                            // Normal chat or streaming result
                            fullContent += data;
                            setMessages(prev => {
                                const newMsgs = [...prev];
                                newMsgs[newMsgs.length - 1].content = fullContent;
                                return newMsgs;
                            });
                        }
                    }
                }
            }
        } catch (err) {
            console.error(err);
            setMessages(prev => [
                ...prev, 
                { role: 'assistant', content: '⚠️ Error de conexión con el servidor MI-AI.' }
            ]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleSaveToNote = async (content: string) => {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const fileName = `MI-AI_Report_${timestamp}.md`;
        await app.vault.create(fileName, content);
        app.workspace.openLinkText(fileName, '', true);
    };

    const handleSyncSharePoint = async () => {
        setIsLoading(true);
        try {
            const response = await fetch(`http://localhost:${settings.serverPort}/sync-sharepoint`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    site_url: settings.sharepointSite,
                    client_id: settings.sharepointClientId,
                    client_secret: settings.sharepointClientSecret,
                    folder_url: settings.sharepointFolder
                })
            });
            const data = await response.json();
            if (data.status === 'success') {
                setMessages(prev => [...prev, { role: 'assistant', content: `✅ Sincronización exitosa: ${data.files_synced} archivos indexados desde SharePoint.` }]);
            } else {
                setMessages(prev => [...prev, { role: 'assistant', content: `⚠️ Advertencia: ${data.detail || data.message}` }]);
            }
        } catch (err) {
            setMessages(prev => [...prev, { role: 'assistant', content: '❌ Error al conectar con SharePoint. Verifica tus credenciales en Ajustes.' }]);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '10px' }}>
            <div style={{ marginBottom: '10px', display: 'flex', flexDirection: 'column', gap: '5px' }}>
                <select 
                    value={currentMode} 
                    onChange={(e) => setCurrentMode(e.target.value)}
                    style={{ width: '100%', padding: '5px', fontWeight: 'bold' }}
                >
                    <option value="local">🔍 Modo Local (Vault)</option>
                    <option value="web">🌍 Modo Web (Scraper)</option>
                    <option value="hybrid">🧬 Modo Híbrido (Pro)</option>
                    <option value="blueprint">🔮 Blueprints (Slash Commands)</option>
                </select>

                <div style={{ display: 'flex', gap: '5px' }}>
                    <select 
                        value={currentAgent} 
                        onChange={(e) => setCurrentAgent(e.target.value)}
                        style={{ flex: 1, padding: '5px' }}
                    >
                        <option value="Detective / Agente Extractor">🔍 Detective (Extracción)</option>
                        <option value="Editor Jefe / Sintetizador">✍️ Editor (Síntesis)</option>
                        <option value="Analista Crítico">⚖️ Crítico (Gaps)</option>
                        <option value="Visionario">🚀 Visionario (Innovación)</option>
                    </select>
                    <button 
                        onClick={handleSyncSharePoint} 
                        title="Sincronizar SharePoint"
                        style={{ padding: '5px 10px' }}
                    >
                        🔄
                    </button>
                </div>
            </div>

            <div 
                ref={scrollRef}
                style={{ flex: 1, overflowY: 'auto', marginBottom: '10px', border: '1px solid var(--background-modifier-border)', padding: '10px', borderRadius: '4px' }}
            >
                {messages.map((m, i) => (
                    <div key={i} style={{ marginBottom: '15px', textAlign: m.role === 'user' ? 'right' : 'left' }}>
                        <div style={{ fontWeight: 'bold', fontSize: '0.8em', color: 'var(--text-muted)' }}>
                            {m.role === 'user' ? 'Tú' : `MI-AI (${m.agent || 'Asistente'})`}
                        </div>
                        <div style={{ 
                            display: 'inline-block', 
                            padding: '8px 12px', 
                            borderRadius: '10px', 
                            background: m.role === 'user' ? 'var(--interactive-accent)' : 'var(--background-secondary)',
                            color: m.role === 'user' ? 'white' : 'var(--text-normal)',
                            maxWidth: '90%',
                            whiteSpace: 'pre-wrap',
                            textAlign: 'left'
                        }}>
                            {m.content}
                        </div>
                        {m.role === 'assistant' && m.content.length > 50 && (
                            <div style={{ marginTop: '5px' }}>
                                <button 
                                    onClick={() => handleSaveToNote(m.content)}
                                    style={{ fontSize: '0.7em', padding: '2px 6px' }}
                                >
                                    💾 Guardar como nota
                                </button>
                            </div>
                        )}
                    </div>
                ))}
                {isLoading && <div style={{ fontSize: '0.8em', fontStyle: 'italic' }}>Escribiendo...</div>}
            </div>

            {currentMode === 'blueprint' && (
                <div style={{ 
                    padding: '10px', 
                    marginBottom: '10px', 
                    fontSize: '0.8em', 
                    background: 'var(--background-secondary)', 
                    border: '1px solid var(--interactive-accent)',
                    borderRadius: '4px' 
                }}>
                    <strong>🔮 Comandos de Blueprint:</strong>
                    <ul style={{ margin: '5px 0', paddingLeft: '20px' }}>
                        <li><code>/roadmap [tema]</code>: Investigación 360° (Estado del arte + Gaps + Visión).</li>
                        <li><code>/synergy [temas]</code>: Encuentra conexiones entre temas (ej: IA, Banca).</li>
                    </ul>
                </div>
            )}

            <div style={{ display: 'flex', gap: '5px' }}>
                <input 
                    type="text" 
                    value={input} 
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                    placeholder={currentMode === 'blueprint' ? "Escribe /roadmap o /synergy..." : "Pregunta algo a tu Segundo Cerebro..."}
                    style={{ flex: 1 }}
                />
                <button onClick={handleSend} disabled={isLoading}>Enviar</button>
            </div>
        </div>
    );
};
