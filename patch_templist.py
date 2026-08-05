# -*- coding: utf-8 -*-
path = 'backend/app/api/v1/endpoints/dataset_summary.py'
with open(path, 'r', encoding='utf-8') as f:
    src = f.read()

# ── Patch 1: replace module-level cache vars with temperature list vars ──
old1 = """_cache: dict | None = None
_analytics_cache: dict | None = None


def clear_dataset_cache():
    \"\"\"Invalidate summary & analytics cache to reload real-time uploaded data.\"\"\"
    global _cache, _analytics_cache
    _cache = None
    _analytics_cache = None
    try:
        from app.api.v1.endpoints.live_ops import clear_live_ops_cache
        clear_live_ops_cache()
    except Exception:
        pass


def _load_parquet() -> pd.DataFrame | None:
    parquet_path = Path(settings.upload_dir) / \"processed_master.parquet\"
    if not parquet_path.exists():
        return None
    return pd.read_parquet(parquet_path)"""

new1 = """_cache: dict | None = None
_analytics_cache: dict | None = None

# ── Session-scoped temperature list ─────────────────────────────────────────
# Loaded once from the base DataCo parquet on first access.
# Uploaded CSVs are appended here in memory only — the base parquet is NEVER
# modified. Every backend restart rebuilds this from the base file alone.
_BASE_PARQUET_PATH: Path | None = None
_temp_df: pd.DataFrame | None = None   # base DataCo + any session uploads


def _get_base_parquet_path() -> Path:
    global _BASE_PARQUET_PATH
    if _BASE_PARQUET_PATH is None:
        _BASE_PARQUET_PATH = Path(settings.upload_dir) / "processed_master.parquet"
    return _BASE_PARQUET_PATH


def get_temp_df() -> pd.DataFrame | None:
    \"\"\"Return the session temperature DataFrame (base + session uploads).\"\"\"
    global _temp_df
    if _temp_df is None:
        base_path = _get_base_parquet_path()
        if base_path.exists():
            try:
                _temp_df = pd.read_parquet(base_path)
                logger.info(f"[TempList] Loaded base DataCo parquet: {len(_temp_df)} rows")
            except Exception as e:
                logger.warning(f"[TempList] Base parquet load failed: {e}")
                return None
        else:
            return None
    return _temp_df


def append_to_temp_df(df_new: pd.DataFrame) -> int:
    \"\"\"
    Append uploaded rows to the session temperature list.
    The base parquet on disk is never modified.
    Returns the new total row count.
    \"\"\"
    global _temp_df, _cache, _analytics_cache
    base = get_temp_df()
    if base is None:
        _temp_df = df_new.copy()
    else:
        _temp_df = pd.concat([base, df_new], ignore_index=True)
        if "Order Item Id" in _temp_df.columns:
            _temp_df = _temp_df.drop_duplicates(subset=["Order Item Id"], keep="last")
    _cache = None
    _analytics_cache = None
    logger.info(f"[TempList] Appended {len(df_new)} rows — session total: {len(_temp_df)}")
    return len(_temp_df)


def clear_dataset_cache():
    \"\"\"Invalidate summary & analytics cache (temperature list is kept).\"\"\"
    global _cache, _analytics_cache
    _cache = None
    _analytics_cache = None
    try:
        from app.api.v1.endpoints.live_ops import clear_live_ops_cache
        clear_live_ops_cache()
    except Exception:
        pass


def _load_parquet() -> pd.DataFrame | None:
    \"\"\"Return the session temperature DataFrame (base DataCo + session uploads).\"\"\"
    return get_temp_df()"""

assert old1 in src, "PATCH1 not found"
src = src.replace(old1, new1)

with open(path, 'w', encoding='utf-8') as f:
    f.write(src)

with open('_p.txt', 'w') as o:
    o.write('DONE\n')
