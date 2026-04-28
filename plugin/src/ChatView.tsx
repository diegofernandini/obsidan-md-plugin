import { ItemView, WorkspaceLeaf, TFile, MarkdownRenderer } from 'obsidian';
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

const MarkdownContent = ({ content, app }: { content: string, app: any }) => {
    const containerRef = React.useRef<HTMLDivElement>(null);

    React.useEffect(() => {
        if (containerRef.current) {
            containerRef.current.empty();
            MarkdownRenderer.renderMarkdown(
                content,
                containerRef.current,
                '',
                null as any
            );
        }
    }, [content]);

    return <div ref={containerRef} className="markdown-rendered-message" style={{ 
        fontSize: '14px', 
        lineHeight: '1.5',
        width: '100%',
        display: 'block'
    }} />;
};

const ChatComponent = ({ app, settings }: { app: any, settings: any }) => {
    const [messages, setMessages] = React.useState<Message[]>([]);
    const [input, setInput] = React.useState('');
    const [isLoading, setIsLoading] = React.useState(false);
    const [currentAgent, setCurrentAgent] = React.useState('Detective / Agente Extractor');
    const [currentMode, setCurrentMode] = React.useState('local');
    const [autoScroll, setAutoScroll] = React.useState(true);
    const scrollRef = React.useRef<HTMLDivElement>(null);

    const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
        const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
        const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
        setAutoScroll(isAtBottom);
    };

    React.useEffect(() => {
        if (autoScroll && scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, autoScroll]);

    const handleSend = async () => {
        if (!input.trim() || isLoading) return;

        const originalInput = input.trim();
        const userMsg: Message = { role: 'user', content: originalInput };
        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setIsLoading(true);

        const assistantMsg: Message = { 
            role: 'assistant', 
            content: '', 
            agent: originalInput.startsWith('/organize') ? '🏗️ Arquitecto de Bóveda' 
                 : originalInput.startsWith('/roadmap ') ? '🗺️ Roadmap Blueprint' 
                 : originalInput.startsWith('/synergy ') ? '🔮 Sinergia Blueprint' 
                 : currentAgent 
        };
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
            } else if (originalInput === '/organize') {
                endpoint = `http://localhost:${settings.serverPort}/blueprint/organize`;
                // No message needed, vault_path is sent in the body already
            }

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (!response.body) return;
            let fullContent = '';

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let currentEventData: string[] = [];

            if (reader) {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop() || ''; // Keep fragment for next chunk

                    for (let rawLine of lines) {
                        rawLine = rawLine.replace(/\r$/, '');
                        if (rawLine.startsWith('data:')) {
                            const dataContent = rawLine.startsWith('data: ') ? rawLine.slice(6) : rawLine.slice(5);
                            currentEventData.push(dataContent);
                        } else if (rawLine === '') {
                            // End of event
                            if (currentEventData.length > 0) {
                                const eventString = currentEventData.join('\n');
                                currentEventData = [];
                                
                                if (eventString === '[DONE]') break;
                                
                                if (eventString.startsWith('LOG: ')) {
                                    // Mensajes de sistema/progreso
                                    const logText = eventString.slice(5);
                                    setMessages(prev => {
                                        const newMsgs = [...prev];
                                        if (newMsgs.length > 0) {
                                            const lastMsg = newMsgs[newMsgs.length - 1];
                                            if (!lastMsg.content.includes('<!-- RESULT_LOADED -->')) {
                                                const newContent = (lastMsg.content ? lastMsg.content + '\n' : '') + `> ${logText.trim()}`;
                                                newMsgs[newMsgs.length - 1] = { ...lastMsg, content: newContent };
                                            }
                                        }
                                        return newMsgs;
                                    });
                                } else if (eventString.startsWith('RESULT: ')) {
                                    const resText = eventString.slice(8);
                                    setMessages(prev => {
                                        const newMsgs = [...prev];
                                        if (newMsgs.length > 0) {
                                            const lastMsg = newMsgs[newMsgs.length - 1];
                                            newMsgs[newMsgs.length - 1] = { ...lastMsg, content: resText + '<!-- RESULT_LOADED -->' };
                                        }
                                        return newMsgs;
                                    });
                                } else if (!eventString.startsWith('TRANSCRIPT: ')) {
                                    // ES UN TOKEN DE STREAMING: Unir sin saltos de línea (A menos que el token sea un \n)
                                    setMessages(prev => {
                                        const newMsgs = [...prev];
                                        if (newMsgs.length > 0) {
                                            const lastMsg = newMsgs[newMsgs.length - 1];
                                            const newContent = lastMsg.content + eventString;
                                            newMsgs[newMsgs.length - 1] = { ...lastMsg, content: newContent };
                                        }
                                        return newMsgs;
                                    });
                                }
                            }
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

    const handleNewChat = () => {
        if (isLoading) return;
        setMessages([]);
        setInput('');
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
        <>
            {/* Add styles for animations */}
            <style>
                {`
                .dot-flashing {
                  position: relative;
                  width: 6px;
                  height: 6px;
                  border-radius: 5px;
                  background-color: var(--text-muted);
                  color: var(--text-muted);
                  animation: dotFlashing 1s infinite linear alternate;
                  animation-delay: .5s;
                }
                .dot-flashing::before, .dot-flashing::after {
                  content: '';
                  display: inline-block;
                  position: absolute;
                  top: 0;
                }
                .dot-flashing::before {
                  left: -12px;
                  width: 6px;
                  height: 6px;
                  border-radius: 5px;
                  background-color: var(--text-muted);
                  color: var(--text-muted);
                  animation: dotFlashing 1s infinite alternate;
                  animation-delay: 0s;
                }
                .dot-flashing::after {
                  left: 12px;
                  width: 6px;
                  height: 6px;
                  border-radius: 5px;
                  background-color: var(--text-muted);
                  color: var(--text-muted);
                  animation: dotFlashing 1s infinite alternate;
                  animation-delay: 1s;
                }
                @keyframes dotFlashing {
                  0% { background-color: var(--text-muted); }
                  50%, 100% { background-color: rgba(var(--text-muted-rgb), 0.2); }
                }
                .markdown-rendered-message {
                  width: 100% !important;
                  font-size: 13px !important;
                  line-height: 1.45 !important;
                  word-break: normal !important;
                  overflow-wrap: break-word !important;
                }
                .markdown-rendered-message p { margin-bottom: 0.6em; }
                .markdown-rendered-message p:last-child { margin-bottom: 0; }
                .markdown-rendered-message h1, .markdown-rendered-message h2, .markdown-rendered-message h3 {
                  margin: 1em 0 0.5em 0;
                  color: var(--text-accent);
                  font-weight: 600;
                  line-height: 1.3;
                }
                .markdown-rendered-message h1 { font-size: 1.15em; }
                .markdown-rendered-message h2 { font-size: 1.05em; }
                .markdown-rendered-message h3 { font-size: 1em; }
                .markdown-rendered-message ul, .markdown-rendered-message ol {
                  padding-left: 1.2em;
                  margin: 0.6em 0;
                }
                .markdown-rendered-message li { margin: 0.3em 0; }
                .markdown-rendered-message strong { color: var(--text-normal); font-weight: 600; }
                .markdown-rendered-message blockquote {
                  border-left: 2px solid var(--interactive-accent);
                  margin: 0.6em 0;
                  padding-left: 0.8em;
                  color: var(--text-muted);
                }
                `}
            </style>
            <div style={{ 
                display: 'flex', 
                flexDirection: 'column', 
                height: '100%', 
                width: '100%',
                padding: '10px',
                background: 'var(--background-primary)',
                color: 'var(--text-normal)',
                fontFamily: 'var(--font-interface)',
                fontSize: '13px',
                boxSizing: 'border-box'
            }}>

            {/* Header / Controls */}
            <div style={{ 
                marginBottom: '12px', 
                display: 'flex', 
                flexDirection: 'column', 
                gap: '6px',
                padding: '0 4px'
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <span style={{ fontSize: '0.8em', fontWeight: 'bold', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>MI-AI Intelligence</span>
                    <button 
                        onClick={handleNewChat}
                        title="Nueva conversación"
                        className="mod-subtle"
                        style={{ 
                            background: 'var(--background-modifier-border)', 
                            border: '1px solid var(--background-modifier-border)', 
                            cursor: 'pointer', 
                            fontSize: '0.85em',
                            padding: '4px 10px',
                            borderRadius: '4px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            color: 'var(--text-normal)',
                            fontWeight: '500',
                            boxShadow: 'none',
                            transition: 'all 0.2s ease'
                        }}
                        onMouseOver={(e) => {
                            e.currentTarget.style.background = 'rgba(123, 97, 255, 0.15)';
                            e.currentTarget.style.borderColor = 'rgba(123, 97, 255, 0.3)';
                            e.currentTarget.style.boxShadow = '0 1px 4px rgba(0,0,0,0.1)';
                        }}
                        onMouseOut={(e) => {
                            e.currentTarget.style.background = 'var(--background-modifier-border)';
                            e.currentTarget.style.borderColor = 'var(--background-modifier-border)';
                            e.currentTarget.style.boxShadow = 'none';
                        }}
                    >
                        <span>+ Nuevo</span>
                    </button>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <select 
                        className="dropdown"
                        value={currentMode} 
                        onChange={(e) => setCurrentMode(e.target.value)}
                        style={{ 
                            width: '100%', 
                            padding: '4px 8px', 
                            borderRadius: '4px',
                            border: '1px solid var(--background-modifier-border)',
                            background: 'var(--background-primary)',
                            color: 'var(--text-normal)',
                            fontSize: '0.9em',
                            boxShadow: 'none',
                            cursor: 'pointer'
                        }}
                    >
                        <option value="local">Modo Local (Vault)</option>
                        <option value="web">Modo Web (Scraper)</option>
                        <option value="hybrid">Modo Híbrido (Pro)</option>
                        <option value="blueprint">Blueprints (Commands)</option>
                    </select>

                    {currentMode === 'local' && (
                        <select 
                            className="dropdown"
                            value={currentAgent} 
                            onChange={(e) => setCurrentAgent(e.target.value)}
                            style={{ 
                                width: '100%', 
                                padding: '4px 8px',
                                borderRadius: '4px',
                                border: '1px solid var(--background-modifier-border)',
                                background: 'var(--background-primary)',
                                color: 'var(--text-normal)',
                                fontSize: '0.9em',
                                boxShadow: 'none',
                                cursor: 'pointer'
                            }}
                        >
                            <option value="Detective / Agente Extractor">🔍 Detective (Extracción)</option>
                            <option value="Editor / Agente Sintetizador">✍️ Editor (Síntesis)</option>
                            <option value="Crítico / Abogado del Diablo">⚖️ Crítico (Brechas)</option>
                            <option value="Visionario / Innovador">💡 Visionario (Disrupción)</option>
                        </select>
                    )}
                </div>
            </div>

            {/* Inject Global Override CSS for Bubble Content */}
            <style>{`
                .markdown-rendered-message {
                    width: 100% !important;
                    min-width: 0 !important;
                }
                .markdown-rendered-message blockquote {
                    margin: 8px 0 !important;
                    padding: 4px 0 4px 12px !important;
                    border-left: 2px solid var(--interactive-accent) !important;
                    width: auto !important;
                    max-width: 100% !important;
                }
                /* Estilo especial para los logs del Arquitecto */
                .markdown-rendered-message p {
                    margin: 4px 0 !important;
                    width: 100% !important;
                    white-space: pre-wrap !important;
                    word-wrap: break-word !important;
                }
            `}</style>

            {/* Chat History */}
            <div 
                ref={scrollRef}
                onScroll={handleScroll}
                style={{ 
                    flex: 1, 
                    overflowY: 'auto', 
                    width: '100%',
                    marginBottom: '10px', 
                    border: '1px solid var(--background-modifier-border)', 
                    padding: '10px', 
                    borderRadius: '4px',
                    background: 'var(--background-primary-alt)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '15px',
                    boxSizing: 'border-box'
                }}
            >
                {messages.length === 0 && (
                    <div style={{ 
                        display: 'flex', 
                        flexDirection: 'column', 
                        alignItems: 'center', 
                        justifyContent: 'center', 
                        height: '100%', 
                        color: 'var(--text-muted)',
                        opacity: 0.6,
                        textAlign: 'center',
                        padding: '20px'
                    }}>
                        <div style={{ fontSize: '2.5em', marginBottom: '15px' }}>
                            {currentMode === 'local' && currentAgent.includes('Detective') && '🔍'}
                            {currentMode === 'local' && currentAgent.includes('Editor') && '✍️'}
                            {currentMode === 'local' && currentAgent.includes('Crítico') && '⚖️'}
                            {currentMode === 'local' && currentAgent.includes('Visionario') && '💡'}
                            {currentMode === 'web' && '🌐'}
                            {currentMode === 'hybrid' && '🤝'}
                            {currentMode === 'blueprint' && '🗺️'}
                        </div>
                        <h4 style={{ margin: '0 0 10px 0', color: 'var(--text-normal)' }}>
                            {currentMode === 'local' ? 'Interrogatorio Local' :
                             currentMode === 'web' ? 'Investigación Autónoma' :
                             currentMode === 'hybrid' ? 'Análisis Híbrido 360' :
                             'Ejecución Multi-Agente'}
                        </h4>
                        <p style={{ fontSize: '0.9em', maxWidth: '80%' }}>
                            {currentMode === 'local' && currentAgent.includes('Detective') && "Extraeré datos y hechos precisos desde el contexto de tus notas locales sin interpretación."}
                            {currentMode === 'local' && currentAgent.includes('Editor') && "Tomaré tus notas y redactaré un nuevo resumen ejecutivo coherente y con narrativa."}
                            {currentMode === 'local' && currentAgent.includes('Crítico') && "Buscaré brechas de información técnica y contradicciones ocultas en tus recortes."}
                            {currentMode === 'local' && currentAgent.includes('Visionario') && "Proyectaré el futuro y propondré innovaciones disruptivas usando de base tus notas."}
                            
                            {currentMode === 'web' && "Saldré a internet, buscaré fuentes, extraeré contexto de las mejores y simularé un debate interno para darte la respuesta más rica."}
                            {currentMode === 'hybrid' && "Revisaré tus notas locales y si detecto vacíos saldré a internet para comparar y complementar la información con datos externos."}
                            {currentMode === 'blueprint' && "Orquestaré un escuadrón pre-programado. Comandos: '/roadmap [tema]', '/synergy [temas]', o '/organize [Ruta_Carpeta]'."}
                        </p>
                    </div>
                )}
                {messages.map((m, i) => (
                    <div key={i} style={{ 
                        width: '100%',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: m.role === 'user' ? 'flex-end' : 'stretch'
                    }}>
                        <div style={{ 
                            fontWeight: '600', 
                            fontSize: '11px', 
                            color: 'var(--text-muted)', 
                            marginBottom: '4px', 
                            textTransform: 'uppercase',
                            padding: '0 4px',
                            textAlign: m.role === 'user' ? 'right' : 'left'
                        }}>
                            {m.role === 'user' ? 'Tú' : (m.agent || 'Asistente')}
                        </div>
                        <div style={{ 
                            padding: '12px 16px', 
                            borderRadius: '8px', 
                            background: m.role === 'user' ? 'var(--interactive-accent)' : 'var(--background-secondary)',
                            color: m.role === 'user' ? 'white' : 'var(--text-normal)',
                            maxWidth: m.role === 'user' ? '80%' : '100%',
                            minWidth: '50px',
                            border: m.role === 'user' ? 'none' : '1px solid var(--background-modifier-border)',
                            boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                            display: 'block',
                            boxSizing: 'border-box'
                        }}>
                            {m.role === 'user' ? (
                                <div style={{ whiteSpace: 'pre-wrap', textAlign: 'left', fontSize: '14px', lineHeight: '1.5' }}>{m.content}</div>
                            ) : (
                                <MarkdownContent content={m.content} app={app} />
                            )}
                        </div>
                        {m.role === 'assistant' && m.content.length > 50 && (
                            <div style={{ marginTop: '6px', textAlign: 'left' }}>
                                <button 
                                    onClick={() => handleSaveToNote(m.content)}
                                    className="mod-subtle"
                                    style={{ 
                                        fontSize: '10px', 
                                        padding: '4px 8px',
                                        borderRadius: '4px',
                                        background: 'transparent',
                                        color: 'var(--text-muted)',
                                        cursor: 'pointer',
                                        border: '1px solid var(--background-modifier-border)'
                                    }}
                                >
                                    💾 Guardar nota
                                </button>
                            </div>
                        )}
                    </div>
                ))}
                {isLoading && (
                    <div style={{ display: 'flex', gap: '15px', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.8em', padding: '5px' }}>
                        <div className="dot-flashing"></div>
                        <span>MI-AI analizando...</span>
                    </div>
                )}
            </div>

            {/* Blueprints Help */}
            {currentMode === 'blueprint' && (
                <div style={{ 
                    padding: '10px', 
                    marginBottom: '10px', 
                    fontSize: '0.8em', 
                    background: 'var(--background-secondary)', 
                    borderLeft: '2px solid var(--interactive-accent)',
                    borderRadius: '4px',
                    color: 'var(--text-muted)'
                }}>
                    <strong>🔮 Blueprints:</strong>
                    <ul style={{ margin: '4px 0', paddingLeft: '16px' }}>
                        <li><code>/roadmap [tema]</code></li>
                        <li><code>/synergy [tema1, tema2]</code></li>
                        <li><code>/organize</code> — organiza todo el vault (incremental)</li>
                    </ul>
                </div>
            )}

            {/* Input Area */}
            <div style={{ 
                display: 'flex', 
                alignItems: 'center',
                gap: '6px',
                background: 'var(--background-secondary)',
                padding: '4px 4px 4px 10px',
                borderRadius: '6px',
                border: '1px solid var(--background-modifier-border)'
            }}>
                <input 
                    type="text" 
                    value={input} 
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                    placeholder="..."
                    style={{ 
                        flex: 1, 
                        background: 'transparent', 
                        border: 'none', 
                        boxShadow: 'none',
                        padding: '6px 0',
                        color: 'var(--text-normal)',
                        fontSize: '0.95em',
                        minWidth: '50px'
                    }}
                />
                <button 
                    onClick={handleSend} 
                    disabled={isLoading || !input.trim()}
                    style={{ 
                        padding: '6px 12px',
                        background: input.trim() ? 'var(--interactive-accent)' : 'transparent',
                        color: input.trim() ? 'white' : 'var(--text-muted)',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: input.trim() ? 'pointer' : 'default',
                        fontWeight: '600',
                        fontSize: '0.85em',
                        flexShrink: 0
                    }}
                >
                    Enviar
                </button>
            </div>
        </div>
        </>
    );
};
