# WHAT DOES THIS FILE DO: Supabase S3 storage wrapper for uploading and retrieving files

# ================== IMPORTS ==================
import logging
from typing import Optional

from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, PGVECTOR_ENABLED, SUPABASE_STORAGE_BUCKET
# ================== IMPORTS ==================


# =========== VARIABLES : logging ===========
logger = logging.getLogger("storage")
# =========== VARIABLES : logging ===========


# =========== CLASS ===========

class SupabaseStorage:
    ''' Wrapper around Supabase storage bucket for file operations '''


    # =========== FUNCTION ===========
    def __init__(self, client, bucket_name: str):
        ''' Store the supabase client and bucket name '''

        # FLOW-1: Keep reference to client and check if its usable
        self._client = client
        self._bucket = bucket_name
        self._enabled = client is not None
    # =========== FUNCTION ===========


    # =========== FUNCTION ===========
    # ROLE: Upload raw file bytes to the S3 bucket at given key path
    def upload_file(self, s3_key: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
        ''' Upload bytes to bucket and return True on success '''

        # FLOW-1: Skip if storage not configured
        if not self._enabled:
            return False

        # FLOW-2: Upload to Supabase storage, upsert so re-uploads dont fail
        try:
            self._client.storage.from_(self._bucket).upload(
                s3_key, data, {"content-type": content_type, "upsert": "true"}
            )
            logger.info(f"storage: uploaded {s3_key} ({len(data)} bytes)")
            return True

        except Exception as exc:
            logger.warning(f"storage: upload failed for {s3_key}: {exc}")
            return False
    # =========== FUNCTION ===========


    # =========== FUNCTION ===========
    # ROLE: Generate a signed URL so user can download a private file
    def get_signed_url(self, s3_key: str, expires_in: int = 3600) -> Optional[str]:
        ''' Return time-limited signed URL or None if it fails '''

        # FLOW-1: Return None if storage not configured
        if not self._enabled:
            return None

        # FLOW-2: Ask Supabase to create signed URL with given expiry
        try:
            resp = self._client.storage.from_(self._bucket).create_signed_url(s3_key, expires_in)
            return resp.get("signedURL") or resp.get("signedUrl")

        except Exception as exc:
            logger.warning(f"storage: signed URL failed for {s3_key}: {exc}")
            return None
    # =========== FUNCTION ===========


    # =========== FUNCTION ===========
    # ROLE: Download file bytes from bucket for backend processing
    def download_file(self, s3_key: str) -> Optional[bytes]:
        ''' Return raw file bytes from S3, or None if download failed '''

        # FLOW-1: Return None if storage not configured
        if not self._enabled:
            return None

        # FLOW-2: Download and return bytes
        try:
            data = self._client.storage.from_(self._bucket).download(s3_key)
            return data

        except Exception as exc:
            logger.warning(f"storage: download failed for {s3_key}: {exc}")
            return None
    # =========== FUNCTION ===========


    # =========== FUNCTION ===========
    # ROLE: Remove a file from the bucket permanently
    def delete_file(self, s3_key: str) -> bool:
        ''' Delete file from bucket, return True if successful '''

        # FLOW-1: Return False if storage not configured
        if not self._enabled:
            return False

        # FLOW-2: Remove using list — Supabase storage delete takes a list of keys
        try:
            self._client.storage.from_(self._bucket).remove([s3_key])
            logger.info(f"storage: deleted {s3_key}")
            return True

        except Exception as exc:
            logger.warning(f"storage: delete failed for {s3_key}: {exc}")
            return False
    # =========== FUNCTION ===========


    # =========== FUNCTION ===========
    @property
    def enabled(self) -> bool:
        ''' Whether storage is available and configured '''
        return self._enabled
    # =========== FUNCTION ===========

# =========== CLASS ===========


# =========== INITIALIZATION ===========
# Initialize supabase_storage instance for use in routes

try:
    from supabase import create_client

    if PGVECTOR_ENABLED:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        supabase_storage = SupabaseStorage(_supabase_client, SUPABASE_STORAGE_BUCKET)
        logger.info(f"supabase_storage ready — bucket: {SUPABASE_STORAGE_BUCKET}")
    else:
        supabase_storage = None
        logger.info("supabase_storage disabled — Supabase credentials not set")

except Exception as exc:
    logger.warning(f"Failed to init supabase_storage: {exc}")
    supabase_storage = None

# =========== INITIALIZATION ===========
