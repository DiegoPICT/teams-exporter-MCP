# Development and Testing

## Local Setup

Run from the repository root with an active virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m bridge
```

Use `.env.example` if you want a starting point for local configuration.

## Manual Test Harness

The repository includes one manual consumer harness:

- `testing/emulate_consumer.py`

Example commands:

```bash
python3 testing/emulate_consumer.py --mode status
python3 testing/emulate_consumer.py --mode list-chats
python3 testing/emulate_consumer.py --mode active-chat
python3 testing/emulate_consumer.py --mode specific-chat --chat-index 1
python3 testing/emulate_consumer.py --mode extension-api --api-method GET --api-endpoint /api/chats
```

## Export Output

- The consumer harness writes exported chat JSON into `testing/output/`.
- That directory is ignored by git and should be treated as sensitive local output.
- Review files before sharing them outside your machine.

## Current Limitations

- Validation is manual today.
- There is no automated unit or integration suite yet.
- There is no CI workflow in this repository yet.
