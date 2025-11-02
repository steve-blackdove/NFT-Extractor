# NFT Extractor Development Session History

## Project Overview
This is an NFT metadata and artwork extraction tool using the Alchemy API to fetch NFT data from Ethereum mainnet. The tool downloads NFT images, videos, metadata, and descriptions for specified contract addresses and token ID ranges.

## Session Summary

### Initial Request
User asked to analyze the codebase and create a CLAUDE.md file for future Claude Code instances.

### Major Features Implemented

#### 1. CLAUDE.md Creation
- Created comprehensive documentation covering:
  - Project overview and setup instructions
  - Running the application (HTTP server on port 3128)
  - Architecture (single-file Python application)
  - Key functions and their purposes
  - File naming conventions
  - Extension detection logic
  - NFT metadata structure variations
  - API integration details
  - Security considerations

#### 2. Nested Media Handling
**User Request:** NFT structures vary with minting. Sometimes the primary object (like full-res MP4) is in hidden owner-only fields in the JSON structure. When the poster still image is downloaded but no primary MP4 exists, retrieve the secondary MP4 from `metadata.media` node.

**Implementation:**
- Modified `save_all_resources()` to check `metadata.media.uri` first for primary media (videos, high-res images)
- Then downloads thumbnails from top-level `media[0].gateway`
- Both files are saved with appropriate extensions
- Example: For token 29934, successfully downloaded both 50MB MP4 and 6.8MB PNG thumbnail

#### 3. API Key Security
**User Request:** Separate the Alchemy API key into another file and exclude from git.

**Implementation:**
- Created `.env` file with API key
- Updated `extractor-alchemy.py` to use `python-dotenv` library
- Added validation to exit if API key not found
- Created `.gitignore` to exclude:
  - `.env` file
  - `artwork/` directory
  - Python cache files
  - Virtual environment directories

#### 4. Configuration System
**User Request:** Add configuration parameter (not hardcoded) to omit downloading still images, so only video files are downloaded.

**Implementation:**
- Added `DOWNLOAD_THUMBNAILS` configuration to `.env` file
- Defaults to `true`
- Set to `false` to skip thumbnail/still image downloads
- Only download primary media (videos, high-res content)

#### 5. Alchemy Gateway Preference
**User Request:** Since using Alchemy, always use Alchemy gateway nodes rather than raw nodes.

**Implementation:**
- Created `prefer_alchemy_gateway()` function
- Prioritizes Alchemy CDN URLs (`https://nft-cdn.alchemy.com/...`) over raw IPFS URLs
- Improves reliability and performance

#### 6. Smart Filename System
**User Request:** Use `metadata.name` property as base filename, altering to be filesystem-safe (converting spaces to hyphens).

**Implementation:**
- Created `sanitize_filename()` function that:
  - Replaces spaces with hyphens
  - Removes unsafe characters (`<>:"/\|?*`)
  - Removes multiple consecutive hyphens
  - Strips leading/trailing hyphens
- Falls back to `title` or `token-{token_id}` if name unavailable
- Example: "Garden of Forking Paths" → `Garden-of-Forking-Paths`

#### 7. Description Files
**User Request:** Create additional file with same name but `.txt` extension containing the description property.

**Implementation:**
- Extracts description from `metadata.description` or `description` field
- Saves to `.txt` file with same base filename
- UTF-8 encoding support

#### 8. Duplicate Prevention
**User Request:** Sometimes thumbnails in both media and metadata sections. When retrieving with thumbnails, only retrieve one.

**Implementation:**
- Added duplicate detection logic
- Checks if URLs are similar or contained within each other
- Skips duplicate downloads
- Logs when duplicates are detected

#### 9. Simplified Naming Convention
**User Request:** Thumbnail filenames and JSON metadata filenames should match the rest. `_thumb` and `_metadata` are obvious and redundant. `.json` files will always be metadata. `.png` (or other still image files) will always be thumbnails.

**Implementation:**
- Removed `_thumb` and `_metadata` suffixes
- All files share the same base filename
- File type differentiated by extension only:
  - `.mp4` = primary video
  - `.png` = thumbnail
  - `.txt` = description
  - `.json` = metadata

### Final File Structure Example
For NFT "Garden of Forking Paths" (token 29934):
```
artwork/
  Garden-of-Forking-Paths.mp4   (50MB primary video)
  Garden-of-Forking-Paths.png   (6.8MB thumbnail via Alchemy gateway)
  Garden-of-Forking-Paths.txt   (description text)
  Garden-of-Forking-Paths.json  (full metadata)
```

### Key Functions in extractor-alchemy.py

1. **`sanitize_filename(name)`** - Converts strings to safe filenames
2. **`prefer_alchemy_gateway(media_item)`** - Prefers Alchemy gateway URLs
3. **`download_file(url, base_filename, fmt)`** - Downloads media with extension detection
4. **`save_all_resources(metadata, token_id, contract_address)`** - Main orchestration function:
   - Determines base filename from metadata
   - Saves description to `.txt`
   - Downloads primary media from `metadata.media.uri`
   - Downloads thumbnail from `media[0]` (if enabled and not duplicate)
   - Saves metadata to `.json`
5. **`fetch_metadata(contract_address, token_id)`** - Calls Alchemy API
6. **`browse_nfts(contract_address, start_id, end_id)`** - Iterates through token IDs
7. **`start_http_listener()`** - HTTP server on port 3128

### Configuration (.env)
```
ALCHEMY_API_KEY=your_api_key_here
DOWNLOAD_THUMBNAILS=true
```

### Running the Application
```bash
python extractor-alchemy.py
```

HTTP request format:
```
http://localhost:3128?NFT_CONTRACT_ADDRESS=0xb932a70a57673d89f4acffbe830e8ed7f75fb9e0&FIRST_TOKEN_ID=29934&LAST_TOKEN_ID=29934
```

### Dependencies
- `requests` - HTTP requests
- `python-dotenv` - Environment variable management

### Testing Performed
- Verified nested media extraction (MP4 from `metadata.media.uri`)
- Verified thumbnail download (PNG from `media[0]`)
- Verified Alchemy gateway URL preference
- Verified filename sanitization
- Verified description file creation
- Verified duplicate detection
- Verified simplified naming (no suffixes)
- Verified configuration options (DOWNLOAD_THUMBNAILS)

### Important Notes
- The tool handles varying NFT metadata structures
- Primary media often in `metadata.media.uri` (owner-only or hidden fields)
- Thumbnails typically in top-level `media` array
- Alchemy gateway URLs provide better reliability than raw IPFS
- File extensions naturally indicate content type (no need for suffixes)

### 10. Google Sheets Batch Processing Script
**User Request:** Write a separate script that accepts a URL as the first argument pointing to a Google Sheets spreadsheet. Accepts additional parameters `--count xx` to limit items to fetch and `--start` to indicate which row to start on. Spreadsheet rows contain URLs for NFTs to be extracted. Blank lines should be skipped. If `--count` is omitted, all items retrieved. If `--start` is omitted, begin on first row. Call this script `retrieve-from-sheet.py`.

**Implementation:**
- Created `retrieve-from-sheet.py` with full argument parsing using `argparse`
- Converts Google Sheets URLs to CSV export URLs automatically
  - Extracts spreadsheet ID from URL
  - Extracts gid (sheet ID) from query params or fragment
  - Generates CSV export URL: `https://docs.google.com/spreadsheets/d/SHEET_ID/export?format=csv&gid=0`
- Parses multiple NFT URL formats:
  - OpenSea: `/assets/ethereum/CONTRACT/TOKEN`
  - Rarible: `/token/CONTRACT:TOKEN`
  - Direct: `0xCONTRACT/TOKEN` or `0xCONTRACT TOKEN`
- Implements row pagination:
  - `--start N`: Begin from row N (1-indexed)
  - `--count N`: Process N items
  - Default: process all rows from row 1
- Automatically skips empty rows
- Imports and uses `save_all_resources()` from `extractor-alchemy.py`
- Provides detailed logging:
  - Shows total rows found
  - Shows processing range
  - Logs each NFT extraction
  - Shows skipped rows and reasons
  - Summary at end (processed vs skipped)

**Testing:**
- Tested with provided spreadsheet (853 rows)
- Verified `--start` and `--count` parameters
- Confirmed empty row skipping
- Successfully processed multiple NFTs:
  - Row 1: Garden of Forking Paths (MP4 + PNG)
  - Row 3: Birds of Paradise (MP4 + GIF)

**Files Created:**
- `retrieve-from-sheet.py` - Main batch processing script
- `README.md` - User-friendly documentation with examples

### 11. Count Parameter Fix
**User Request:** The `--count` should refer to how many valid URLs to process, not how many sheet rows.

**Implementation:**
- Changed `process_rows()` to use a while loop instead of for loop
- Tracks `processed_count` for valid NFTs processed
- Continues through rows until count of valid NFTs is reached
- Skips empty/invalid rows without counting them toward the limit
- Example: `--count 2` processes 2 valid NFTs even if it needs to scan 5 rows

### 12. Media Source Clarification and SSL Fix
**User Request:** Primary media in some cases is missing. The `metadata.media` is the PRIMARY media source (full-quality artwork), and top-level `media` array is just the thumbnail/preview.

**Implementation:**
- Confirmed code was already correct (was treating `metadata.media.uri` as primary)
- Fixed SSL certificate verification issue preventing IPFS downloads
- Added SSL verification bypass for IPFS URLs (certificates frequently expire)
- Updated documentation with "Display Hierarchy" section explaining:
  - `metadata.media.uri` = PRIMARY (50MB+ full-quality artwork)
  - `media[0].gateway` = THUMBNAIL (7MB preview/poster image)
  - Why this structure exists (performance, UX, compatibility)

**Code Change:**
```python
# Disable SSL verification for IPFS URLs (certificates often expire)
verify_ssl = not url.startswith('https://ipfs.')
response = requests.get(url, verify=verify_ssl)
```

### 13. JSON File Structure Changes
**User Request:** Alter the filename of the JSON data by appending `-token` onto the end, so `big-bunny.json` becomes `big-bunny-token.json`. Create a new `.json` file that contains only metadata section fields: name, description, tags, createdBy, yearCreated.

**Implementation:**
- Full token metadata saved as `{name}-token.json` (complete Alchemy API response)
- Simplified metadata saved as `{name}.json` (only key fields from metadata section)
- Extracts only: name, description, tags, createdBy, yearCreated
- Simplified JSON is clean and easy to parse for integration

**Example Output:**
```json
{
    "name": "Garden of Forking Paths",
    "description": "An homage to...",
    "tags": ["impressionism", "landscape", ...],
    "createdBy": "mpkoz",
    "yearCreated": "2021"
}
```

### 14. Removed .txt File
**User Request:** Remove code that creates the .txt file. It has been replaced by the .json file.

**Implementation:**
- Removed description text file creation code
- Description now only exists in the simplified JSON file
- Cleaner output with fewer files per NFT

**Final File Structure per NFT:**
```
Garden-of-Forking-Paths.mp4         # 50MB primary video
Garden-of-Forking-Paths.png         # 6.8MB thumbnail
Garden-of-Forking-Paths.json        # 928 bytes simplified metadata
Garden-of-Forking-Paths-token.json  # 4.3KB complete token data
```

## Development Approach
- Used TodoWrite tool to track tasks throughout development
- Marked tasks completed as work progressed
- Tested each feature after implementation
- Updated documentation to match code changes
- Verified all changes with actual NFT data (tokens from SuperRare contract)
- Created comprehensive README for end users
- Iteratively refined based on user feedback
- Fixed SSL issues for IPFS gateway access
- Clarified media source hierarchy in documentation
