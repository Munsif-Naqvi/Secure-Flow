import { defineConfig } from '@vscode/test-cli';

export default defineConfig({
	files: 'out/test/**/*.test.js',
	// Open the engine's tiny sample app: it has routes with and without login checks.
	workspaceFolder: '../engine/tests/fixtures/tiny_app',
});
