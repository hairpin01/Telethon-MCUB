def test_downloads_module_imports():
    """Test that downloads module can be imported without errors"""
    from telethon.client import downloads
    assert hasattr(downloads, 'DownloadMethods')
    assert hasattr(downloads, '_DirectDownloadIter')
    assert hasattr(downloads, '_GenericDownloadIter')


def test_download_iter_has_file_migrate_handler():
    """Test that _DirectDownloadIter has proper method for handling FileMigrateError"""
    from telethon.client.downloads import _DirectDownloadIter
    assert hasattr(_DirectDownloadIter, '_request')
    import inspect
    source = inspect.getsource(_DirectDownloadIter._request)
    assert '_borrow_exported_sender' in source
    assert '_return_exported_sender' in source or 'disconnect' in source
