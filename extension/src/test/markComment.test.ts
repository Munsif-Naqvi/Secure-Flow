import * as assert from 'assert';
import { hasMisplacedDecorator, markCommentLine, markInsertLine } from '../markComment';

// Where "# secureflow: public" goes (docs/03-detection-rules.md, part 8):
// directly above the route's topmost decorator. Line numbers count from 0.
suite('SecureFlow: where the public mark goes', () => {
	test('right above a single route decorator', () => {
		const lines = ['x = 1', '', '@app.route("/a")', 'def a():', '    return "a"'];
		assert.strictEqual(markInsertLine(lines, 2), 2);
		assert.strictEqual(markCommentLine(lines, 2), '# secureflow: public');
	});

	test('above a stack of decorators, even when the route decorator is not the first', () => {
		const lines = ['', '@app.route("/a")', '@app.route("/b")', 'def a():', '    return "a"'];
		assert.strictEqual(markInsertLine(lines, 2), 1); // finding on @app.route("/b")
	});

	test('above a decorator written over several lines', () => {
		const lines = ['', '@cache', '@app.route("/a",', '           methods=["GET"])', '@app.route("/b")', 'def a():'];
		assert.strictEqual(markInsertLine(lines, 4), 1);
	});

	test('does not climb into the function above when there is no blank line', () => {
		const lines = ['@app.route("/x")', 'def x(): return 1', '@app.route("/y")', 'def y(): return 2'];
		assert.strictEqual(markInsertLine(lines, 2), 2);
	});

	test('stops at an existing comment block', () => {
		const lines = ['# ---', '# about this route', '@app.route("/a")', 'def a():'];
		assert.strictEqual(markInsertLine(lines, 2), 2);
	});

	test('add_url_rule: right above the call, with its indentation', () => {
		const lines = ['def create_app():', '    app.add_url_rule("/h", view_func=h)'];
		assert.strictEqual(markInsertLine(lines, 1), 1);
		assert.strictEqual(markCommentLine(lines, 1), '    # secureflow: public');
	});

	test('a login decorator above the route decorator is recognised from the explanation', () => {
		assert.ok(hasMisplacedDecorator('... A @login_required sits above the route decorator, so Flask ignores it; move it below. ...'));
		assert.ok(!hasMisplacedDecorator('This route (GET /a) has no login check that SecureFlow could find.'));
	});
});
