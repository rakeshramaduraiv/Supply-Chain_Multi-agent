# -*- coding: utf-8 -*-
path = 'backend/app/services/enterprise_learning_engine.py'
with open(path, 'r', encoding='utf-8') as f:
    src = f.read()

# Replace Stage 8 block that writes to parquet with temp list append
old8 = """        # ── Stage 8: Historical Dataset Expansion (2015-2018 -> 2015-Jan 2019 v2) ────────────
        t0 = time.perf_counter()
        if not df_old.empty:
            df_expanded = pd.concat([df_old, df_new], ignore_index=True)
            if \"Order Item Id\" in df_expanded.columns:
                df_expanded = df_expanded.drop_duplicates(subset=[\"Order Item Id\"], keep=\"last\")
        else:
            df_expanded = df_new

        cumulative_rows = len(df_expanded)
        df_features = self._feature_pipeline.transform(df_expanded)

        # Sanitize object columns to string for PyArrow serialization compatibility
        for col in df_features.select_dtypes(include=[\"object\"]).columns:
            df_features[col] = df_features[col].astype(str)

        self.master_parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df_features.to_parquet(self.master_parquet_path, index=False)
        clear_dataset_cache()

        new_version_tag = f\"2015-{period}_v2\""""

new8 = """        # ── Stage 8: Session Temperature List Expansion ────────────────────────────────────
        # Appends uploaded rows to the in-memory temperature list only.
        # The base DataCo parquet on disk is NEVER modified.
        # Every backend restart rebuilds the temperature list from the base file alone.
        t0 = time.perf_counter()
        from app.api.v1.endpoints.dataset_summary import append_to_temp_df
        df_features = self._feature_pipeline.transform(df_new)
        for col in df_features.select_dtypes(include=["object"]).columns:
            df_features[col] = df_features[col].astype(str)
        cumulative_rows = append_to_temp_df(df_features)

        new_version_tag = f"2015-{period}_v2\""""

assert old8 in src, "PATCH8 not found"
src = src.replace(old8, new8)

with open(path, 'w', encoding='utf-8') as f:
    f.write(src)

with open('_p.txt', 'w') as o:
    o.write('DONE\n')
