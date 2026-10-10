import pandas as pd

# Читаем исходную таблицу
df = pd.read_csv("data/raw/source.csv")

# Удаляем повторяющиеся строки
df = df.drop_duplicates()

# Сохраняем в CSV
df.to_csv(
    "data/processed/clean.csv",
    index=False,
    encoding="utf-8-sig"
)

# Сохраняем в Parquet
df.to_parquet(
    "data/interim/source.parquet",
    index=False
)

print("Данные сохранены в CSV и Parquet!")
print("Количество строк:", len(df))