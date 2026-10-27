import * as assert from 'assert';
import * as vscode from 'vscode';

suite('SecureFlow: Scan Project', () => {
	test('underlines the unprotected routes of the tiny app', async () => {
		await vscode.commands.executeCommand('secureflow.scanProject');

		const folder = vscode.workspace.workspaceFolders![0].uri;
		const found = vscode.languages.getDiagnostics(vscode.Uri.joinPath(folder, 'app.py'));

		// app.py in engine/tests/fixtures/tiny_app has 9 unprotected routes.
		assert.strictEqual(found.length, 9);
		for (const diagnostic of found) {
			assert.strictEqual(diagnostic.source, 'SecureFlow');
			assert.strictEqual(diagnostic.code, 'Unconfirmed');
		}

		// GET /status (line 29) is Medium: amber warning. POST /submit (line 34) is High: red error.
		const status = found.find((d) => d.range.start.line === 28)!;
		const submit = found.find((d) => d.range.start.line === 33)!;
		assert.strictEqual(status.severity, vscode.DiagnosticSeverity.Warning);
		assert.strictEqual(submit.severity, vscode.DiagnosticSeverity.Error);
	});

	test('Show Results opens the results view without an error', async () => {
		await vscode.commands.executeCommand('secureflow.showResults');
	});
});
