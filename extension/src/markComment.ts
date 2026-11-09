// Where to put "# secureflow: public" above a flagged route
// (docs/03-detection-rules.md, part 8).
//
// The engine only accepts the comment directly above the route's TOPMOST
// decorator, for example above @app.route in:
//
//     # secureflow: public      <- goes here
//     @app.route("/a")
//     @app.route("/b")
//     def handler(): ...
//
// The finding's line is the line of one route decorator (or of an
// add_url_rule call), which may sit below other decorators. So we walk up
// from that line over the decorators above it.
//
// This file does not use VS Code, so it can be tested on plain text.

export const MARK_COMMENT = '# secureflow: public';

// lines: the file's lines. routeLine: the finding's line, counted from 0.
// Returns the line (from 0) the comment must be inserted in front of.
export function markInsertLine(lines: string[], routeLine: number): number {
	let top = routeLine;
	let index = routeLine - 1;
	while (index >= 0) {
		const text = lines[index].trim();
		if (text.startsWith('@')) {
			top = index; // a one-line decorator, e.g. @cache
			index -= 1;
			continue;
		}
		// The last line of a decorator written over several lines, e.g.
		//     @app.route("/a",
		//                methods=["GET"])
		// Look up for its "@" line, and only accept it when the brackets
		// between the two lines are balanced (so it really is one decorator).
		const start = decoratorStart(lines, index);
		if (start === -1) {
			break; // a blank line, a comment or other code: the stack ends here
		}
		top = start;
		index = start - 1;
	}
	return top;
}

// The "@" line of a multi-line decorator ending at `end`, or -1.
function decoratorStart(lines: string[], end: number): number {
	for (let index = end; index >= 0 && index > end - 20; index--) {
		const text = lines[index].trim();
		if (text === '' || text.startsWith('#')) {
			return -1;
		}
		if (text.startsWith('@')) {
			// The "@" line must open a bracket it does not close (otherwise it is
			// a complete one-line decorator of some earlier function), and the
			// whole block must close every bracket it opens.
			const opensBracket = !bracketsBalanced(lines[index]);
			const closesAll = bracketsBalanced(lines.slice(index, end + 1).join('\n'));
			return opensBracket && closesAll ? index : -1;
		}
	}
	return -1;
}

function bracketsBalanced(text: string): boolean {
	const count = (character: string) => text.split(character).length - 1;
	return count('(') === count(')') && count('[') === count(']') && count('{') === count('}');
}

// The comment line to insert, with the same indentation as the line below it
// (routes inside a class or function are indented).
export function markCommentLine(lines: string[], insertLine: number): string {
	const indent = /^\s*/.exec(lines[insertLine] ?? '')?.[0] ?? '';
	return indent + MARK_COMMENT;
}

// True if the finding says a login decorator sits above the route decorator.
// Such a route stays flagged even when marked (the engine's rule), so the
// "Mark as public" action is not offered for it. The sentence comes from the
// explanation template in docs/03-detection-rules.md, part 3.
export function hasMisplacedDecorator(explanation: string): boolean {
	return explanation.includes('above the route decorator');
}
