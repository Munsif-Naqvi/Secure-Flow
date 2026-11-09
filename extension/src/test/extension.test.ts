import * as assert from 'assert';
import * as fs from 'fs';
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

	test('"Mark this route as public" adds the comment and the route leaves the list', async () => {
		const folder = vscode.workspace.workspaceFolders![0].uri;
		const appUri = vscode.Uri.joinPath(folder, 'app.py');
		const original = fs.readFileSync(appUri.fsPath, 'utf8');
		try {
			await vscode.commands.executeCommand('secureflow.scanProject');
			// GET /status is on line 29 (28 counted from 0).
			const actions = await vscode.commands.executeCommand<vscode.CodeAction[]>(
				'vscode.executeCodeActionProvider', appUri, new vscode.Range(28, 0, 28, 0)
			);
			const mark = actions.find((a) => a.title === 'SecureFlow: Mark this route as public');
			assert.ok(mark && mark.command, 'the lightbulb offers the action');
			await vscode.commands.executeCommand(mark.command.command, ...(mark.command.arguments ?? []));

			const lines = fs.readFileSync(appUri.fsPath, 'utf8').split(/\r?\n/);
			assert.strictEqual(lines[28], '# secureflow: public');
			assert.strictEqual(lines[29], '@app.get("/status")');
			// The scan ran again: 8 underlines instead of 9.
			assert.strictEqual(vscode.languages.getDiagnostics(appUri).length, 8);
		} finally {
			// Put the fixture back as it was, for the other tests.
			const document = await vscode.workspace.openTextDocument(appUri);
			if (document.isDirty) {
				await document.save();
			}
			fs.writeFileSync(appUri.fsPath, original);
			await vscode.commands.executeCommand('workbench.action.files.revert');
			await vscode.commands.executeCommand('secureflow.scanProject');
		}
	});
});
