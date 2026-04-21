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
    const scrollRef = React.useRef<HTMLDivElement>(null);

    React.useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    const handleSend = async () => {
        if (!input.trim() || isLoading) return;

        const userMsg: Message = { role: 'user', content: input };
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

            const response = await fetch(`http://localhost:${settings.serverPort}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: input,
                    vault_path: app.vault.adapter.getBasePath(),
                    active_note_content: noteContent,
                    agent_role: currentAgent
                })
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
                        fullContent += data;
                        setMessages(prev => {
                            const newMsgs = [...prev];
                            newMsgs[newMsgs.length - 1].content = fullContent;
                            return newMsgs;
                        });
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

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '10px' }}>
            <div style={{ marginBottom: '10px' }}>
                <select 
                    value={currentAgent} 
                    onChange={(e) => setCurrentAgent(e.target.value)}
                    style={{ width: '100%', padding: '5px' }}
                >
                    <option value="Detective / Agente Extractor">🔍 Detective (Extracción)</option>
                    <option value="Editor Jefe / Sintetizador">✍️ Editor (Síntesis)</option>
                    <option value="Analista Crítico">⚖️ Crítico (Gaps)</option>
                    <option value="Visionario">🚀 Visionario (Innovación)</option>
                </select>
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

            <div style={{ display: 'flex', gap: '5px' }}>
                <input 
                    type="text" 
                    value={input} 
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                    placeholder="Pregunta algo a tu Segundo Cerebro..."
                    style={{ flex: 1 }}
                />
                <button onClick={handleSend} disabled={isLoading}>Enviar</button>
            </div>
        </div>
    );
};
