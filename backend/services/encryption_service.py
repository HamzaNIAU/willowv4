"""AES-256-CBC Encryption Service for bank-grade token security"""

import os
import base64
import secrets
from typing import Tuple, Optional
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding, hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet
from utils.logger import logger


class EncryptionService:
    """Enterprise-grade encryption service using AES-256-CBC"""
    
    def __init__(self, master_key: Optional[str] = None):
        """
        Initialize encryption service with master key
        
        Args:
            master_key: Base64 encoded 32-byte master key
        """
        if master_key:
            self.master_key = base64.b64decode(master_key)
        else:
            # Get from environment or generate
            env_key = os.getenv("YOUTUBE_ENCRYPTION_MASTER_KEY")
            if env_key:
                self.master_key = base64.b64decode(env_key)
            else:
                # Generate new key for development (not for production!)
                logger.warning("No master key found, generating temporary key - NOT FOR PRODUCTION")
                self.master_key = os.urandom(32)
                logger.info(f"Generated master key (save this): {base64.b64encode(self.master_key).decode()}")
        
        if len(self.master_key) != 32:
            raise ValueError("Master key must be exactly 32 bytes")
        
        # Also maintain Fernet instance for backward compatibility
        fernet_key = os.getenv("MCP_CREDENTIAL_ENCRYPTION_KEY")
        if fernet_key:
            self.fernet = Fernet(fernet_key.encode())
        else:
            self.fernet = None
        
        logger.info("EncryptionService initialized with AES-256-CBC")
    
    def derive_key(self, salt: bytes, info: str = "youtube-token") -> bytes:
        """
        Derive an encryption key from master key using PBKDF2
        
        Args:
            salt: Random salt for key derivation
            info: Context information for key derivation
            
        Returns:
            32-byte derived key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,  # OWASP recommended minimum
            backend=default_backend()
        )
        return kdf.derive(self.master_key + info.encode())
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt data using AES-256-CBC with HMAC
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            Base64 encoded encrypted data with format:
            version(1) || salt(16) || iv(16) || ciphertext || hmac(32)
        """
        # Generate random salt and IV
        salt = os.urandom(16)
        iv = os.urandom(16)
        
        # Derive encryption key
        key = self.derive_key(salt)
        
        # Pad plaintext to AES block size (16 bytes)
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(plaintext.encode()) + padder.finalize()
        
        # Encrypt using AES-256-CBC
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        
        # Generate HMAC for integrity
        from cryptography.hazmat.primitives import hmac
        h = hmac.HMAC(key, hashes.SHA256(), backend=default_backend())
        h.update(iv + ciphertext)
        mac = h.finalize()
        
        # Combine: version || salt || iv || ciphertext || hmac
        version = b'\x01'  # Version 1
        encrypted_data = version + salt + iv + ciphertext + mac
        
        # Return base64 encoded
        return base64.b64encode(encrypted_data).decode('utf-8')
    
    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt data encrypted with AES-256-CBC
        
        Args:
            encrypted: Base64 encoded encrypted data
            
        Returns:
            Decrypted plaintext
            
        Raises:
            ValueError: If decryption fails or HMAC verification fails
        """
        try:
            # Decode from base64
            encrypted_data = base64.b64decode(encrypted)
            
            # Check version
            version = encrypted_data[0]
            if version == 1:
                # AES-256-CBC format
                return self._decrypt_aes(encrypted_data)
            elif version == ord('g'):
                # Likely Fernet format (starts with 'gAAAAA')
                if self.fernet:
                    return self._decrypt_fernet(encrypted)
                else:
                    raise ValueError("Fernet key not available for legacy decryption")
            else:
                raise ValueError(f"Unknown encryption version: {version}")
                
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError(f"Failed to decrypt data: {e}")
    
    def _decrypt_aes(self, encrypted_data: bytes) -> str:
        """
        Decrypt AES-256-CBC encrypted data
        
        Args:
            encrypted_data: Raw encrypted bytes
            
        Returns:
            Decrypted plaintext
        """
        # Parse components
        version = encrypted_data[0]
        salt = encrypted_data[1:17]
        iv = encrypted_data[17:33]
        mac = encrypted_data[-32:]
        ciphertext = encrypted_data[33:-32]
        
        # Derive key
        key = self.derive_key(salt)
        
        # Verify HMAC
        from cryptography.hazmat.primitives import hmac
        h = hmac.HMAC(key, hashes.SHA256(), backend=default_backend())
        h.update(iv + ciphertext)
        try:
            h.verify(mac)
        except Exception:
            raise ValueError("HMAC verification failed - data may be tampered")
        
        # Decrypt
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        
        # Remove padding
        unpadder = padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()
        
        return plaintext.decode('utf-8')
    
    def _decrypt_fernet(self, encrypted: str) -> str:
        """
        Decrypt legacy Fernet encrypted data
        
        Args:
            encrypted: Base64 encoded Fernet encrypted data
            
        Returns:
            Decrypted plaintext
        """
        if not self.fernet:
            raise ValueError("Fernet key not configured for legacy decryption")
        
        return self.fernet.decrypt(encrypted.encode()).decode()
    
    def migrate_from_fernet(self, fernet_encrypted: str) -> str:
        """
        Migrate a Fernet encrypted token to AES-256-CBC
        
        Args:
            fernet_encrypted: Fernet encrypted data
            
        Returns:
            AES-256-CBC encrypted data
        """
        # Decrypt with Fernet
        plaintext = self._decrypt_fernet(fernet_encrypted)
        
        # Re-encrypt with AES-256-CBC
        return self.encrypt(plaintext)
    
    def encrypt_json(self, data: dict) -> str:
        """
        Encrypt JSON data
        
        Args:
            data: Dictionary to encrypt
            
        Returns:
            Base64 encoded encrypted JSON
        """
        import json
        json_str = json.dumps(data, separators=(',', ':'))
        return self.encrypt(json_str)
    
    def decrypt_json(self, encrypted: str) -> dict:
        """
        Decrypt JSON data
        
        Args:
            encrypted: Base64 encoded encrypted JSON
            
        Returns:
            Decrypted dictionary
        """
        import json
        json_str = self.decrypt(encrypted)
        return json.loads(json_str)
    
    def generate_key(self) -> str:
        """
        Generate a new master key for initial setup
        
        Returns:
            Base64 encoded 32-byte key
        """
        key = os.urandom(32)
        return base64.b64encode(key).decode('utf-8')
    
    def rotate_key(self, old_encrypted: str, new_master_key: str) -> str:
        """
        Rotate encryption by re-encrypting with new master key
        
        Args:
            old_encrypted: Data encrypted with current master key
            new_master_key: New base64 encoded master key
            
        Returns:
            Data encrypted with new master key
        """
        # Decrypt with current key
        plaintext = self.decrypt(old_encrypted)
        
        # Create new service with new key
        new_service = EncryptionService(new_master_key)
        
        # Encrypt with new key
        return new_service.encrypt(plaintext)


class TokenEncryption:
    """High-level token encryption interface"""
    
    def __init__(self):
        self.service = EncryptionService()
    
    def encrypt_token(self, token: str) -> str:
        """Encrypt an OAuth token"""
        return self.service.encrypt(token)
    
    def decrypt_token(self, encrypted: str) -> str:
        """Decrypt an OAuth token"""
        return self.service.decrypt(encrypted)
    
    def encrypt_tokens(self, access_token: str, refresh_token: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """
        Encrypt both access and refresh tokens
        
        Args:
            access_token: Access token to encrypt
            refresh_token: Optional refresh token to encrypt
            
        Returns:
            Tuple of (encrypted_access, encrypted_refresh)
        """
        encrypted_access = self.encrypt_token(access_token)
        encrypted_refresh = self.encrypt_token(refresh_token) if refresh_token else None
        return encrypted_access, encrypted_refresh
    
    def decrypt_tokens(self, encrypted_access: str, encrypted_refresh: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """
        Decrypt both access and refresh tokens
        
        Args:
            encrypted_access: Encrypted access token
            encrypted_refresh: Optional encrypted refresh token
            
        Returns:
            Tuple of (access_token, refresh_token)
        """
        access_token = self.decrypt_token(encrypted_access)
        refresh_token = self.decrypt_token(encrypted_refresh) if encrypted_refresh else None
        return access_token, refresh_token


# Singleton instance
_encryption_service = None

def get_encryption_service() -> EncryptionService:
    """Get singleton encryption service instance"""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service

def get_token_encryption() -> TokenEncryption:
    """Get token encryption interface"""
    return TokenEncryption()