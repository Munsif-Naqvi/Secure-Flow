# SecureFlow

SecureFlow reads the code of a Python Flask app and points out routes that have **no login check**.

This is the FYP-1 midterm version. It only reads the code, it never runs your app, and it never sends your code anywhere. Every result is labelled **Unconfirmed**: it is a suspect found by reading the code, not a problem proven by a live test.

## How to use it

1. Open your Flask project folder in VS Code.
2. Run **SecureFlow: Scan Project** from the Command Palette (Ctrl+Shift+P, or Cmd+Shift+P on macOS).
3. Flagged routes are underlined in the editor and listed in the Problems panel, the SecureFlow results view (shield icon in the Activity Bar) and the status bar.

## Requirements

- Python 3.10 or newer, available as `python` or `python3` on your PATH. The engine uses only the Python standard library, so nothing else needs installing.

## Known limits

- Only Flask apps, and only the "missing login check" rule.
- No live tests yet, so nothing is ever marked Confirmed.
