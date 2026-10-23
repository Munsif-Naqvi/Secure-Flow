import * as assert from 'assert';
import * as vscode from 'vscode';

suite('SecureFlow: Scan Project', () => {
	test('runs the engine and underlines line 1 of app.py', async () => {
		await vscode.commands.executeCommand('secureflow.scanProject');

		const folder = vscode.workspace.workspaceFolders![0].uri;
		const found = vscode.languages.getDiagnostics(vscode.Uri.joinPath(folder, 'app.py'));

		assert.strictEqual(found.length, 1);
		assert.strictEqual(found[0].source, 'SecureFlow');
		assert.strictEqual(found[0].range.start.line, 0);
		assert.strictEqual(found[0].severity, vscode.DiagnosticSeverity.Warning);
	});
});
