from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Пути к файлам
source_path = Path("data/raw/source.csv")
output_path = Path("data/interim/source.parquet")

# Проверяем исходный файл
if not source_path.exists():
    raise FileNotFoundError(f"Файл не найден: {source_path}")

print(f"Исходный файл: {source_path}")
print(f"Размер файла: {source_path.stat().st_size / (1024**3):.2f} ГБ")

# Читаем первые 100 строк для изучения структуры
first_rows = pd.read_csv(source_path, nrows=100)

print("\nНазвания столбцов:")
print(first_rows.columns.tolist())

print("\nПервые 5 строк:")
print(first_rows.head())

print(f"\nПрочитано строк для изучения: {len(first_rows)}")

# Создаём папку для промежуточных данных
output_path.parent.mkdir(parents=True, exist_ok=True)

# Потоковое чтение и запись первых 200 000 строк
chunk_size = 50_000
target_rows = 200_000
total_rows = 0
writer = None

try:
    for chunk in pd.read_csv(source_path, chunksize=chunk_size):
        remaining = target_rows - total_rows
        if remaining <= 0:
            break

        chunk = chunk.head(remaining)

        table = pa.Table.from_pandas(chunk, preserve_index=False)

        if writer is None:
            writer = pq.ParquetWriter(output_path, table.schema)

        writer.write_table(table)
        total_rows += len(chunk)

        print(f"Обработано строк: {total_rows}")

        if total_rows >= target_rows:
            break
finally:
    if writer is not None:
        writer.close()

# Проверяем результат
if total_rows == 0:
    raise ValueError("В исходном файле нет строк для обработки.")

result = pd.read_parquet(output_path)

print(f"\nСрез сохранён: {output_path}")
print(f"Количество строк в срезе: {len(result)}")
print(f"Размер среза: {output_path.stat().st_size / (1024**2):.2f} МБ")
print("\nПервые 5 строк среза:")
print(result.head())