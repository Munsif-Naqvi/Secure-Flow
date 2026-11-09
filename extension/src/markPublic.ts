import * as vscode from 'vscode';
import * as fs from 'fs';
import { hasMisplacedDecorator, markCommentLine, markInsertLine } from './markComment';
import { Finding } from './types';

// "Mark this route as public": writes "# secureflow: public" above a flagged
// route, then scans again. The engine then lists the route as
// developer_marked:comment instead of flagging it (docs/03-detection-rules.md, part 8).
//
// The file is only changed when the developer clicks the action, and the
// change is one undo step (Ctrl+Z removes it).

export const MARK_PUBLIC_COMMAND = 'secureflow.markPublic';

// What the last scan found, so the lightbulb and the results view can find
// the finding behind an underline.
export interface LastScan {
	projectPath: string;
	startedAt: number; // Date.now() when the scan started
	findings: Finding[];
	fileOf: (finding: Finding) => string; // absolute path of the finding's file
}

// The lightbulb on a SecureFlow underline offers "Mark this route as public".
export class MarkPublicActions implements vscode.CodeActionProvider {
	public static readonly kinds = [vscode.CodeActionKind.QuickFix];

	constructor(private readonly lastScan: () => LastScan | undefined) {}

	provideCodeActions(document: vscode.TextDocument, _range: vscode.Range, context: vscode.CodeActionContext) {
		const scan = this.lastScan();
		if (!scan) {
			return [];
		}
		const actions: vscode.CodeAction[] = [];
		for (const diagnostic of context.diagnostics) {
			if (diagnostic.source !== 'SecureFlow') {
				continue;
			}
			const finding = findingAt(scan, document.uri.fsPath, diagnostic.range.start.line + 1);
			if (!finding || !canMark(finding)) {
				continue;
			}
			const action = new vscode.CodeAction('SecureFlow: Mark this route as public', vscode.CodeActionKind.QuickFix);
			action.diagnostics = [diagnostic];
			action.command = {
				command: MARK_PUBLIC_COMMAND,
				title: 'Mark this route as public',
				arguments: [finding],
			};
			actions.push(action);
		}
		return actions;
	}
}

// Only a missing-login finding can be answered with a mark, and not when a
// login decorator sits above the route decorator (the engine keeps those
// flagged, so the mark would do nothing).
export function canMark(finding: Finding): boolean {
	return finding.problem_type === 'missing_login' && !hasMisplacedDecorator(finding.explanation);
}

function findingAt(scan: LastScan, filePath: string, lineNumber: number): Finding | undefined {
	return scan.findings.find(
		(finding) => finding.line_number === lineNumber && samePath(scan.fileOf(finding), filePath)
	);
}

function samePath(a: string, b: string): boolean {
	// Windows paths are not case-sensitive.
	return process.platform === 'win32' ? a.toLowerCase() === b.toLowerCase() : a === b;
}

// Inserts the comment, saves the file and scans again.
// Returns true if the comment was written.
export async function markPublic(scan: LastScan, finding: Finding): Promise<boolean> {
	const filePath = scan.fileOf(finding);
	const document = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));

	// The finding's line number is from the scan. If the file changed since
	// then, the line may now point at something else, so we refuse.
	const name = vscode.workspace.asRelativePath(filePath);
	if (document.isDirty || fs.statSync(filePath).mtimeMs > scan.startedAt) {
		vscode.window.showWarningMessage(`${name} changed since the scan. Save it and scan again before marking a route.`);
		return false;
	}

	const lines = document.getText().split(/\r?\n/);
	const insertLine = markInsertLine(lines, finding.line_number - 1);
	const eol = document.eol === vscode.EndOfLine.CRLF ? '\r\n' : '\n';

	const edit = new vscode.WorkspaceEdit();
	edit.insert(document.uri, new vscode.Position(insertLine, 0), markCommentLine(lines, insertLine) + eol);
	if (!(await vscode.workspace.applyEdit(edit))) {
		vscode.window.showErrorMessage(`SecureFlow could not change ${name}.`);
		return false;
	}
	// The engine reads the file from disk, so save before scanning again.
	await document.save();
	await vscode.window.showTextDocument(document, { selection: new vscode.Range(insertLine, 0, insertLine, 0) });
	return true;
}
