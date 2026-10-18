from pathlib import Path
import argparse
import logging
import json
import hashlib

import duckdb
import pandas as pd

BASE_DIR = Path(r"E:\laba_results")
DEFAULT_SOURCE = BASE_DIR / "clean_final.parquet"
DEFAULT_OUTPUT = BASE_DIR / "step13_result.parquet"
DEFAULT_LOG = BASE_DIR / "step13_pipeline.log"

MEMORY_LIMIT = "3GB"
THREADS = 2

def setup_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_path),
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        encoding="utf-8",
        force=True,
    )

def connect_duckdb():
    con = duckdb.connect()
    con.execute(f"SET memory_limit = '{MEMORY_LIMIT}'")
    con.execute(f"SET threads = {THREADS}")
    con.execute("SET preserve_insertion_order = false")
    return con

def validate_source(source_path: Path) -> dict:
    if not source_path.is_file():
        raise FileNotFoundError(
            f"Исходный файл не найден: {source_path}"
        )

    if source_path.suffix.lower() != ".parquet":
        raise ValueError("Ожидается файл формата Parquet.")

    con = connect_duckdb()
    try:
        source = source_path.resolve().as_posix().replace("'", "''")
        rows = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{source}')"
        ).fetchone()[0]

        columns = con.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{source}')"
        ).fetchdf()["column_name"].tolist()

        return {
            "rows_before": int(rows),
            "rows_after": int(rows),
            "columns": columns,
            "changed": 0,
        }
    except duckdb.Error as exc:
        raise ValueError(
            f"Не удалось прочитать Parquet: {exc}"
        ) from exc
    finally:
        con.close()

def clean_data(
    source_path: Path,
    output_path: Path,
    mode: str = "full",
    limit: int = 1000,
) -> dict:
    """
    Преобразует дату, удаляет полные дубликаты
    и сохраняет итоговый Parquet.
    """
    if mode not in {"full", "debug"}:
        raise ValueError("mode должен быть full или debug.")

    if limit < 1:
        raise ValueError("limit должен быть больше нуля.")

    source_info = validate_source(source_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    source = source_path.resolve().as_posix().replace("'", "''")
    output = output_path.resolve().as_posix().replace("'", "''")

    con = connect_duckdb()
    try:
        columns = source_info["columns"]
        datetime_exists = "pickup_datetime" in columns

        if mode == "debug":
            base_query = (
                f"SELECT * FROM read_parquet('{source}') "
                f"LIMIT {int(limit)}"
            )
        else:
            base_query = f"SELECT * FROM read_parquet('{source}')"

        if datetime_exists:
            query = f"""
                SELECT * REPLACE (
                    TRY_CAST(pickup_datetime AS TIMESTAMP)
                    AS pickup_datetime
                )
                FROM ({base_query}) AS input_data
            """
        else:
            query = base_query

        before = con.execute(
            f"SELECT COUNT(*) FROM ({query}) AS q"
        ).fetchone()[0]

        temp_output = output_path.with_name(
            output_path.stem + "_temp.parquet"
        )
        temp = temp_output.resolve().as_posix().replace("'", "''")

        con.execute(f"""
            COPY (
                SELECT DISTINCT *
                FROM ({query}) AS prepared_data
            )
            TO '{temp}'
            (FORMAT PARQUET, COMPRESSION SNAPPY)
        """)

        after = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{temp}')"
        ).fetchone()[0]

        # Заменяем итоговый файл только после успешной записи.
        temp_output.replace(output_path)

        result = {
            "stage": "clean_data",
            "rows_before": int(before),
            "rows_after": int(after),
            "changed": int(before - after),
            "output": str(output_path),
            "mode": mode,
        }

        logging.info("Очистка: %s", json.dumps(result, ensure_ascii=False))
        return result
    except duckdb.Error as exc:
        raise ValueError(
            f"Ошибка обработки данных DuckDB: {exc}"
        ) from exc
    finally:
        con.close()

def analyze_missing(source_path: Path, report_path: Path) -> pd.DataFrame:
    """Подсчитывает пропуски по каждому столбцу."""
    info = validate_source(source_path)
    source = source_path.resolve().as_posix().replace("'", "''")
    report_path.parent.mkdir(parents=True, exist_ok=True)

    con = connect_duckdb()
    try:
        rows = info["rows_before"]
        results = []

        for column in info["columns"]:
            col = '"' + column.replace('"', '""') + '"'
            missing = con.execute(f"""
                SELECT COUNT(*) - COUNT({col})
                FROM read_parquet('{source}')
            """).fetchone()[0]

            results.append({
                "столбец": column,
                "пропусков": int(missing),
                "доля_пропусков_процентов": (
                    round(100 * missing / rows, 4) if rows else 0
                ),
            })

        df = pd.DataFrame(results)
        df.to_csv(report_path, index=False, encoding="utf-8-sig")
        logging.info("Сохранён анализ пропусков: %s", report_path)
        return df
    finally:
        con.close()

def analyze_outliers(
    source_path: Path,
    report_path: Path,
) -> pd.DataFrame:
    """Обнаруживает выбросы fare_amount методами IQR и Z-score."""
    info = validate_source(source_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    if "fare_amount" not in info["columns"]:
        raise ValueError("В файле отсутствует столбец fare_amount.")

    source = source_path.resolve().as_posix().replace("'", "''")
    con = connect_duckdb()

    try:
        q1, q3, mean_value, std_value = con.execute(f"""
            SELECT
                QUANTILE_CONT(fare_amount, 0.25),
                QUANTILE_CONT(fare_amount, 0.75),
                AVG(fare_amount),
                STDDEV_POP(fare_amount)
            FROM read_parquet('{source}')
            WHERE fare_amount IS NOT NULL
        """).fetchone()

        iqr_count = 0
        z_count = 0

        if q1 is not None and q3 is not None:
            iqr = q3 - q1
            low = q1 - 1.5 * iqr
            high = q3 + 1.5 * iqr
            iqr_count = con.execute(f"""
                SELECT COUNT(*)
                FROM read_parquet('{source}')
                WHERE fare_amount < {low}
                   OR fare_amount > {high}
            """).fetchone()[0]

        if mean_value is not None and std_value not in (None, 0):
            z_count = con.execute(f"""
                SELECT COUNT(*)
                FROM read_parquet('{source}')
                WHERE ABS((fare_amount - {mean_value}) / {std_value}) > 3
            """).fetchone()[0]

        df = pd.DataFrame([
            {
                "столбец": "fare_amount",
                "метод": "IQR",
                "обнаружено_выбросов": int(iqr_count),
            },
            {
                "столбец": "fare_amount",
                "метод": "Z-score",
                "обнаружено_выбросов": int(z_count),
            },
        ])

        df.to_csv(report_path, index=False, encoding="utf-8-sig")
        logging.info("Сохранён анализ выбросов: %s", report_path)
        return df
    finally:
        con.close()

def file_sha256(path: Path) -> str:
    """Вычисляет контрольную сумму файла блоками."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def run_pipeline(
    source_path: Path,
    output_path: Path,
    mode: str = "full",
    limit: int = 1000,
    stage: str = "all",
) -> dict:
    if stage == "validate":
        return validate_source(source_path)

    if stage == "clean":
        return clean_data(source_path, output_path, mode, limit)

    if stage == "missing":
        report = output_path.with_name("step13_missing_analysis.csv")
        df = analyze_missing(source_path, report)
        return {"stage": stage, "columns_analyzed": len(df), "report": str(report)}

    if stage == "outliers":
        report = output_path.with_name("step13_outliers.csv")
        df = analyze_outliers(source_path, report)
        return {"stage": stage, "methods": len(df), "report": str(report)}

    if stage != "all":
        raise ValueError("Неизвестный этап.")

    cleaned = clean_data(source_path, output_path, mode, limit)
    missing = analyze_missing(
        output_path,
        output_path.with_name("step13_missing_analysis.csv"),
    )
    outliers = analyze_outliers(
        output_path,
        output_path.with_name("step13_outliers.csv"),
    )

    return {
        "cleaning": cleaned,
        "missing_columns_analyzed": len(missing),
        "outlier_methods": len(outliers),
        "output_sha256": file_sha256(output_path),
    }

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Конвейер обработки Parquet"
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--mode", choices=["full", "debug"], default="full"
    )
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument(
        "--stage",
        choices=["all", "validate", "clean", "missing", "outliers"],
        default="all",
    )
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    args = parser.parse_args()

    setup_logging(args.log)

    try:
        result = run_pipeline(
            args.source, args.output, args.mode, args.limit, args.stage
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    except (FileNotFoundError, ValueError, OSError) as exc:
        logging.exception("Ошибка конвейера")
        print(f"Ошибка: {exc}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())