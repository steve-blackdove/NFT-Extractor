import sys
import requests
import argparse
import re
import csv
from io import StringIO
from urllib.parse import urlparse, parse_qs

# Import from the main extractor
from dotenv import load_dotenv
import os
import json

# Load environment variables
load_dotenv()
ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY")

if not ALCHEMY_API_KEY:
    sys.stderr.write("[ERROR] ALCHEMY_API_KEY not found in .env file\n")
    sys.exit(1)


def convert_to_csv_url(sheets_url):
    """
    Convert a Google Sheets URL to a CSV export URL.

    Example input: https://docs.google.com/spreadsheets/d/1xmTotkBe5LFMeKUPDaH-pcZFZ7uXvUSJotjxbprhf1Q/edit?gid=0#gid=0
    Example output: https://docs.google.com/spreadsheets/d/1xmTotkBe5LFMeKUPDaH-pcZFZ7uXvUSJotjxbprhf1Q/export?format=csv&gid=0
    """
    # Extract spreadsheet ID from URL
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', sheets_url)
    if not match:
        sys.stderr.write(f"[ERROR] Could not extract spreadsheet ID from URL: {sheets_url}\n")
        sys.exit(1)

    spreadsheet_id = match.group(1)

    # Extract gid (sheet ID) if present
    gid = "0"  # default to first sheet
    parsed = urlparse(sheets_url)

    # Check query parameters
    query_params = parse_qs(parsed.query)
    if 'gid' in query_params:
        gid = query_params['gid'][0]

    # Check fragment (after #)
    if parsed.fragment:
        fragment_match = re.search(r'gid=(\d+)', parsed.fragment)
        if fragment_match:
            gid = fragment_match.group(1)

    csv_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    return csv_url


def fetch_csv_data(csv_url):
    """Fetch CSV data from Google Sheets export URL"""
    sys.stdout.write(f"[INFO] Fetching data from: {csv_url}\n")
    sys.stdout.flush()

    try:
        response = requests.get(csv_url)
        if response.status_code == 200:
            return response.text
        else:
            sys.stderr.write(f"[ERROR] Failed to fetch CSV. Status code: {response.status_code}\n")
            sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"[ERROR] Exception fetching CSV: {e}\n")
        sys.exit(1)


def parse_nft_url(url):
    """
    Parse NFT URL to extract contract address and token ID.

    Supports formats like:
    - https://opensea.io/assets/ethereum/0xb932a70a57673d89f4acffbe830e8ed7f75fb9e0/29934
    - https://rarible.com/token/0xb932a70a57673d89f4acffbe830e8ed7f75fb9e0:29934
    - Direct format: 0xb932a70a57673d89f4acffbe830e8ed7f75fb9e0/29934
    """
    if not url or not url.strip():
        return None, None

    url = url.strip()

    # Pattern 1: OpenSea format - /assets/ethereum/CONTRACT/TOKEN
    opensea_match = re.search(r'/assets/(?:ethereum|eth)/([0-9a-fA-Fx]+)/(\d+)', url)
    if opensea_match:
        return opensea_match.group(1), opensea_match.group(2)

    # Pattern 2: Rarible format - /token/CONTRACT:TOKEN
    rarible_match = re.search(r'/token/([0-9a-fA-Fx]+):(\d+)', url)
    if rarible_match:
        return rarible_match.group(1), rarible_match.group(2)

    # Pattern 3: Direct format - CONTRACT/TOKEN or CONTRACT:TOKEN
    direct_match = re.search(r'(0x[0-9a-fA-F]{40})[/:]+(\d+)', url)
    if direct_match:
        return direct_match.group(1), direct_match.group(2)

    # Pattern 4: Just a contract address and token on same line separated by whitespace or comma
    parts = re.split(r'[,\s]+', url)
    if len(parts) >= 2:
        contract_match = re.match(r'(0x[0-9a-fA-F]{40})', parts[0])
        token_match = re.match(r'(\d+)', parts[1])
        if contract_match and token_match:
            return contract_match.group(1), token_match.group(1)

    sys.stdout.write(f"[WARN] Could not parse NFT URL: {url}\n")
    sys.stdout.flush()
    return None, None


def fetch_metadata(contract_address, token_id):
    """Fetch NFT metadata from Alchemy API"""
    try:
        url = f"https://eth-mainnet.g.alchemy.com/nft/v2/{ALCHEMY_API_KEY}/getNFTMetadata?contractAddress={contract_address}&tokenId={token_id}&refreshCache=false"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            sys.stdout.write(f"[ERROR] Failed to fetch metadata for {contract_address}/{token_id}. Status: {response.status_code}\n")
    except Exception as e:
        sys.stdout.write(f"[EXCEPTION] Error fetching metadata: {e}\n")
    sys.stdout.flush()
    return None


def process_rows(csv_data, start_row=1, count=None):
    """
    Process rows from CSV data.

    Args:
        csv_data: CSV content as string
        start_row: Row number to start from (1-indexed, header is row 1)
        count: Maximum number of valid NFTs to process (None = all)
    """
    # Import save function from main extractor
    from importlib import import_module
    extractor = import_module('extractor-alchemy')

    csv_reader = csv.reader(StringIO(csv_data))
    rows = list(csv_reader)

    if not rows:
        sys.stdout.write("[WARN] No rows found in spreadsheet\n")
        return

    sys.stdout.write(f"[INFO] Found {len(rows)} total rows in spreadsheet\n")
    sys.stdout.flush()

    # Adjust for 0-indexing (user provides 1-indexed row numbers)
    start_idx = start_row - 1
    if start_idx < 0:
        start_idx = 0

    if count is not None:
        sys.stdout.write(f"[INFO] Will process {count} valid NFTs starting from row {start_row}\n")
    else:
        sys.stdout.write(f"[INFO] Will process all valid NFTs starting from row {start_row}\n")
    sys.stdout.flush()

    processed_count = 0
    skipped_count = 0
    current_row_idx = start_idx

    # Continue processing rows until we've processed enough valid NFTs or run out of rows
    while current_row_idx < len(rows):
        # If we've reached our count limit, stop
        if count is not None and processed_count >= count:
            break

        idx = current_row_idx
        current_row_idx += 1
        row = rows[idx]

        # Skip empty rows
        if not row or all(cell.strip() == '' for cell in row):
            sys.stdout.write(f"[INFO] Skipping empty row {idx + 1}\n")
            sys.stdout.flush()
            skipped_count += 1
            continue

        # Try to find NFT URL in any column
        nft_url = None
        for cell in row:
            if cell and cell.strip():
                # Check if this cell contains a URL or contract/token info
                contract, token = parse_nft_url(cell)
                if contract and token:
                    nft_url = cell
                    break

        if not nft_url:
            sys.stdout.write(f"[WARN] Row {idx + 1}: No valid NFT URL found: {row}\n")
            sys.stdout.flush()
            skipped_count += 1
            continue

        contract_address, token_id = parse_nft_url(nft_url)

        if not contract_address or not token_id:
            sys.stdout.write(f"[WARN] Row {idx + 1}: Could not parse NFT info from: {nft_url}\n")
            sys.stdout.flush()
            skipped_count += 1
            continue

        sys.stdout.write(f"\n[INFO] Row {idx + 1}: Processing {contract_address}/{token_id}\n")
        sys.stdout.flush()

        # Fetch and save NFT data
        metadata = fetch_metadata(contract_address, token_id)
        if metadata:
            extractor.save_all_resources(metadata, int(token_id), contract_address)
            processed_count += 1
        else:
            sys.stdout.write(f"[ERROR] Row {idx + 1}: Failed to fetch metadata\n")
            sys.stdout.flush()
            skipped_count += 1

    sys.stdout.write(f"\n[SUMMARY] Processed: {processed_count}, Skipped: {skipped_count}\n")
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(
        description='Retrieve NFTs from a Google Sheets spreadsheet',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  python retrieve-from-sheet.py "https://docs.google.com/spreadsheets/d/SHEET_ID/edit"
  python retrieve-from-sheet.py "SHEET_URL" --start 5 --count 10
  python retrieve-from-sheet.py "SHEET_URL" --count 20

The spreadsheet should contain NFT URLs in one of these formats:
  - OpenSea: https://opensea.io/assets/ethereum/0xCONTRACT/TOKEN
  - Rarible: https://rarible.com/token/0xCONTRACT:TOKEN
  - Direct: 0xCONTRACT/TOKEN or 0xCONTRACT TOKEN
        """
    )

    parser.add_argument('url', help='Google Sheets URL')
    parser.add_argument('--start', type=int, default=1,
                       help='Row number to start from (default: 1, first row)')
    parser.add_argument('--count', type=int, default=None,
                       help='Number of items to fetch (default: all)')

    args = parser.parse_args()

    sys.stdout.write(f"[INFO] Google Sheets URL: {args.url}\n")
    sys.stdout.write(f"[INFO] Start row: {args.start}\n")
    sys.stdout.write(f"[INFO] Count: {args.count if args.count else 'all'}\n")
    sys.stdout.flush()

    # Convert Google Sheets URL to CSV export URL
    csv_url = convert_to_csv_url(args.url)

    # Fetch CSV data
    csv_data = fetch_csv_data(csv_url)

    # Process rows
    process_rows(csv_data, start_row=args.start, count=args.count)

    sys.stdout.write("\n[INFO] Done!\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
