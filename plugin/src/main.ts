import { App, Plugin, PluginSettingTab, Setting, WorkspaceLeaf, ItemView } from 'obsidian';
import * as child_process from 'child_process';
import { ChatView, VIEW_TYPE_CHAT } from './ChatView';

interface MIAISettings {
	pythonPath: string;
	serverPort: string;
	modelName: string;
}

const DEFAULT_SETTINGS: MIAISettings = {
	pythonPath: '/Users/diegofernandiini/obsidan-md-plugin/venv/bin/python3',
	serverPort: '8000',
	modelName: 'llama3.1'
}

export default class MIAIBrainPlugin extends Plugin {
	settings: MIAISettings;
	serverProcess: child_process.ChildProcess | null = null;

	async onload() {
		await this.loadSettings();

		this.registerView(
			VIEW_TYPE_CHAT,
			(leaf) => new ChatView(leaf, this.settings)
		);

		this.addRibbonIcon('brain', 'MI-AI Chat', () => {
			this.activateView();
		});

		this.addSettingTab(new MIAISettingTab(this.app, this));

		// Auto-start server
		this.startServer();
	}

	onunload() {
		this.stopServer();
	}

	async loadSettings() {
		this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
	}

	async saveSettings() {
		await this.saveData(this.settings);
	}

	startServer() {
		if (this.serverProcess) return;

		console.log('MI-AI: Iniciando servidor...');
		const serverScript = '/Users/diegofernandiini/obsidan-md-plugin/server.py';
		
		this.serverProcess = child_process.spawn(this.settings.pythonPath, [serverScript], {
			cwd: '/Users/diegofernandiini/obsidan-md-plugin',
			env: { ...process.env, PATH: '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin' }
		});

		this.serverProcess.stdout?.on('data', (data) => {
			console.log(`MI-AI Server: ${data}`);
		});

		this.serverProcess.stderr?.on('data', (data) => {
			console.error(`MI-AI Server Error: ${data}`);
		});

		this.serverProcess.on('close', (code) => {
			console.log(`MI-AI Server cerrado con código ${code}`);
			this.serverProcess = null;
		});
	}

	stopServer() {
		if (this.serverProcess) {
			this.serverProcess.kill();
			this.serverProcess = null;
		}
	}

	async activateView() {
		const { workspace } = this.app;

		let leaf: WorkspaceLeaf | null = null;
		const leaves = workspace.getLeavesOfType(VIEW_TYPE_CHAT);

		if (leaves.length > 0) {
			leaf = leaves[0];
		} else {
			leaf = workspace.getRightLeaf(false);
			if (leaf) {
				await leaf.setViewState({ type: VIEW_TYPE_CHAT, active: true });
			}
		}

		if (leaf) {
			workspace.revealLeaf(leaf);
		}
	}
}

class MIAISettingTab extends PluginSettingTab {
	plugin: MIAIBrainPlugin;

	constructor(app: App, plugin: MIAIBrainPlugin) {
		super(app, plugin);
		this.plugin = plugin;
	}

	display(): void {
		const { containerEl } = this;
		containerEl.empty();

		new Setting(containerEl)
			.setName('Ruta de Python (Venv)')
			.setDesc('Ruta al ejecutable de python en tu entorno virtual.')
			.addText(text => text
				.setPlaceholder('/ruta/a/tu/venv/bin/python3')
				.setValue(this.plugin.settings.pythonPath)
				.onChange(async (value) => {
					this.plugin.settings.pythonPath = value;
					await this.plugin.saveSettings();
				}));

		new Setting(containerEl)
			.setName('Puerto del Servidor')
			.setDesc('Puerto en el que corre FastAPI.')
			.addText(text => text
				.setPlaceholder('8000')
				.setValue(this.plugin.settings.serverPort)
				.onChange(async (value) => {
					this.plugin.settings.serverPort = value;
					await this.plugin.saveSettings();
				}));
        
        new Setting(containerEl)
			.setName('Modelo de Ollama')
			.setDesc('Nombre del modelo descargado en Ollama.')
			.addText(text => text
				.setPlaceholder('llama3.1')
				.setValue(this.plugin.settings.modelName)
				.onChange(async (value) => {
					this.plugin.settings.modelName = value;
					await this.plugin.saveSettings();
				}));

		new Setting(containerEl)
			.setName('Reiniciar Servidor')
			.setDesc('Detiene e inicia el servidor de nuevo para aplicar cambios.')
			.addButton(btn => btn
				.setButtonText('Reiniciar Now')
				.onClick(() => {
					this.plugin.stopServer();
					this.plugin.startServer();
				}));
	}
}
