import sys
import requests
import os
import json
import re
import mimetypes
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Alchemy API Key
ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY")
if not ALCHEMY_API_KEY:
    sys.stderr.write("[ERROR] ALCHEMY_API_KEY not found in .env file\n")
    sys.exit(1)

# Configuration: Download thumbnails/still images (default: true)
DOWNLOAD_THUMBNAILS = os.getenv("DOWNLOAD_THUMBNAILS", "true").lower() in ["true", "1", "yes"]

# Create directory for artwork and metadata if it doesn't exist
os.makedirs("artwork", exist_ok=True)

def has_extension(url):
    path = url.split("?")[0]  # remove query params
    return bool(re.search(r"\.[a-zA-Z0-9]{2,5}$", path))

def get_extension(url, fmt):
    if has_extension(url):
        return os.path.splitext(url.split("?")[0])[1]
    if fmt:
        mime_type = normalize_mime(fmt)
        ext = extension_from_mime(mime_type)
        return ext
    return ""

def normalize_mime(fmt):
    fmt = fmt.lower().strip()
    if '/' not in fmt:
        if fmt in ['jpg', 'jpeg']:
            return 'image/jpeg'
        if fmt == 'png':
            return 'image/png'
        if fmt == 'gif':
            return 'image/gif'
        if fmt == 'webp':
            return 'image/webp'
        if fmt == 'svg':
            return 'image/svg+xml'
        if fmt == 'bmp':
            return 'image/bmp'
        return f'image/{fmt}'
    return fmt

def extension_from_mime(mime_type):
    # Explicit mappings for missing or inconsistent mimetypes
    mime_map = {
        'image/webp': '.webp',
        'video/webm': '.webm',
        'image/jpg': '.jpg',
        'image/jpeg': '.jpg',
    }

    if mime_type in mime_map:
        return mime_map[mime_type]

    ext = mimetypes.guess_extension(mime_type)
    if ext == '.jpe':  # normalize uncommon .jpe
        return '.jpg'
    return ext or ''
    

def sanitize_filename(name):
    """Convert a string to a safe filename by replacing spaces and special chars"""
    # Replace spaces with hyphens
    name = name.replace(' ', '-')
    # Remove or replace characters that are unsafe for filenames
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    # Replace multiple hyphens with single hyphen
    name = re.sub(r'-+', '-', name)
    # Remove leading/trailing hyphens
    name = name.strip('-')
    return name

def download_file(url, base_filename, fmt=None):
    if not url:
        return
    try:
        sys.stdout.write(f"[DEBUG] Downloading from {url}\n")
        sys.stdout.flush()

        extension = get_extension(url, fmt)
        file_path = os.path.join("artwork", f"{base_filename}{extension}")

        # Disable SSL verification for IPFS URLs (certificates often expire)
        verify_ssl = not url.startswith('https://ipfs.')
        response = requests.get(url, verify=verify_ssl)
        if response.status_code == 200:
            with open(file_path, "wb") as file:
                file.write(response.content)
            sys.stdout.write(f"[INFO] File saved to {file_path}\n")
        else:
            sys.stdout.write(f"[ERROR] Failed to download from {url}\n")
    except Exception as e:
        sys.stdout.write(f"[EXCEPTION] Error downloading file: {e}\n")
    sys.stdout.flush()

def prefer_alchemy_gateway(media_item):
    """Prefer Alchemy gateway URL over raw IPFS URLs"""
    if media_item.get("gateway"):
        return media_item.get("gateway")
    return media_item.get("raw")

def save_all_resources(metadata, token_id, contract_address):
    try:
        sys.stdout.write(f"[DEBUG] Saving metadata for Token ID: {token_id}\n")
        sys.stdout.flush()

        # Get the NFT name for filename, fallback to token_id
        nft_name = metadata.get("metadata", {}).get("name", metadata.get("title", f"token-{token_id}"))
        base_filename = sanitize_filename(nft_name)

        sys.stdout.write(f"[DEBUG] Using base filename: {base_filename}\n")
        sys.stdout.flush()

        # Check for primary media in metadata.media.uri (often the full-res file)
        nested_media = metadata.get("metadata", {}).get("media", {})
        primary_downloaded = False

        if isinstance(nested_media, dict) and nested_media.get("uri"):
            primary_url = nested_media.get("uri")
            primary_mime = nested_media.get("mimeType", "")
            sys.stdout.write(f"[DEBUG] Found primary media in metadata.media.uri: {primary_url}\n")
            sys.stdout.flush()
            download_file(primary_url, base_filename, fmt=primary_mime)
            primary_downloaded = True

        # Download thumbnail from top-level media array (if enabled and not duplicate)
        if DOWNLOAD_THUMBNAILS:
            top_level_media = metadata.get("media", [])
            if top_level_media and len(top_level_media) > 0:
                media_item = top_level_media[0]
                gateway_url = prefer_alchemy_gateway(media_item)
                fmt = media_item.get("format")

                # Check if this is likely a duplicate of the primary media
                is_duplicate = False
                if isinstance(nested_media, dict) and nested_media.get("uri"):
                    # If URLs are similar or if both exist in metadata, assume duplicate
                    nested_uri = nested_media.get("uri", "")
                    if gateway_url and nested_uri and (nested_uri in gateway_url or gateway_url in nested_uri):
                        is_duplicate = True

                if gateway_url and not is_duplicate:
                    # Download thumbnail with same base name (extension will differentiate)
                    download_file(gateway_url, base_filename, fmt=fmt)
                elif is_duplicate:
                    sys.stdout.write(f"[INFO] Skipping duplicate thumbnail (same as primary media)\n")
                    sys.stdout.flush()
        else:
            sys.stdout.write(f"[INFO] Skipping thumbnail download (DOWNLOAD_THUMBNAILS=false)\n")
            sys.stdout.flush()

        # Save full token metadata JSON with -token suffix
        token_metadata_filename = f"{base_filename}-token.json"
        token_metadata_file_path = os.path.join("artwork", token_metadata_filename)
        with open(token_metadata_file_path, "w", encoding="utf-8") as metadata_file:
            json.dump(metadata, metadata_file, indent=4)
        sys.stdout.write(f"[INFO] Token metadata saved to {token_metadata_file_path}\n")

        # Extract and save simplified metadata from metadata section
        simplified_metadata = {}
        metadata_section = metadata.get("metadata", {})

        if metadata_section.get("name"):
            simplified_metadata["name"] = metadata_section.get("name")
        if metadata_section.get("description"):
            simplified_metadata["description"] = metadata_section.get("description")
        if metadata_section.get("tags"):
            simplified_metadata["tags"] = metadata_section.get("tags")
        if metadata_section.get("createdBy"):
            simplified_metadata["createdBy"] = metadata_section.get("createdBy")
        if metadata_section.get("yearCreated"):
            simplified_metadata["yearCreated"] = metadata_section.get("yearCreated")

        # Save simplified metadata JSON
        simple_metadata_filename = f"{base_filename}.json"
        simple_metadata_file_path = os.path.join("artwork", simple_metadata_filename)
        with open(simple_metadata_file_path, "w", encoding="utf-8") as simple_file:
            json.dump(simplified_metadata, simple_file, indent=4)
        sys.stdout.write(f"[INFO] Simplified metadata saved to {simple_metadata_file_path}\n")
    except Exception as e:
        sys.stdout.write(f"[EXCEPTION] Error saving resources for Token ID {token_id}: {e}\n")
    sys.stdout.flush()

def fetch_metadata(contract_address, token_id):
    try:
        url = f"https://eth-mainnet.g.alchemy.com/nft/v2/{ALCHEMY_API_KEY}/getNFTMetadata?contractAddress={contract_address}&tokenId={token_id}&refreshCache=false"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            sys.stdout.write(f"[ERROR] Failed to fetch metadata. Status: {response.status_code}\n")
    except Exception as e:
        sys.stdout.write(f"[EXCEPTION] Error fetching metadata: {e}\n")
    sys.stdout.flush()
    return None

def browse_nfts(contract_address, start_id, end_id):
    for token_id in range(start_id, end_id + 1):
        metadata = fetch_metadata(contract_address, token_id)
        if metadata:
            save_all_resources(metadata, token_id, contract_address)

def parse_token_id(value):
    try:
        return int(value, 16) if value.startswith("0x") else int(value)
    except ValueError:
        return None

def start_http_listener():
    class RequestHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            sys.stdout.write(f"[HTTP LOG] {self.client_address[0]} - {format % args}\n")
            sys.stdout.flush()

        def do_GET(self):
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            contract_address = query_params.get("NFT_CONTRACT_ADDRESS", [None])[0]
            first_token_id = query_params.get("FIRST_TOKEN_ID", [None])[0]
            last_token_id = query_params.get("LAST_TOKEN_ID", [first_token_id])[0]

            start_id = parse_token_id(first_token_id)
            end_id = parse_token_id(last_token_id)

            if contract_address and start_id is not None and end_id is not None:
                browse_nfts(contract_address, start_id, end_id)
                self.send_response(200)
            else:
                self.send_response(400)
                self.wfile.write(b"Invalid request. Provide NFT_CONTRACT_ADDRESS and FIRST_TOKEN_ID.\n")
            self.end_headers()

    server = HTTPServer(('localhost', 3128), RequestHandler)
    sys.stdout.write("[INFO] HTTP listener started on port 3128\n")
    sys.stdout.flush()
    server.serve_forever()

if len(sys.argv) <= 2:
    start_http_listener()
