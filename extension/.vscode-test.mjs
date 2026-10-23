import { defineConfig } from '@vscode/test-cli';

export default defineConfig({
	files: 'out/test/**/*.test.js',
	// Open the engine's small sample app, so the scan has a Python file to report on.
	workspaceFolder: '../engine/tests/fixtures/hello_app',
});
