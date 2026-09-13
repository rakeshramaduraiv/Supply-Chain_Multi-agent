import pandas as pd

files = {
    "2_preprocessed_full":       "data/stages/2_preprocessed_full.csv",
    "2_fe_inputs":               "data/stages/2_fe_inputs.csv",
    "3_all_features_combined":   "data/stages/feature_groups/3_all_features_combined.csv",
    "3a_temporal":               "data/stages/feature_groups/3a_temporal.csv",
    "3b_demand_rolling":         "data/stages/feature_groups/3b_demand_rolling.csv",
    "3c_inventory":              "data/stages/feature_groups/3c_inventory.csv",
    "3d_supplier":               "data/stages/feature_groups/3d_supplier.csv",
    "3e_logistics":              "data/stages/feature_groups/3e_logistics.csv",
    "3f_post_shipment":          "data/stages/feature_groups/3f_post_shipment.csv",
    "3g_graph_context":          "data/stages/feature_groups/3g_graph_context.csv",
    "3h_aliases":                "data/stages/feature_groups/3h_aliases.csv",
}

for name, path in files.items():
    df = pd.read_csv(path)
    print(f"{name}: {len(df):,} rows x {len(df.columns)} cols | {list(df.columns)}")
