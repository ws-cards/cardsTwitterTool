from services.paths import ensure_data_dirs, get_browser_profile_dir, get_data_root


def test_ensure_data_dirs(data_root):
    dirs = ensure_data_dirs()
    assert dirs["root"] == data_root.resolve()
    assert dirs["browser_profile"].is_dir()
    assert dirs["db"].is_dir()
    assert dirs["images"].is_dir()
    assert dirs["exports"].is_dir()
    assert get_data_root() == data_root.resolve()
    assert get_browser_profile_dir() == data_root.resolve() / "browser_profile"
