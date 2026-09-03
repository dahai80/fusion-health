# Data Sources

Fusion-Health bundles **sample** medical coding datasets so the API and CLI run
out-of-the-box without external downloads. These samples are NOT suitable for
clinical or billing use. Before any production deployment you must ingest
authoritative datasets using `scripts/ingest_data.py`.

## Current Status

| Dataset | File | Rows | Source | Status |
|---|---|---|---|---|
| ICD-10-CN | `fusion_health/data/icd10_cn/icd10_cn.tsv` | 30 | sample | demo only |
| ICD-9-CM-3 CN | `fusion_health/data/icd9cm3_cn/icd9cm3_cn.tsv` | 30 | sample | demo only |
| DRG (CN) | `fusion_health/data/drg/drg_cn.tsv` | 20 | sample | demo only |
| Insurance Catalog | `fusion_health/data/insurance_catalog.tsv` | 12 | sample | demo only |

The active state is recorded in `fusion_health/data/.data_source`:
- `sample` — bundled demo data (default)
- `full` — authoritative data ingested via `ingest_data.py`

Every validator response includes a `data_source` field (`sample` | `full`) so
downstream consumers can refuse to act on unvalidated sample data in production.

## Ingesting Authoritative Data

### 1. Obtain datasets

Acquire authoritative TSV files with the required columns below. Common
sources (China-specific):

| Dataset | Required columns | Key | Authoritative source |
|---|---|---|---|
| ICD-10-CN | `code`, `description`, `category` | `code` | 国家卫健委 ICD-10 临床版 |
| ICD-9-CM-3 CN | `code`, `description`, `category` | `code` | 国家卫健委手术操作分类 |
| DRG | `drg_code`, `drg_name`, `mdc`, `category` | `drg_code` | CHS-DRG 国家版 |
| Insurance Catalog | `code`, `name`, `category`, `level` | `code` | 国家医保药品/诊疗目录 |

Place each file (flat, by basename) in a source directory, e.g. `~/datasets/`:

```
~/datasets/
  icd10_cn.tsv
  icd9cm3_cn.tsv
  drg_cn.tsv
  insurance_catalog.tsv
```

### 2. Validate (dry-run)

```bash
python scripts/ingest_data.py --src ~/datasets --dry-run
```

Reports row counts, missing columns, and duplicate keys. Exits non-zero on
validation failure — no files are written.

### 3. Ingest

```bash
python scripts/ingest_data.py --src ~/datasets
```

- Backs up each existing sample file to `*.bak`
- Installs the authoritative file into `fusion_health/data/...`
- Writes `full` to `.data_source` marker only if **all** datasets validate

Ingest a single dataset:

```bash
python scripts/ingest_data.py --src ~/datasets --dataset icd10_cn
```

### 4. Verify

```bash
python scripts/ingest_data.py --status
```

Validators reload automatically (mtime-checked cache), so a running server
needs no restart.

## Rollback

```bash
cp fusion_health/data/icd10_cn/icd10_cn.tsv.bak fusion_health/data/icd10_cn/icd10_cn.tsv
echo -n sample > fusion_health/data/.data_source
```

## Production Gate

A production readiness check should assert `.data_source == full`. Sample data
must never reach a clinical or billing pipeline.
