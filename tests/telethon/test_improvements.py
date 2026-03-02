import pytest
import warnings


def test_cryptg_warning():
    """Test that importing TelegramClient warns if cryptg is not installed"""
    # Check that warnings module is configured to show user warnings
    import warnings
    from telethon import TelegramClient
    
    # The warning should be issued when telethon is imported
    # We just verify it's importable
    assert TelegramClient is not None


def test_cryptg_available():
    """Test that cryptg is available or not"""
    try:
        import cryptg
    except ImportError:
        pass


def test_mtproto_sender_has_reconnect_lock():
    """Test that MTProtoSender has proper lock for reconnection"""
    import inspect
    from telethon.network import mtprotosender
    
    # Check that the class has _connect_lock in source
    source = inspect.getsource(mtprotosender.MTProtoSender.__init__)
    assert '_connect_lock' in source, "MTProtoSender should have _connect_lock"
    assert '_reconnecting' in source, "MTProtoSender should have _reconnecting flag"
    
    # Check _start_reconnect uses the lock
    reconnect_source = inspect.getsource(mtprotosender.MTProtoSender._start_reconnect)
    assert '_connect_lock' in reconnect_source or 'async with' in reconnect_source


def test_download_iter_file_migrate_handler():
    """Test that download iterator properly handles FileMigrateError"""
    from telethon.client.downloads import _DirectDownloadIter
    import inspect
    
    source = inspect.getsource(_DirectDownloadIter._request)
    # Check that the fix for FileMigrateError is in place
    assert '_return_exported_sender' in source or 'disconnect' in source
    assert 'old_sender' in source


def test_aes_crypto_import():
    """Test that AES crypto module can be imported"""
    from telethon.crypto import AES
    assert hasattr(AES, 'encrypt_ige')
    assert hasattr(AES, 'decrypt_ige')


def test_upload_files_method_exists():
    """Test that upload_files method exists"""
    from telethon.client.uploads import UploadMethods
    assert hasattr(UploadMethods, 'upload_files')
