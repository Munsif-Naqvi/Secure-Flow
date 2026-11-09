import * as vscode from 'vscode';
import * as path from 'path';
import { execFile } from 'child_process';
import { ResultsView } from './resultsView';
import { LastScan, MARK_PUBLIC_COMMAND, MarkPublicActions, markPublic } from './markPublic';
import { Finding, ScanResult } from './types';

let diagnostics: vscode.DiagnosticCollection;
let log: vscode.OutputChannel;
let statusBar: vscode.StatusBarItem;
let resultsView: ResultsView;
let lastScan: LastScan | undefined; // what the last successful scan found

export function activate(context: vscode.ExtensionContext) {
	diagnostics = vscode.languages.createDiagnosticCollection('SecureFlow');
	log = vscode.window.createOutputChannel('SecureFlow');

	// The status bar item stays hidden until the first scan. Clicking it opens the results.
	statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
	statusBar.command = 'secureflow.showResults';

	resultsView = new ResultsView(() => lastScan);

	context.subscriptions.push(
		diagnostics,
		log,
		statusBar,
		vscode.window.registerWebviewViewProvider(ResultsView.viewId, resultsView),
		vscode.commands.registerCommand('secureflow.scanProject', () => scanProject(context)),
		vscode.commands.registerCommand('secureflow.showResults', () => resultsView.reveal()),
		// "Mark this route as public": from the lightbulb on an underline, or the results view.
		vscode.commands.registerCommand(MARK_PUBLIC_COMMAND, (finding: Finding) => markAndRescan(context, finding)),
		vscode.languages.registerCodeActionsProvider(
			{ language: 'python', scheme: 'file' },
			new MarkPublicActions(() => lastScan),
			{ providedCodeActionKinds: MarkPublicActions.kinds }
		)
	);
}

async function scanProject(context: vscode.ExtensionContext) {
	const folder = vscode.workspace.workspaceFolders?.[0];
	if (!folder) {
		vscode.window.showInformationMessage('Open a Flask project folder first.');
		return;
	}

	diagnostics.clear();
	lastScan = undefined;
	const startedAt = Date.now();
	statusBar.text = '$(sync~spin) SecureFlow: scanning';
	statusBar.show();
	resultsView.showScanning(folder.name);

	const engineMain = findEngine(context);
	const projectPath = folder.uri.fsPath;

	let result: ScanResult;
	try {
		const output = await vscode.window.withProgress(
			{ location: vscode.ProgressLocation.Notification, title: `Scanning ${folder.name}` },
			() => runEngine(engineMain, projectPath)
		);
		result = JSON.parse(output);
		if (!result.schema_version || !Array.isArray(result.findings) || !result.summary) {
			throw new Error('Engine output is missing schema_version, findings or summary.');
		}
	} catch (error) {
		log.appendLine(`Scan failed: ${error}`);
		statusBar.text = '$(warning) SecureFlow: scan failed';
		const choice = await vscode.window.showErrorMessage(
			'SecureFlow could not read the scan result. Your files were not changed.',
			'Open log'
		);
		if (choice === 'Open log') {
			log.show();
		}
		return;
	}

	lastScan = {
		projectPath,
		startedAt,
		findings: result.findings,
		fileOf: (finding) => path.join(projectPath, finding.file_path),
	};
	showFindings(projectPath, result.findings);
	updateStatusBar(result.findings.length);
	resultsView.showResults(projectPath, result);
	await resultsView.reveal();
}

// Writes "# secureflow: public" above the finding's route, then scans again
// so the route leaves the list.
async function markAndRescan(context: vscode.ExtensionContext, finding: Finding) {
	if (!lastScan) {
		vscode.window.showInformationMessage('Run SecureFlow: Scan Project first.');
		return;
	}
	if (await markPublic(lastScan, finding)) {
		await scanProject(context);
		vscode.window.showInformationMessage(
			`Marked ${finding.url_path} as public. A wrong mark hides a real problem: delete the comment to undo it.`
		);
	}
}

// Where engine/main.py is.
// - Development (F5) and tests: the engine in the repo, next to the extension folder:
//   <repo>/extension (this extension) and <repo>/engine/main.py.
//   So engine edits are picked up without repackaging.
// - Installed from the .vsix: the copy packed inside the extension folder
//   (copy-engine.js puts it there when packaging).
function findEngine(context: vscode.ExtensionContext): string {
	if (context.extensionMode !== vscode.ExtensionMode.Production) {
		return path.join(context.extensionPath, '..', 'engine', 'main.py');
	}
	return path.join(context.extensionPath, 'engine', 'main.py');
}

// Runs `python engine/main.py <folder>` and returns what it printed.
// If `python` is not installed (common on macOS and Linux), tries `python3`.
async function runEngine(engineMain: string, projectPath: string): Promise<string> {
	try {
		return await runCommand('python', [engineMain, projectPath]);
	} catch (error) {
		if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
			return await runCommand('python3', [engineMain, projectPath]);
		}
		throw error;
	}
}

function runCommand(command: string, args: string[]): Promise<string> {
	return new Promise((resolve, reject) => {
		execFile(command, args, (error, stdout, stderr) => {
			if (stderr) {
				log.appendLine(stderr);
			}
			if (error) {
				reject(error);
			} else {
				resolve(stdout);
			}
		});
	});
}

// Turns each finding into an underline (a "diagnostic") on its file and line.
function showFindings(projectPath: string, findings: Finding[]) {
	const byFile = new Map<string, vscode.Diagnostic[]>();

	for (const finding of findings) {
		// The engine counts lines from 1, VS Code counts from 0.
		const line = finding.line_number - 1;
		// Underline the whole line: VS Code trims the end to the real line length.
		const range = new vscode.Range(line, 0, line, Number.MAX_SAFE_INTEGER);
		const severity = finding.severity === 'High'
			? vscode.DiagnosticSeverity.Error
			: vscode.DiagnosticSeverity.Warning;

		const diagnostic = new vscode.Diagnostic(range, finding.explanation, severity);
		diagnostic.source = 'SecureFlow';
		// Shown next to the source in the hover and the Problems panel: "SecureFlow(Unconfirmed)".
		diagnostic.code = 'Unconfirmed';

		const filePath = path.join(projectPath, finding.file_path);
		byFile.set(filePath, [...(byFile.get(filePath) ?? []), diagnostic]);
	}

	for (const [filePath, fileDiagnostics] of byFile) {
		diagnostics.set(vscode.Uri.file(filePath), fileDiagnostics);
	}

	log.appendLine(`Scan finished: ${findings.length} finding(s).`);
}

// "SecureFlow: 3 unprotected routes", or "SecureFlow: no problems found".
function updateStatusBar(count: number) {
	if (count === 0) {
		statusBar.text = '$(shield) SecureFlow: no problems found';
	} else {
		statusBar.text = `$(shield) SecureFlow: ${count} unprotected ${count === 1 ? 'route' : 'routes'}`;
	}
	statusBar.tooltip = 'Unconfirmed: found by reading the code, not tested live. Click to see the results.';
	statusBar.show();
}

export function deactivate() {}
