# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an NFT metadata and artwork extraction tool that uses the Alchemy API to fetch NFT data from Ethereum mainnet. The tool downloads NFT images and metadata for specified contract addresses and token ID ranges.

## Setup

1. Install required dependencies:
```bash
pip install requests python-dotenv
```

2. Create a `.env` file in the project root with your configuration:
```
ALCHEMY_API_KEY=your_api_key_here
DOWNLOAD_THUMBNAILS=true
```

Configuration options:
- `ALCHEMY_API_KEY`: Your Alchemy API key (required)
- `DOWNLOAD_THUMBNAILS`: Set to `false` to skip downloading thumbnail/still images, only downloading primary video/media files (default: `true`)

## Running the Application

### Method 1: HTTP Listener Server

Start the HTTP listener server:
```bash
python extractor-alchemy.py
```

The server listens on `localhost:3128` and accepts GET requests with query parameters:
- `NFT_CONTRACT_ADDRESS`: Ethereum contract address (required)
- `FIRST_TOKEN_ID`: Starting token ID, supports decimal or hex with 0x prefix (required)
- `LAST_TOKEN_ID`: Ending token ID, defaults to FIRST_TOKEN_ID if not provided (optional)

Example request:
```
http://localhost:3128?NFT_CONTRACT_ADDRESS=0xb932a70a57673d89f4acffbe830e8ed7f75fb9e0&FIRST_TOKEN_ID=29934&LAST_TOKEN_ID=29934
```

### Method 2: Google Sheets Batch Processing

Extract NFTs from a Google Sheets spreadsheet:
```bash
python retrieve-from-sheet.py "GOOGLE_SHEETS_URL"
python retrieve-from-sheet.py "GOOGLE_SHEETS_URL" --start 5 --count 10
python retrieve-from-sheet.py "GOOGLE_SHEETS_URL" --count 20
```

Parameters:
- First argument: Google Sheets URL (required)
- `--start N`: Start from row N (default: 1, first row)
- `--count N`: Process N items (default: all rows)

The spreadsheet should contain NFT URLs in any column. Supported formats:
- OpenSea: `https://opensea.io/assets/ethereum/0xCONTRACT/TOKEN`
- Rarible: `https://rarible.com/token/0xCONTRACT:TOKEN`
- Direct: `0xCONTRACT/TOKEN` or `0xCONTRACT TOKEN`

Empty rows are automatically skipped.

## Architecture

### Core Files

1. **`extractor-alchemy.py`**: Main NFT extraction engine
   - Runs as an HTTP server on port 3128
   - Handles individual NFT extraction
   - Contains all media download and metadata processing logic

2. **`retrieve-from-sheet.py`**: Batch processing script
   - Reads NFT URLs from Google Sheets
   - Converts Google Sheets URLs to CSV export format
   - Parses multiple NFT URL formats (OpenSea, Rarible, direct)
   - Imports and uses functions from `extractor-alchemy.py`
   - Supports pagination with `--start` and `--count`

### Key Functions

- `fetch_metadata(contract_address, token_id)`: Calls Alchemy API to retrieve NFT metadata
- `save_all_resources(metadata, token_id, contract_address)`: Extracts and saves all NFT resources with intelligent handling:
  - Uses `metadata.name` for base filename (sanitized for filesystem)
  - Saves simplified metadata to `.json` file (name, description, tags, createdBy, yearCreated)
  - Saves complete token data to `-token.json` file
  - Checks for primary media in `metadata.media.uri` (often high-res video/image)
  - Downloads thumbnail from top-level `media[0]` (if `DOWNLOAD_THUMBNAILS=true`)
  - Prefers Alchemy gateway URLs over raw IPFS URLs for better reliability
  - Detects and skips duplicate thumbnails when same URL appears in both locations
  - All files share the same base name, differentiated only by extension/suffix
- `download_file(url, token_id, contract_address, fmt)`: Downloads media files with proper extension detection
- `browse_nfts(contract_address, start_id, end_id)`: Iterates through a range of token IDs
- `start_http_listener()`: Runs HTTP server on port 3128 with RequestHandler

### File Naming Convention
All outputs use the NFT's `metadata.name` property as the base filename (sanitized for filesystem safety). File types are differentiated by extension and suffix:
- Spaces converted to hyphens
- Special characters removed
- Primary media: `Garden-of-Forking-Paths.mp4`
- Thumbnail: `Garden-of-Forking-Paths.png`
- Simplified metadata: `Garden-of-Forking-Paths.json`
- Full token data: `Garden-of-Forking-Paths-token.json`

If no name is available, falls back to `title` or `token-{token_id}`.

**Metadata Files:**
- `{name}.json` - Simplified metadata containing only: name, description, tags, createdBy, yearCreated
- `{name}-token.json` - Complete token metadata from Alchemy API (contract, tokenId, media URLs, etc.)

### Extension Detection Logic
The tool uses a multi-strategy approach for file extensions:
1. Extract from URL if present (removes query params first)
2. Use format field from metadata via `normalize_mime()` and `extension_from_mime()`
3. Handles various formats: jpg, png, gif, webp, svg, bmp, webm

### Output Directory
All downloads are saved to the `artwork/` directory (created automatically if missing).

## API Integration

The application uses Alchemy's NFT API v2:
- Endpoint: `https://eth-mainnet.g.alchemy.com/nft/v2/{API_KEY}/getNFTMetadata`
- The API key is loaded from the `.env` file using python-dotenv
- The application will exit with an error if the API key is not found

### NFT Metadata Structure Variations - Display Hierarchy

NFT metadata structures vary depending on how they were minted. The tool correctly prioritizes media sources:

1. **`metadata.media.uri`** - PRIMARY MEDIA (full-quality artwork)
   - Purpose: The actual, full-quality artwork that collectors own
   - Typical size: 50MB+ video files or high-resolution images
   - Use case: Full viewing experience when viewing the artwork in detail
   - Format: Complete piece (e.g., 1080x1080 video loop, high-res image)
   - Includes: `mimeType`, `size`, `dimensions`, and `uri` fields
   - Note: This field may be owner-only or hidden in some NFT contracts

2. **`media[0].gateway`** - THUMBNAIL/PREVIEW (quick-loading preview)
   - Purpose: Quick-loading preview/thumbnail for browsing
   - Typical size: 7MB PNG/GIF - much smaller and faster to load
   - Use case: Gallery views, marketplace listings, wallet displays, social media previews
   - Format: Static image or small animation representing the artwork

**Why This Structure?**
- **Performance**: Loading a 52MB video for every NFT in a gallery would be extremely slow
- **User Experience**: Users browsing collections need quick visual identification
- **Platform Compatibility**: Some platforms only support static images
- **Bandwidth**: Thumbnails ensure the gallery experience is responsive

The tool downloads both when available, sharing the same base filename but with different extensions.

Example output for a video NFT named "Garden of Forking Paths":
- `Garden-of-Forking-Paths.mp4` (50MB primary video from `metadata.media.uri`)
- `Garden-of-Forking-Paths.png` (6.8MB thumbnail from `media[0]`, using Alchemy gateway)
- `Garden-of-Forking-Paths.json` (simplified metadata: name, description, tags, createdBy, yearCreated)
- `Garden-of-Forking-Paths-token.json` (complete token data from Alchemy API)

### Gateway URL Preference

The tool always prefers Alchemy gateway URLs (`https://nft-cdn.alchemy.com/...`) over raw IPFS URLs for improved reliability and performance. The `prefer_alchemy_gateway()` function checks for gateway URLs first before falling back to raw URLs.

**IPFS SSL Handling**: The tool automatically disables SSL certificate verification for IPFS URLs (those starting with `https://ipfs.`) because IPFS gateway certificates frequently expire. This allows reliable downloads from IPFS sources while maintaining SSL verification for all other URLs.

## Security

- The `.env` file containing the Alchemy API key is excluded from git via `.gitignore`
- The `artwork/` directory is also excluded to avoid committing downloaded NFT files
- Never commit the `.env` file or expose the API key in code
