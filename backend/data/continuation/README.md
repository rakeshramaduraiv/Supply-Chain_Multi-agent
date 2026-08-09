# backend/data/continuation/

## What this folder contains

Synthetic monthly CSV files continuing from the DataCo Supply Chain dataset.
DataCo ends **2018-01-31**. These files continue from **2018-02** onward.

All post-2018-01 data is **synthetic**. It is generated from the empirical
2017-08..2018-01 distribution of DataCo. The system has no code path that
treats these files differently from real uploads.

## Upload order

Upload one month at a time, in chronological order, via the **Data** stage:

```
2018-02 → 2018-03 → 2018-04 → ... → 2019-01
```

Do not skip months. The cycle service validates continuity.

## Declared drift schedule

| Period    | Drift type              | Magnitude | Affected entities                        |
|-----------|-------------------------|-----------|------------------------------------------|
| 2018-02   | none (baseline)         | —         | —                                        |
| 2018-03   | none (baseline)         | —         | —                                        |
| 2018-04   | supplier_degradation    | +0.18     | Fan Shop, Golf Shop (Department Name)    |
| 2018-05   | supplier_degradation    | +0.18     | Fan Shop, Golf Shop (Department Name)    |
| 2018-06   | none (decay/prune)      | —         | —                                        |
| 2018-07   | route_congestion        | +0.15     | First Class in Central America           |
| 2018-08   | route_congestion        | +0.15     | First Class in Central America           |
| 2018-09   | none (decay/prune)      | —         | —                                        |
| 2018-10   | demand_shift            | +0.20     | Cleats, Men's Footwear (Category Name)   |
| 2018-11   | demand_shift            | +0.20     | Cleats, Men's Footwear (Category Name)   |
| 2018-12   | seasonal_amplification  | +0.12     | All entities                             |
| 2019-01   | none (return baseline)  | —         | —                                        |

## Accuracy note

Accuracy measured against these files is **agreement with the generator**,
not real-world forecast accuracy. The generator uses a fixed seed per period
so files are reproducible. The model was trained on DataCo (2015-01..2018-01)
and has never seen these files.

## Regenerating

```bash
python tools/generate_continuation.py --verify
```

Frozen parameters (do not tune): theta=0.70, K=3, delta=0.05, theta_rem=0.10
