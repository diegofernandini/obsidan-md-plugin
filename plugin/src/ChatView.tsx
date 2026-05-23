import { ItemView, WorkspaceLeaf, TFile, MarkdownRenderer } from 'obsidian';
import * as React from 'react';
import * as ReactDOM from 'react-dom/client';

export const VIEW_TYPE_CHAT = "mi-ai-chat-view";

interface Message {
    role: 'user' | 'assistant';
    content: string;
    agent?: string;
}

interface ChatSession {
    id: string;
    title: string;
    createdAt: number;
    messages: Message[];
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
            // Eliminar etiquetas internas antes de renderizar
            const cleanContent = content.replace('<!-- RESULT_LOADED -->', '');
            MarkdownRenderer.renderMarkdown(
                cleanContent,
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
    const [chatHistory, setChatHistory] = React.useState<ChatSession[]>([]);
    const [showHistory, setShowHistory] = React.useState(false);
    const [activeSessionId, setActiveSessionId] = React.useState<string | null>(null);
    const [saveState, setSaveState] = React.useState<'idle' | 'saving' | 'saved'>('idle');
    const savedBadgeTimerRef = React.useRef<number | null>(null);
    const scrollRef = React.useRef<HTMLDivElement>(null);

    const HISTORY_STORAGE_KEY = 'mi-ai-chat-history';
    const HISTORY_MAX_ITEMS = 20;

    React.useEffect(() => {
        try {
            const rawHistory = localStorage.getItem(HISTORY_STORAGE_KEY);
            if (!rawHistory) return;
            const parsed: ChatSession[] = JSON.parse(rawHistory);
            if (Array.isArray(parsed)) {
                setChatHistory(parsed);
            }
        } catch (error) {
            console.error('No se pudo cargar el historial del chat', error);
        }
    }, []);

    React.useEffect(() => {
        try {
            localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(chatHistory));
        } catch (error) {
            console.error('No se pudo guardar el historial del chat', error);
        }
    }, [chatHistory]);

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
                 : originalInput.startsWith('/explore ') ? '📚 Exploración literaria' 
                 : originalInput.startsWith('/ask ') ? '🧠 Deep Ask' 
                 : currentAgent 
        };
        setMessages(prev => [...prev, assistantMsg]);

        try {
            const activeFile = app.workspace.getActiveFile();
            let noteContent = "";
            if (activeFile instanceof TFile) {
                noteContent = await app.vault.read(activeFile);
            }

            let endpoint = `http://127.0.0.1:${settings.serverPort}/chat`;
            let body: any = {
                message: originalInput,
                vault_path: app.vault.adapter.getBasePath(),
                active_note_content: noteContent,
                agent_role: currentAgent,
                mode: currentMode
            };

            // Handle Slash Commands (override mode if necessary)
            if (originalInput.startsWith('/roadmap ')) {
                endpoint = `http://127.0.0.1:${settings.serverPort}/blueprint/roadmap`;
                body.message = originalInput.replace('/roadmap ', '').replace(/[\[\]]/g, '');
            } else if (originalInput.startsWith('/synergy ')) {
                endpoint = `http://127.0.0.1:${settings.serverPort}/blueprint/synergy`;
                const cleanInput = originalInput.replace('/synergy ', '').replace(/[\[\]]/g, '');
                const topics = cleanInput.split(',').map(s => s.trim());
                body = { topics, vault_path: app.vault.adapter.getBasePath() };
            } else if (originalInput.startsWith('/explore ')) {
                endpoint = `http://127.0.0.1:${settings.serverPort}/blueprint/explore`;
                const cleanInput = originalInput.replace('/explore ', '').replace(/[\[\]]/g, '');
                const topics = cleanInput.split(',').map(s => s.trim());
                body = { topics, vault_path: app.vault.adapter.getBasePath() };
            } else if (originalInput.startsWith('/ask ')) {
                endpoint = `http://127.0.0.1:${settings.serverPort}/blueprint/ask`;
                
                let cleanInput = originalInput.replace('/ask ', '').trim();
                let targetPath = null;
                // Parse optional target: /ask [folder/file] question
                const match = cleanInput.match(/^\[(.*?)\]\s*(.*)/);
                if (match) {
                    targetPath = match[1];
                    cleanInput = match[2];
                }
                
                body = { 
                    message: cleanInput, 
                    vault_path: app.vault.adapter.getBasePath(),
                    target_path: targetPath
                };
            } else if (originalInput === '/organize') {
                endpoint = `http://127.0.0.1:${settings.serverPort}/blueprint/organize`;
                // No message needed, vault_path is sent in the body already
            }

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (!response.ok) {
                setMessages(prev => [...prev, { role: 'system', content: `Error: ${response.status} - ${response.statusText}` }]);
                return;
            }

            if (!response.body) return;
            let fullContent = '';

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let currentEventData: string[] = [];

            if (reader) {
                while (true) {
                    const { done, value } = await reader.read();

                    // Flush remaining buffer when stream ends
                    if (done) {
                        buffer += decoder.decode();
                        if (buffer.trim()) {
                            buffer += '\n\n'; // force event flush
                        }
                    }

                    if (!done) {
                        buffer += decoder.decode(value, { stream: true });
                    }

                    const lines = buffer.split('\n');
                    buffer = done ? '' : (lines.pop() || ''); // Keep fragment for next chunk

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

                    if (done) break;
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
        setShowHistory(false);
        setActiveSessionId(null);
    };

    const buildSessionTitle = (sessionMessages: Message[]) => {
        const firstUserMessage = sessionMessages.find((m) => m.role === 'user');
        if (!firstUserMessage?.content) return 'Conversación sin título';
        const compact = firstUserMessage.content.trim().replace(/\s+/g, ' ');
        return compact.length > 48 ? `${compact.slice(0, 48)}...` : compact;
    };

    const saveChatToHistory = (sessionMessages: Message[], sessionId?: string) => {
        if (sessionMessages.length === 0) return;
        setSaveState('saving');
        const clonedMessages = sessionMessages.map((m) => ({ ...m }));
        const resolvedSessionId = sessionId ?? `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
        const session: ChatSession = {
            id: resolvedSessionId,
            title: buildSessionTitle(clonedMessages),
            createdAt: Date.now(),
            messages: clonedMessages
        };
        setChatHistory((prev) => {
            const withoutCurrent = prev.filter((item) => item.id !== resolvedSessionId);
            return [session, ...withoutCurrent].slice(0, HISTORY_MAX_ITEMS);
        });
        setActiveSessionId(resolvedSessionId);
        setSaveState('saved');
        if (savedBadgeTimerRef.current) {
            window.clearTimeout(savedBadgeTimerRef.current);
        }
        savedBadgeTimerRef.current = window.setTimeout(() => setSaveState('idle'), 1400);
    };

    const loadSession = (session: ChatSession) => {
        if (isLoading) return;
        setMessages(session.messages.map((m) => ({ ...m })));
        setInput('');
        setShowHistory(false);
        setActiveSessionId(session.id);
    };

    React.useEffect(() => {
        if (messages.length === 0) return;
        setSaveState('saving');
        const autosaveTimer = window.setTimeout(() => {
            saveChatToHistory(messages, activeSessionId ?? undefined);
        }, 400);

        return () => window.clearTimeout(autosaveTimer);
    }, [messages, activeSessionId]);

    React.useEffect(() => {
        return () => {
            if (savedBadgeTimerRef.current) {
                window.clearTimeout(savedBadgeTimerRef.current);
            }
        };
    }, []);

    const handleSaveToNote = async (content: string) => {
        const cleanContent = content.replace('<!-- RESULT_LOADED -->', '');
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const fileName = `MI-AI_Report_${timestamp}.md`;
        await app.vault.create(fileName, cleanContent);
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
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px', position: 'relative' }}>
                    <span style={{ fontSize: '0.8em', fontWeight: 'bold', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>MI-AI Intelligence</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', position: 'relative' }}>
                        <span
                            style={{
                                fontSize: '0.72em',
                                color: saveState === 'saved' ? 'var(--text-accent)' : 'var(--text-muted)',
                                opacity: saveState === 'idle' ? 0 : 1,
                                transition: 'opacity 0.2s ease, color 0.2s ease',
                                minWidth: '54px',
                                textAlign: 'right',
                                letterSpacing: '0.01em'
                            }}
                        >
                            {saveState === 'saving' ? 'Saving...' : saveState === 'saved' ? 'Saved' : ''}
                        </span>
                        <button
                            onClick={() => {
                                if (!showHistory && messages.length > 0) {
                                    saveChatToHistory(messages, activeSessionId ?? undefined);
                                }
                                setShowHistory((prev) => !prev);
                            }}
                            title="Mostrar historial del chat"
                            className="mod-subtle"
                            style={{
                                background: 'var(--background-modifier-border)',
                                border: '1px solid var(--background-modifier-border)',
                                cursor: 'pointer',
                                fontSize: '0.85em',
                                width: '28px',
                                height: '28px',
                                borderRadius: '4px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                color: 'var(--text-normal)',
                                boxShadow: showHistory ? '0 1px 4px rgba(123, 97, 255, 0.25)' : 'none',
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
                                e.currentTarget.style.boxShadow = showHistory ? '0 1px 4px rgba(123, 97, 255, 0.25)' : 'none';
                            }}
                        >
                            <svg width="15" height="15" viewBox="0 0 24 24" aria-hidden="true">
                                <path
                                    d="M12 2a10 10 0 1 0 10 10A10.012 10.012 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8.009 8.009 0 0 1-8 8zm1-12h-2v5.414l3.293 3.293 1.414-1.414L13 12.586z"
                                    fill="currentColor"
                                />
                            </svg>
                        </button>
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
                        {showHistory && (
                            <div
                                style={{
                                    position: 'absolute',
                                    top: '34px',
                                    right: 0,
                                    zIndex: 20,
                                    width: '280px',
                                    maxHeight: '280px',
                                    overflowY: 'auto',
                                    background: 'var(--background-primary-alt)',
                                    border: '1px solid var(--background-modifier-border)',
                                    borderRadius: '6px',
                                    boxShadow: '0 6px 18px rgba(0, 0, 0, 0.25)',
                                    padding: '6px'
                                }}
                            >
                                {chatHistory.length === 0 ? (
                                    <div style={{ color: 'var(--text-muted)', fontSize: '0.8em', padding: '8px' }}>
                                        Aun no hay conversaciones guardadas.
                                    </div>
                                ) : (
                                    chatHistory.map((session) => (
                                        <button
                                            key={session.id}
                                            onClick={() => loadSession(session)}
                                            style={{
                                                width: '100%',
                                                textAlign: 'left',
                                                border: '1px solid transparent',
                                                background: 'transparent',
                                                color: 'var(--text-normal)',
                                                borderRadius: '4px',
                                                padding: '8px',
                                                cursor: 'pointer',
                                                marginBottom: '4px'
                                            }}
                                            onMouseOver={(e) => {
                                                e.currentTarget.style.background = 'rgba(123, 97, 255, 0.12)';
                                                e.currentTarget.style.borderColor = 'rgba(123, 97, 255, 0.2)';
                                            }}
                                            onMouseOut={(e) => {
                                                e.currentTarget.style.background = 'transparent';
                                                e.currentTarget.style.borderColor = 'transparent';
                                            }}
                                        >
                                            <div style={{ fontSize: '0.82em', fontWeight: 500, marginBottom: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                                {session.title}
                                            </div>
                                            <div style={{ fontSize: '0.72em', color: 'var(--text-muted)' }}>
                                                {new Date(session.createdAt).toLocaleString()}
                                            </div>
                                        </button>
                                    ))
                                )}
                            </div>
                        )}
                    </div>
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
                        <option value="blueprint">Blueprints (/ask, /roadmap, /synergy, /explore, /organize)</option>
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
                            {currentMode === 'blueprint' && '📚'}
                        </div>
                        <h4 style={{ margin: '0 0 10px 0', color: 'var(--text-normal)' }}>
                            {currentMode === 'local' ? 'Interrogatorio Local' :
                             currentMode === 'web' ? 'Investigación Autónoma' :
                             currentMode === 'hybrid' ? 'Análisis Híbrido 360' :
                             'Blueprints MI-AI'}
                        </h4>
                        <p style={{ fontSize: '0.9em', maxWidth: '85%', lineHeight: 1.45 }}>
                            {currentMode === 'local' && currentAgent.includes('Detective') && "Extraeré datos y hechos precisos desde el contexto de tus notas locales sin interpretación."}
                            {currentMode === 'local' && currentAgent.includes('Editor') && "Tomaré tus notas y redactaré un nuevo resumen ejecutivo coherente y con narrativa."}
                            {currentMode === 'local' && currentAgent.includes('Crítico') && "Buscaré brechas de información técnica y contradicciones ocultas en tus recortes."}
                            {currentMode === 'local' && currentAgent.includes('Visionario') && "Proyectaré el futuro y propondré innovaciones disruptivas usando de base tus notas."}
                            
                            {currentMode === 'web' && "Saldré a internet, buscaré fuentes, extraeré contexto de las mejores y simularé un debate interno para darte la respuesta más rica."}
                            {currentMode === 'hybrid' && "Revisaré tus notas locales y si detecto vacíos saldré a internet para comparar y complementar la información con datos externos."}
                            {currentMode === 'blueprint' && (
                                <>
                                    <strong>/ask [ruta opcional] pregunta</strong> explora a profundidad el vault o una carpeta específica (ej: <code>/ask [Proyectos] ¿estado?</code>).
                                    <br /><br />
                                    <strong>/explore</strong> lanza búsquedas académicas por <em>ejes</em> (cada concepto, cada par de conceptos y, si aplica, la combinación completa) en arXiv y web académica, fusiona resultados y genera un informe con síntesis cruzada.
                                    <br /><br />
                                    También: <code style={{ fontSize: '0.88em' }}>/roadmap [tema]</code>, <code style={{ fontSize: '0.88em' }}>/synergy [t1, t2, …]</code> (sinergias híbrido local+web), <code style={{ fontSize: '0.88em' }}>/organize</code> (vault incremental).
                                </>
                            )}
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
                    <strong>🔮 Blueprints</strong>
                    <ul style={{ margin: '6px 0 8px 0', paddingLeft: '16px', lineHeight: 1.5 }}>
                        <li><code>/explore [c1, c2, …]</code> — <strong>exploración literaria multi-concepto</strong> (2–5 términos separados por comas). Búsqueda por ejes académicos, informe y guardado en <code>MI-AI Reports</code>.</li>
                        <li><code>/roadmap [tema]</code> — roadmap de investigación (local + web).</li>
                        <li><code>/synergy [tema1, tema2]</code> — matriz de sinergias (vault + web por tema).</li>
                        <li><code>/organize</code> — organiza el vault de forma incremental.</li>
                    </ul>
                    <div style={{ fontSize: '0.92em', color: 'var(--text-normal)', opacity: 0.9 }}>
                        Ejemplo: <code>/explore quantitative modeling, microstructures, finance</code>
                    </div>
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
                    placeholder={currentMode === 'blueprint'
                        ? '/explore concepto1, concepto2, concepto3'
                        : '...'}
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
