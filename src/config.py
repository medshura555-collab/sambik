from pathlib import Path
import time
import pandas as pd

# Пути к данным
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "raw" / "source.csv"
OUTPUT_PATH = Path(r"E:\laba_results\source_optimized.csv")

CHUNK_SIZE = 500_000

# Оптимизированная схема
DTYPES = {
    "key": "string",
    "fare_amount": "float32",
    "pickup_longitude": "float32",
    "pickup_latitude": "float32",
    "dropoff_longitude": "float32",
    "dropoff_latitude": "float32",
    "passenger_count": "Int8",
}

DATE_COLUMNS = ["pickup_datetime"]

def format_mb(size_bytes):
    return size_bytes / (1024 ** 2)

def read_chunks(optimized=False):
    options = {
        "chunksize": CHUNK_SIZE,
        "low_memory": True,
    }

    if optimized:
        options["dtype"] = DTYPES

    for chunk in pd.read_csv(DATA_PATH, **options):
        for column in DATE_COLUMNS:
            if column in chunk.columns:
                chunk[column] = pd.to_datetime(
                    chunk[column],
                    errors="coerce",
                    utc=True,
                )

        if optimized and "key" in chunk.columns:
            chunk["key"] = chunk["key"].astype("category")

        yield chunk

def measure_reading(optimized=False):
    """Измеряет время чтения всех порций исходного CSV."""
    start = time.perf_counter()
    total_rows = 0
    total_memory = 0
    category_columns = set()

    for chunk in read_chunks(optimized=optimized):
        total_rows += len(chunk)
        total_memory += chunk.memory_usage(
            index=False,
            deep=True,
        ).sum()

        for column in chunk.columns:
            if isinstance(chunk[column].dtype, pd.CategoricalDtype):
                category_columns.add(column)

    elapsed = time.perf_counter() - start

    return {
        "seconds": elapsed,
        "rows": total_rows,
        "memory_mb": format_mb(total_memory),
        "category_count": len(category_columns),
    }

def create_optimized_csv():
    """Создаёт оптимизированный CSV порциями."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if OUTPUT_PATH.exists():
        OUTPUT_PATH.unlink()

    first_chunk = True
    start = time.perf_counter()

    for chunk in read_chunks(optimized=True):
        # CSV не хранит типы pandas, поэтому category
        # будет записан как обычный текст.
        chunk.to_csv(
            OUTPUT_PATH,
            mode="w" if first_chunk else "a",
            header=first_chunk,
            index=False,
        )
        first_chunk = False

    return time.perf_counter() - start

def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Не найден файл: {DATA_PATH}")

    print("ШАГ 10. ДОПОЛНИТЕЛЬНЫЕ ИЗМЕРЕНИЯ")
    print(f"Исходный CSV: {DATA_PATH}")

    original_size = DATA_PATH.stat().st_size
    print(f"Размер исходного файла: {format_mb(original_size):.2f} МБ")

    print("\n1. Измерение чтения до оптимизации...")
    before = measure_reading(optimized=False)

    print(f"Строк прочитано: {before['rows']:,}")
    print(f"Время чтения до оптимизации: {before['seconds']:.2f} с")
    print(f"Объём в памяти до оптимизации: {before['memory_mb']:.2f} МБ")

    print("\n2. Измерение чтения с оптимизированными типами...")
    after = measure_reading(optimized=True)

    print(f"Строк прочитано: {after['rows']:,}")
    print(f"Время чтения после оптимизации: {after['seconds']:.2f} с")
    print(f"Объём в памяти после оптимизации: {after['memory_mb']:.2f} МБ")

    print("\n3. Создание оптимизированного CSV...")
    write_seconds = create_optimized_csv()

    optimized_size = OUTPUT_PATH.stat().st_size
    print(f"Файл создан: {OUTPUT_PATH}")
    print(f"Время создания файла: {write_seconds:.2f} с")
    print(f"Размер оптимизированного файла: {format_mb(optimized_size):.2f} МБ")

    size_change = (
        (optimized_size - original_size) / original_size * 100
        if original_size else 0
    )

    print("\n4. Итоговые значениядля таблицы")
    print(f"Размер файла до: {format_mb(original_size):.2f} МБ")
    print(f"Размер файла после: {format_mb(optimized_size):.2f} МБ")
    print(f"Изменение размера файла: {size_change:+.2f}%")
    print(f"Время чтения до: {before['seconds']:.2f} с")
    print(f"Время чтения после: {after['seconds']:.2f} с")
    print(f"Категориальных столбцов до: 0")
    print(f"Категориальных столбцов после чтения: {after['category_count']}")

    print("\nИзмерения завершены.")

if __name__ == "__main__":
    main()