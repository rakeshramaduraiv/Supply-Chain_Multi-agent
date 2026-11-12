# Data Quality Report

| issue_id | category | column | severity | rows_affected | pct_affected | action_taken | verified |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DQ-05 | Value range | Order Profit Per Order | INFO | 77 | 38.5 | retained — genuine losses | True |
| DQ-07 | Identifier | Order Item Id | MEDIUM | 200 | 100.0 | Excluded from all model feature lists; retained for traceability | True |
| DQ-08 | Duplicates | (all columns) | PASSED | 0 | 0.0 | No action required | True |
| DQ-09a | Date integrity | order date (DateOrders) | PASSED | 0 | 0.0 | No action required | True |
| DQ-09b | Date integrity | order date (DateOrders) | PASSED | 0 | 0.0 | No action required | True |
| DQ-10 | Target integrity | Late_delivery_risk | PASSED | 0 | 0.0 | No action required | True |
| DQ-11 | Class balance | Late_delivery_risk | INFO | 88 | 44.0 | Supplier model uses class_weight='balanced'; no resampling applied | True |
