# Розрахунково-графічна робота (РГР)
## Тема: Консольний застосунок для роботи з базою даних PostgreSQL (шаблон MVC)

###  Опис проєкту
Цей проєкт реалізує консольний застосунок на мові **Python** для взаємодії з базою даних **PostgreSQL**, створеною у **pgAdmin 4**.  
Програма побудована за архітектурним шаблоном **MVC (Model-View-Controller)**, що забезпечує чітке розділення логіки роботи з даними, відображення та управління користувацькими діями.

---

###  Структура проєкту
```
 RGR_Popov_KV-34
 ┣  main.py           # Точка входу в програму
 ┣  controllers.py    # Контролер — логіка взаємодії з користувачем
 ┣  models.py         # Модель — робота з базою даних
 ┣  view.py           # Представлення — консольний інтерфейс
 ┣  config.py         # Параметри підключення до PostgreSQL
 ┗  README.md         # Документація проєкту
```

---

###  Архітектура MVC

- **Model** (`models.py`) — логіка доступу до БД, SQL-запити, генерація, CRUD.  
- **View** (`view.py`) — відповідає за відображення інформації в консолі.  
- **Controller** (`controllers.py`) — координує взаємодію користувача та моделі.  
- **Config** (`config.py`) — містить параметри підключення до бази даних.  
- **Main** (`main.py`) — головний файл запуску програми.

---

###  Фрагменти коду

####  Фрагмент програми внесення даних (`controllers.py`)
```python
def action_insert(self):
    table = input("Назва таблиці для вставки: ").strip()
    cols = self.model.get_columns(table)
    values = {}
    for col, dtype in cols.items():
        if col == self.model.primary_key(table):
            continue
        val = input(f"{col} ({dtype}) []: ")
        values[col] = val if val else None
    try:
        self.model.insert(table, values)
        print(" Запис успішно додано!")
    except Exception as e:
        print(f"Помилка: Не вдалося додати запис: {e}")
```

####  Фрагмент програми редагування даних
```python
def action_update(self):
    table = input("Назва таблиці для оновлення: ").strip()
    pk = self.model.primary_key(table)
    pk_val = input(f"Введіть значення {pk}: ")
    updates = {}
    cols = self.model.get_columns(table)
    for col, dtype in cols.items():
        if col == pk:
            continue
        val = input(f"Нове значення для {col} ({dtype}) []: ")
        if val:
            updates[col] = val
    try:
        self.model.update(table, pk, pk_val, updates)
        print("Дані оновлено успішно.")
    except Exception as e:
        print(f"Помилка: Не вдалося оновити дані: {e}")
```

####  Фрагмент програми видалення даних
```python
def action_delete(self):
    table = input("Назва таблиці для видалення рядка: ").strip()
    pk = self.model.primary_key(table)
    pk_val = input(f"Значення PK ({pk}) для видалення: ")
    try:
        if self.model.has_dependencies(table, pk, pk_val):
            print(" Не можна видалити: існують рядки у підлеглих таблицях.")
            return
        self.model.delete(table, pk, pk_val)
        print(" Рядок успішно видалено.")
    except Exception as e:
        print(f"Помилка: Не вдалося видалити рядок: {e}")
```

####  Фрагмент програми генерації випадкових даних (`models.py`)
```python
def generate_students(self, n):
    cur = self.conn.cursor()
    try:
        q = f"""
        INSERT INTO "Student"("Student_ID","Student_Name","Group")
        SELECT s, name, grp FROM (
            SELECT
                COALESCE(MAX("Student_ID"), 0) + seq AS s,
                (ARRAY['Дмитро Мельник','Олег Шевченко','Катерина Коваленко','Ірина Савчук','Максим Попов'])[floor(random()*5)+1] AS name,
                floor(random()*100)+1 AS grp
            FROM generate_series(1, {n}) AS seq
        ) t;
        """
        cur.execute(q)
        self.conn.commit()
        print(f"Згенеровано {n} студентів.")
    except Exception as e:
        print(f"Помилка: Student: не вдалося згенерувати: {e}")
        self.conn.rollback()
```

---

###  Як запустити

1. Установіть залежності:
   ```bash
   pip install psycopg2 tabulate python-dateutil faker
   ```
2. Налаштуйте `config.py` з вашими параметрами PostgreSQL.
3. Запустіть програму:
   ```bash
   python main.py
   ```

---

###  Висновок

У результаті виконання розрахунково-графічної роботи було створено повноцінний консольний застосунок для роботи з базою даних **PostgreSQL**.  
Програма реалізує всі необхідні функції — перегляд, внесення, редагування, видалення та автоматичну генерацію даних, а також забезпечує перевірку зв’язків між таблицями та коректну обробку помилок.  
Архітектурний підхід **MVC** дозволив створити зручну, структуровану та масштабовану систему.

---

###  Автор
**Попов Єгор**, група **КВ-34**  
Розрахунково-графічна робота з дисципліни **"Бази даних"**
