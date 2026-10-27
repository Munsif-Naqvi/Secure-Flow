import * as vscode from 'vscode';
import * as path from 'path';
import { Finding, ScanResult } from './types';

// What the side panel is showing right now.
type ViewState =
	| { kind: 'noScan' }
	| { kind: 'scanning'; folderName: string }
	| { kind: 'results'; projectPath: string; result: ScanResult };

// The results list in the SecureFlow side panel (layout: docs/figma/03-results.png).
// It is a "webview": a small web page inside VS Code. The page cannot touch
// VS Code itself, so it sends messages ("open finding 3", "scan again") and
// this class does the work.
export class ResultsView implements vscode.WebviewViewProvider {
	public static readonly viewId = 'secureflow.results';

	private view?: vscode.WebviewView;
	private state: ViewState = { kind: 'noScan' };

	public resolveWebviewView(webviewView: vscode.WebviewView) {
		this.view = webviewView;
		webviewView.webview.options = { enableScripts: true };
		webviewView.webview.onDidReceiveMessage((message) => this.onMessage(message));
		this.render();
	}

	public showScanning(folderName: string) {
		this.state = { kind: 'scanning', folderName };
		this.render();
	}

	public showResults(projectPath: string, result: ScanResult) {
		this.state = { kind: 'results', projectPath, result };
		this.render();
	}

	// Brings the side panel into view (used by "Show Results" and the status bar).
	public async reveal() {
		await vscode.commands.executeCommand(`${ResultsView.viewId}.focus`);
	}

	private async onMessage(message: { type: string; index?: number }) {
		if (message.type === 'scan') {
			await vscode.commands.executeCommand('secureflow.scanProject');
		} else if (message.type === 'open' && this.state.kind === 'results' && message.index !== undefined) {
			const finding = this.state.result.findings[message.index];
			if (finding) {
				await openAtLine(this.state.projectPath, finding);
			}
		}
	}

	private render() {
		if (this.view) {
			this.view.webview.html = pageHtml(this.state);
		}
	}
}

// Opens the finding's file with the cursor on its line.
async function openAtLine(projectPath: string, finding: Finding) {
	const uri = vscode.Uri.file(path.join(projectPath, finding.file_path));
	const line = finding.line_number - 1; // the engine counts lines from 1, VS Code from 0
	const position = new vscode.Position(line, 0);
	await vscode.window.showTextDocument(uri, {
		selection: new vscode.Range(position, position),
		preserveFocus: false,
	});
}

// Text from the scanned project (paths, explanations) goes into the HTML,
// so characters like < and & must be escaped or the page would break.
function escapeHtml(text: string): string {
	return text
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;');
}

function pageHtml(state: ViewState): string {
	let body: string;
	if (state.kind === 'noScan') {
		body = `
			<p class="muted">No scan yet. SecureFlow reads your Flask code and lists routes that have no login check.</p>
			<button class="primary" data-action="scan">Scan Project</button>`;
	} else if (state.kind === 'scanning') {
		body = `
			<h2>Scanning ${escapeHtml(state.folderName)}</h2>
			<p class="muted">Reading the code. Nothing is run and nothing leaves this computer.</p>`;
	} else {
		body = resultsHtml(state.result);
	}

	// A random "nonce" lets only our own script run on the page (a VS Code security rule).
	const nonce = Math.random().toString(36).slice(2) + Date.now().toString(36);
	return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>${STYLE}</style>
</head>
<body>
${body}
<script nonce="${nonce}">${SCRIPT}</script>
</body>
</html>`;
}

function resultsHtml(result: ScanResult): string {
	const count = result.findings.length;

	const summary = `
		<div class="card summary">
			<div class="headline"><span class="big">${count}</span> unprotected ${count === 1 ? 'route' : 'routes'} found</div>
			<p class="muted">Unconfirmed: found by reading the code, not tested live.</p>
			<div class="stats">
				<div><b>${result.routes.length}</b><span>Routes</span></div>
				<div><b>${result.summary.suspects_found}</b><span>Suspects</span></div>
				<div><b>${result.scan.files_scanned}</b><span>Files</span></div>
			</div>
		</div>`;

	let list: string;
	if (count === 0) {
		list = `<p class="muted">No unprotected routes found. This does not prove the app is safe.</p>`;
	} else {
		// Each card is identified by its position in the list, not by
		// finding_match_key: routes with the same path in the same file
		// (for example PUT and DELETE on /item/<id>) share one match key.
		const cards = result.findings.map((finding, index) => cardHtml(result, finding, index)).join('');
		list = `
			<div class="group"><span>Missing login checks</span><span class="muted">${count}</span></div>
			${cards}`;
	}

	return `${summary}${list}
		<div class="footer"><button class="primary" data-action="scan">Scan again</button></div>`;
}

function cardHtml(result: ScanResult, finding: Finding, index: number): string {
	// Findings do not carry HTTP methods, so take them from the matching route.
	const route = result.routes.find(
		(r) => r.file_path === finding.file_path && r.line_number === finding.line_number
	);
	const methods = route ? route.http_methods.join(', ') + ' ' : '';
	const severityClass = finding.severity === 'High' ? 'high' : 'medium';

	return `
		<div class="card finding" role="button" tabindex="0" data-index="${index}" title="Open ${escapeHtml(finding.file_path)}, line ${finding.line_number}">
			<div class="row">
				<span class="badge ${severityClass}">${escapeHtml(finding.severity)}</span>
				<code>${escapeHtml(methods + finding.url_path)}</code>
			</div>
			<div class="muted">${escapeHtml(finding.file_path)}, line ${finding.line_number} · No login check found</div>
			<div class="details">
				<span class="badge unconfirmed">Unconfirmed</span>
				<p>${escapeHtml(finding.explanation)}</p>
				<p class="muted">Unconfirmed means SecureFlow found this by reading the code. It has not been tested on a running copy of the app.</p>
			</div>
		</div>`;
}

// Colours come from the user's VS Code theme, so the panel matches light and dark themes.
const STYLE = `
	body { font-family: var(--vscode-font-family); font-size: var(--vscode-font-size); color: var(--vscode-foreground); padding: 8px 4px; }
	h2 { font-size: 1.15em; margin: 4px 0; }
	p { margin: 6px 0; line-height: 1.4; }
	code { font-family: var(--vscode-editor-font-family); }
	.muted { color: var(--vscode-descriptionForeground); }
	.card { display: block; width: 100%; box-sizing: border-box; text-align: left; margin: 0 0 8px; padding: 10px 12px;
		border: 1px solid var(--vscode-panel-border, transparent); border-radius: 6px;
		background: var(--vscode-sideBar-background); color: inherit; font: inherit; }
	.summary .headline { font-size: 1.1em; font-weight: 600; }
	.summary .big { font-size: 1.8em; margin-right: 4px; color: var(--vscode-editorWarning-foreground); }
	.stats { display: flex; gap: 20px; margin-top: 10px; padding-top: 8px; border-top: 1px solid var(--vscode-panel-border, transparent); }
	.stats div { display: flex; flex-direction: column; }
	.stats b { font-size: 1.2em; }
	.stats span { color: var(--vscode-descriptionForeground); font-size: 0.9em; }
	.group { display: flex; justify-content: space-between; font-weight: 600; margin: 14px 2px 6px; }
	.finding { cursor: pointer; }
	.finding:focus-visible { outline: 1px solid var(--vscode-focusBorder); }
	.finding:hover { background: var(--vscode-list-hoverBackground); }
	.finding.selected { border-color: var(--vscode-focusBorder); }
	.finding .row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
	.finding .details { display: none; margin-top: 8px; }
	.finding.selected .details { display: block; }
	.badge { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 0.85em; font-weight: 600; border: 1px solid currentColor; }
	.badge.high { color: var(--vscode-editorError-foreground); }
	.badge.medium { color: var(--vscode-editorWarning-foreground); }
	.badge.unconfirmed { color: var(--vscode-descriptionForeground); }
	button.primary { padding: 6px 14px; border: none; border-radius: 2px; cursor: pointer; font: inherit;
		background: var(--vscode-button-background); color: var(--vscode-button-foreground); }
	button.primary:hover { background: var(--vscode-button-hoverBackground); }
	.footer { margin-top: 12px; }
`;

// Runs inside the panel. Clicking a finding selects it (showing its
// explanation) and asks the extension to open the code at that line.
// Pressing Enter on a focused finding does the same as clicking it.
const SCRIPT = `
	const vscode = acquireVsCodeApi();
	function select(card) {
		document.querySelectorAll('.finding.selected').forEach((c) => c.classList.remove('selected'));
		card.classList.add('selected');
		vscode.postMessage({ type: 'open', index: Number(card.dataset.index) });
	}
	document.addEventListener('click', (event) => {
		if (event.target.closest('[data-action="scan"]')) {
			vscode.postMessage({ type: 'scan' });
			return;
		}
		const card = event.target.closest('.finding');
		if (card) {
			select(card);
		}
	});
	document.addEventListener('keydown', (event) => {
		const card = event.target.closest && event.target.closest('.finding');
		if (card && event.key === 'Enter') {
			select(card);
		}
	});
`;
