import * as vscode from 'vscode';
import * as path from 'path';
import { execFile } from 'child_process';

// The parts of one finding the extension uses (full format: docs/04-findings.schema.json).
interface Finding {
	severity: string;
	file_path: string;
	line_number: number;
	explanation: string;
}

interface ScanResult {
	schema_version: string;
	findings: Finding[];
	summary: object;
}

let diagnostics: vscode.DiagnosticCollection;
let log: vscode.OutputChannel;

export function activate(context: vscode.ExtensionContext) {
	diagnostics = vscode.languages.createDiagnosticCollection('SecureFlow');
	log = vscode.window.createOutputChannel('SecureFlow');
	context.subscriptions.push(diagnostics, log);

	context.subscriptions.push(
		vscode.commands.registerCommand('secureflow.scanProject', () => scanProject(context))
	);
}

async function scanProject(context: vscode.ExtensionContext) {
	const folder = vscode.workspace.workspaceFolders?.[0];
	if (!folder) {
		vscode.window.showInformationMessage('Open a Flask project folder first.');
		return;
	}

	diagnostics.clear();

	// During development the engine sits next to the extension folder in the repo:
	// <repo>/extension (this extension) and <repo>/engine/main.py.
	const engineMain = path.join(context.extensionPath, '..', 'engine', 'main.py');
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
		const choice = await vscode.window.showErrorMessage(
			'SecureFlow could not read the scan result. Your files were not changed.',
			'Open log'
		);
		if (choice === 'Open log') {
			log.show();
		}
		return;
	}

	showFindings(projectPath, result.findings);
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

		const filePath = path.join(projectPath, finding.file_path);
		byFile.set(filePath, [...(byFile.get(filePath) ?? []), diagnostic]);
	}

	for (const [filePath, fileDiagnostics] of byFile) {
		diagnostics.set(vscode.Uri.file(filePath), fileDiagnostics);
	}

	log.appendLine(`Scan finished: ${findings.length} finding(s).`);
}

export function deactivate() {}
