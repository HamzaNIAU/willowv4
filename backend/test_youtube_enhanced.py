#!/usr/bin/env python3
"""Test script for enhanced YouTube integration components"""

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.encryption_service import EncryptionService, TokenEncryption
from services.channel_cache import ChannelCache, get_channel_cache
from services.token_refresh_manager import TokenRefreshManager, get_refresh_manager
from services.youtube_file_service import YouTubeFileService
from services.supabase import DBConnection
from utils.logger import logger


class YouTubeEnhancedTester:
    """Test suite for enhanced YouTube features"""
    
    def __init__(self):
        self.db = DBConnection()
        self.results = {
            "encryption": {"passed": 0, "failed": 0},
            "cache": {"passed": 0, "failed": 0},
            "refresh": {"passed": 0, "failed": 0},
            "file_service": {"passed": 0, "failed": 0}
        }
    
    async def test_encryption_service(self):
        """Test AES-256-CBC encryption service"""
        print("\n" + "="*50)
        print("Testing Encryption Service")
        print("="*50)
        
        try:
            # Test 1: Initialize encryption service
            encryption = EncryptionService()
            print("✓ Encryption service initialized")
            self.results["encryption"]["passed"] += 1
            
            # Test 2: Encrypt and decrypt text
            test_token = "ya29.a0AfH6SMBx3jFakeTokenExample123456789"
            encrypted = encryption.encrypt(test_token)
            decrypted = encryption.decrypt(encrypted)
            
            assert decrypted == test_token, "Decryption failed"
            print(f"✓ Token encryption/decryption successful")
            print(f"  Original: {test_token[:20]}...")
            print(f"  Encrypted: {encrypted[:40]}...")
            self.results["encryption"]["passed"] += 1
            
            # Test 3: Encrypt JSON data
            test_data = {
                "access_token": test_token,
                "refresh_token": "refresh_token_example",
                "expiry": datetime.now(timezone.utc).isoformat()
            }
            
            encrypted_json = encryption.encrypt_json(test_data)
            decrypted_json = encryption.decrypt_json(encrypted_json)
            
            assert decrypted_json == test_data, "JSON decryption failed"
            print("✓ JSON encryption/decryption successful")
            self.results["encryption"]["passed"] += 1
            
            # Test 4: Token encryption interface
            token_enc = TokenEncryption()
            access_encrypted, refresh_encrypted = token_enc.encrypt_tokens(
                "access_token_test",
                "refresh_token_test"
            )
            
            access_decrypted, refresh_decrypted = token_enc.decrypt_tokens(
                access_encrypted,
                refresh_encrypted
            )
            
            assert access_decrypted == "access_token_test"
            assert refresh_decrypted == "refresh_token_test"
            print("✓ Token encryption interface working")
            self.results["encryption"]["passed"] += 1
            
        except Exception as e:
            print(f"✗ Encryption test failed: {e}")
            self.results["encryption"]["failed"] += 1
    
    async def test_channel_cache(self):
        """Test channel caching with LRU eviction"""
        print("\n" + "="*50)
        print("Testing Channel Cache")
        print("="*50)
        
        try:
            # Test 1: Initialize cache
            cache = ChannelCache(max_channels=5, ttl_seconds=2)
            print("✓ Channel cache initialized")
            self.results["cache"]["passed"] += 1
            
            # Test 2: Cache and retrieve metadata
            test_metadata = {
                "id": "test_channel_1",
                "name": "Test Channel",
                "subscriber_count": 1000
            }
            
            await cache.set_channel_metadata("user1", "channel1", test_metadata)
            retrieved = await cache.get_channel_metadata("user1", "channel1")
            
            assert retrieved == test_metadata, "Metadata retrieval failed"
            print("✓ Metadata caching working")
            self.results["cache"]["passed"] += 1
            
            # Test 3: Cache tokens
            await cache.set_channel_tokens(
                "user1",
                "channel1",
                "access_token",
                "refresh_token",
                datetime.now(timezone.utc) + timedelta(hours=1)
            )
            
            tokens = await cache.get_channel_tokens("user1", "channel1")
            assert tokens is not None
            assert tokens[0] == "access_token"
            print("✓ Token caching working")
            self.results["cache"]["passed"] += 1
            
            # Test 4: TTL expiration
            await asyncio.sleep(2.5)  # Wait for TTL to expire
            expired = await cache.get_channel_metadata("user1", "channel1")
            assert expired is None, "TTL expiration not working"
            print("✓ TTL expiration working")
            self.results["cache"]["passed"] += 1
            
            # Test 5: LRU eviction
            cache_small = ChannelCache(max_channels=2, ttl_seconds=60)
            
            # Add 3 items to cache with max size 2
            await cache_small.set_channel_metadata("user1", "ch1", {"id": "ch1"})
            await cache_small.set_channel_metadata("user1", "ch2", {"id": "ch2"})
            await cache_small.set_channel_metadata("user1", "ch3", {"id": "ch3"})
            
            # First item should be evicted
            ch1 = await cache_small.get_channel_metadata("user1", "ch1")
            ch2 = await cache_small.get_channel_metadata("user1", "ch2")
            ch3 = await cache_small.get_channel_metadata("user1", "ch3")
            
            assert ch1 is None, "LRU eviction not working"
            assert ch2 is not None
            assert ch3 is not None
            print("✓ LRU eviction working")
            self.results["cache"]["passed"] += 1
            
            # Test 6: Cache statistics
            stats = await cache.get_cache_stats()
            print(f"✓ Cache stats: {stats}")
            self.results["cache"]["passed"] += 1
            
        except Exception as e:
            print(f"✗ Cache test failed: {e}")
            self.results["cache"]["failed"] += 1
    
    async def test_refresh_manager(self):
        """Test token refresh manager"""
        print("\n" + "="*50)
        print("Testing Token Refresh Manager")
        print("="*50)
        
        try:
            # Test 1: Initialize refresh manager
            manager = TokenRefreshManager(
                max_concurrent=2,
                max_retries=2,
                rate_limit_per_minute=10
            )
            print("✓ Refresh manager initialized")
            self.results["refresh"]["passed"] += 1
            
            # Test 2: Start workers
            await manager.start()
            print(f"✓ Started {manager.max_concurrent} workers")
            self.results["refresh"]["passed"] += 1
            
            # Test 3: Get statistics
            stats = await manager.get_stats()
            print(f"✓ Manager stats: {stats}")
            assert stats["running"] == True
            assert stats["workers"] == 2
            self.results["refresh"]["passed"] += 1
            
            # Test 4: Stop workers
            await manager.stop()
            stats = await manager.get_stats()
            assert stats["running"] == False
            print("✓ Manager stopped successfully")
            self.results["refresh"]["passed"] += 1
            
        except Exception as e:
            print(f"✗ Refresh manager test failed: {e}")
            self.results["refresh"]["failed"] += 1
    
    async def test_file_service(self):
        """Test enhanced file service"""
        print("\n" + "="*50)
        print("Testing Enhanced File Service")
        print("="*50)
        
        try:
            # Test 1: Initialize file service
            service = YouTubeFileService(self.db, "test_user")
            print("✓ File service initialized")
            self.results["file_service"]["passed"] += 1
            
            # Test 2: File type detection
            test_files = [
                ("/tmp/video.mp4", "video"),
                ("/tmp/thumbnail.jpg", "thumbnail"),
                ("/tmp/image.png", "thumbnail"),
                ("/tmp/movie.avi", "video"),
                ("/tmp/unknown.xyz", "unknown")
            ]
            
            for file_path, expected_type in test_files:
                detected = await service.detect_file_type_enhanced(file_path)
                if detected == expected_type:
                    print(f"✓ Correctly detected {file_path} as {detected}")
                else:
                    print(f"✗ Failed to detect {file_path} (got {detected}, expected {expected_type})")
            self.results["file_service"]["passed"] += 1
            
            # Test 3: File pairing
            files = [
                "/tmp/video1.mp4",
                "/tmp/video1_thumbnail.jpg",
                "/tmp/video2.mp4",
                "/tmp/video3.avi",
                "/tmp/video3.png",
                "/tmp/random_image.jpg"
            ]
            
            pairs = await service.pair_files(files)
            print(f"✓ Paired {len(pairs)} video/thumbnail combinations")
            for video, thumbnail in pairs:
                if thumbnail:
                    print(f"  {Path(video).name} → {Path(thumbnail).name}")
                else:
                    print(f"  {Path(video).name} → No thumbnail")
            self.results["file_service"]["passed"] += 1
            
            # Test 4: Similarity calculation
            sim1 = service._calculate_similarity("video", "video")
            sim2 = service._calculate_similarity("video", "video_thumb")
            sim3 = service._calculate_similarity("video", "completely_different")
            
            print(f"  Debug: 'video' vs 'video': {sim1:.2f}")
            print(f"  Debug: 'video' vs 'video_thumb': {sim2:.2f}")
            print(f"  Debug: 'video' vs 'completely_different': {sim3:.2f}")
            
            assert sim1 == 1.0, "Identical strings should have similarity 1.0"
            assert sim2 > 0.4, f"Similar strings should have high similarity (got {sim2:.2f})"
            assert sim3 < 0.5, f"Different strings should have low similarity (got {sim3:.2f})"
            print(f"✓ Similarity calculation working")
            self.results["file_service"]["passed"] += 1
            
            # Test 5: Metadata preparation
            metadata = service._prepare_video_metadata(
                "/tmp/test_video.mp4",
                {"title": "Custom Title", "description": "Test Description"}
            )
            
            assert metadata["title"] == "Custom Title"
            assert metadata["description"] == "Test Description"
            assert "privacy" in metadata
            print(f"✓ Metadata preparation working")
            self.results["file_service"]["passed"] += 1
            
        except Exception as e:
            print(f"✗ File service test failed: {e}")
            self.results["file_service"]["failed"] += 1
    
    async def run_all_tests(self):
        """Run all test suites"""
        print("\n" + "="*60)
        print("ENHANCED YOUTUBE INTEGRATION TEST SUITE")
        print("="*60)
        
        # Run individual test suites
        await self.test_encryption_service()
        await self.test_channel_cache()
        await self.test_refresh_manager()
        await self.test_file_service()
        
        # Print summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        total_passed = 0
        total_failed = 0
        
        for component, stats in self.results.items():
            passed = stats["passed"]
            failed = stats["failed"]
            total = passed + failed
            total_passed += passed
            total_failed += failed
            
            status = "✓ PASSED" if failed == 0 else "✗ FAILED"
            print(f"{component.capitalize():15} {status:10} ({passed}/{total} tests passed)")
        
        print("-"*60)
        print(f"{'TOTAL':15} {'':10} ({total_passed}/{total_passed + total_failed} tests passed)")
        
        if total_failed == 0:
            print("\n🎉 All tests passed successfully!")
        else:
            print(f"\n⚠️  {total_failed} tests failed")
        
        return total_failed == 0


async def main():
    """Main test runner"""
    tester = YouTubeEnhancedTester()
    success = await tester.run_all_tests()
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    # Ensure we have necessary environment variables
    if not os.getenv("SUPABASE_URL"):
        print("Warning: SUPABASE_URL not set, some tests may fail")
    
    # Add path import
    from pathlib import Path
    
    asyncio.run(main())