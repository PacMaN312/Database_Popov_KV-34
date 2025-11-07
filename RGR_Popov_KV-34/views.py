# views.py
from tabulate import tabulate
from typing import Any, List, Dict, Optional

def print_banner():
    print("="*70)
    print("Лабораторна робота — консольний інтерфейс для PostgreSQL (MVC)")
    print("="*70)

def show_menu():
    print("""
Меню:
1) Показати таблиці
2) Показати перші записи таблиці
3) Показати запис за PK
4) Додати запис
5) Редагувати запис
6) Видалити запис
7) Згенерувати дані SQL-на-сервері (generate_series)
8) Виконати складні запити (3 варіанти)
9) Перевірити наявність дітей перед видаленням (демо)
0) Вийти
""")

def print_tables(tables: List[str]):
    print("Таблиці (public):")
    for t in tables:
        print(" -", t)

def print_rows(rows: List[Dict[str, Any]], max_rows: int = 50):
    if not rows:
        print("Немає рядків для відображення.")
        return
    print(tabulate(rows[:max_rows], headers="keys", tablefmt="psql"))
    if len(rows) > max_rows:
        print(f"... показано {max_rows} з {len(rows)} рядків")

def print_row(row: Optional[Dict[str, Any]]):
    if not row:
        print("Запис не знайдено.")
        return
    for k, v in row.items():
        print(f"{k}: {v}")

def prompt(msg: str) -> str:
    return input(f"{msg}: ").strip()

def prompt_nullable(msg: str, default: Optional[str] = None) -> Optional[str]:
    s = input(f"{msg} [{default if default is not None else ''}]: ").strip()
    if s == "":
        return None
    return s

def show_message(msg: str):
    print(msg)

def show_error(msg: str):
    print("Помилка:", msg)

def show_success(msg: str):
    print("Успіх:", msg)

def show_query_result(rows, exec_time_ms, explain_text=None):
    print_rows(rows, max_rows=200)
    if exec_time_ms is not None:
        print(f"\nЧас виконання (EXPLAIN ANALYZE): {exec_time_ms} ms")
    else:
        print("\nЧас виконання: недоступний")
    # optional: show part of explain for debugging
    if explain_text:
        print("\n-- EXPLAIN ANALYZE (скорочено) --")
        expl_lines = explain_text.splitlines()
        print("\n".join(expl_lines[-8:]))
