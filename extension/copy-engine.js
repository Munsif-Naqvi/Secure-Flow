// Copies the Python engine into the extension folder, so it is packed into the .vsix.
//
// In the repo the engine lives next to the extension: <repo>/engine.
// An installed extension only has the files inside its own folder, so before
// packaging we copy engine/main.py and engine/secureflow/*.py to
// extension/engine/. Tests, fixtures and score.py are not needed by users.
const fs = require('fs');
const path = require('path');

const source = path.join(__dirname, '..', 'engine');
const target = path.join(__dirname, 'engine');

// Start from an empty folder so a deleted engine file does not linger.
fs.rmSync(target, { recursive: true, force: true });
fs.mkdirSync(path.join(target, 'secureflow'), { recursive: true });

fs.copyFileSync(path.join(source, 'main.py'), path.join(target, 'main.py'));
for (const name of fs.readdirSync(path.join(source, 'secureflow'))) {
	if (name.endsWith('.py')) {
		fs.copyFileSync(path.join(source, 'secureflow', name), path.join(target, 'secureflow', name));
	}
}

console.log(`Copied the engine to ${target}`);
