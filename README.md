# NFT Extractor

A Python tool to extract NFT metadata, artwork, and descriptions from Ethereum using the Alchemy API.

## Features

- 🎨 Downloads primary media (videos, high-res images)
- 🖼️ Downloads thumbnails/poster images
- 📝 Extracts descriptions to text files
- 🔍 Fetches complete metadata as JSON
- 📊 Batch processing from Google Sheets
- ⚙️ Configurable thumbnail downloads
- 🏷️ Smart filename generation from NFT names
- 🌐 Prefers Alchemy gateway URLs for reliability

## Setup

1. Install dependencies:
```bash
pip install requests python-dotenv
```

2. Create `.env` file:
```
ALCHEMY_API_KEY=your_api_key_here
DOWNLOAD_THUMBNAILS=true
```

## Usage

### Individual NFT Extraction

Start the HTTP server:
```bash
python extractor-alchemy.py
```

Make a request:
```
http://localhost:3128?NFT_CONTRACT_ADDRESS=0xb932a70a57673d89f4acffbe830e8ed7f75fb9e0&FIRST_TOKEN_ID=29934
```

### Batch Processing from Google Sheets

Process all NFTs in a spreadsheet:
```bash
python retrieve-from-sheet.py "https://docs.google.com/spreadsheets/d/SHEET_ID/edit"
```

Process specific rows:
```bash
# Start from row 10, process 20 items
python retrieve-from-sheet.py "SHEET_URL" --start 10 --count 20

# Process only first 50 items
python retrieve-from-sheet.py "SHEET_URL" --count 50
```

**Spreadsheet Format:**

The spreadsheet should contain NFT URLs in any column. Supported formats:
- OpenSea: `https://opensea.io/assets/ethereum/0xCONTRACT/TOKEN`
- Rarible: `https://rarible.com/token/0xCONTRACT:TOKEN`
- Direct: `0xCONTRACT/TOKEN` or `0xCONTRACT TOKEN`

Empty rows are automatically skipped.

## Output

All files are saved to the `artwork/` directory with the NFT name as the base filename:

```
artwork/
  Garden-of-Forking-Paths.mp4         # Primary video
  Garden-of-Forking-Paths.png         # Thumbnail
  Garden-of-Forking-Paths.json        # Simplified metadata (name, description, tags, etc.)
  Garden-of-Forking-Paths-token.json  # Complete token data from Alchemy API
```

## Configuration

Edit `.env` to configure:

- `ALCHEMY_API_KEY`: Your Alchemy API key (required)
- `DOWNLOAD_THUMBNAILS`: Set to `false` to skip thumbnails (default: `true`)

## How It Works

1. **Fetches metadata** from Alchemy NFT API
2. **Identifies primary media** from `metadata.media.uri` (videos, high-res images)
3. **Downloads thumbnails** from `media[0].gateway` using Alchemy CDN
4. **Extracts description** to `.txt` file
5. **Saves complete metadata** to `.json` file
6. **Sanitizes filenames** from NFT names (spaces → hyphens, removes special chars)
7. **Detects duplicates** to avoid downloading the same file twice

## Notes

- NFT metadata structures vary by minting method
- Primary media often in `metadata.media.uri` (may be owner-only)
- Thumbnails typically in top-level `media` array
- Alchemy gateway URLs provide better reliability than raw IPFS
- File extensions naturally indicate content type

## Documentation

See [CLAUDE.md](CLAUDE.md) for detailed technical documentation and [SESSION_HISTORY.md](SESSION_HISTORY.md) for development history.
