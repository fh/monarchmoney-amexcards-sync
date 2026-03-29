# American Express to Monarch Synchronization

This script helps bridge a gap in syncing American Express accounts with Monarch Money. When Monarch Money synchronizes your overall American Express account, it pulls in all transactions but does not distinguish *which* specific card (e.g. which Card Member) was used for each transaction. 

This script parses a standard American Express CSV export, matches each transaction with its corresponding entry already in Monarch, and applies a tag indicating which Card Member made the purchase (e.g., `Amex John Doe`). Go to the Amex website, download the statement (Format CSV with additional information checkbox checked), run the script.

## Warning
This entire thing is built as an experiment solely using GenAI prompts in Anti Gravity. The only guarantee I give is that 'it works for me'. If it messes up something on your end, I am sorry, but you should dry run this first.

## Prerequisites
- Python 3.9 or newer
- An active Monarch Money account
- An exported `.csv` of your transactions from the American Express web dashboard

## Setup

First, navigate to the folder where this script is located and create a Python virtual environment:

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the required dependencies
pip install -r requirements.txt
```

*(Note: We use the `monarchmoneycommunity` package, which is an actively maintained fork of the original SDK).*

## Usage

1. **Export your Data:** Go to your American Express account online and export your recent transactions as a CSV file.
2. **Activate the Environment:** Ensure your virtual environment is active (`source .venv/bin/activate`).
3. **Run the Script via terminal:**

```bash
python sync_amex_monarch.py /path/to/your/activity.csv
```

### Safely Testing with `--dry-run`
If you want to test the matching logic to see what tags would be applied *without* actually modifying your live Monarch data, append `--dry-run` to the command:

```bash
python sync_amex_monarch.py /path/to/your/activity.csv --dry-run
```

### Authentication
The script uses an interactive login prompt. The first time you run it, you will be prompted securely for:
- Your Monarch Money Email
- Your Monarch Money Password
- Your Multi-Factor Authentication (MFA) Code, if enabled

Once successfully authenticated, a secure session file is automatically saved locally so you won't need to sign in manually on subsequent runs.
