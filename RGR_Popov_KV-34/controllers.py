# controllers.py
from models import DBModel
import views
from typing import Dict, Any

class Controller:
    def __init__(self):
        self.model = DBModel()
        self.tables = ["Student", "Professor", "Course", "Task", "Registration"]

    def close(self):
        self.model.close()

    def run(self):
        views.print_banner()
        while True:
            views.show_menu()
            choice = views.prompt("Виберіть опцію")
            if choice == "1":
                self.action_list_tables()
            elif choice == "2":
                self.action_show_table()
            elif choice == "3":
                self.action_show_by_pk()
            elif choice == "4":
                self.action_insert()
            elif choice == "5":
                self.action_update()
            elif choice == "6":
                self.action_delete()
            elif choice == "7":
                self.action_generate()
            elif choice == "8":
                self.action_complex_queries()
            elif choice == "9":
                self.action_demo_check_children()
            elif choice == "0":
                print("До побачення!")
                break
            else:
                print("Невірний вибір. Спробуйте ще.")

    def action_list_tables(self):
        try:
            tables = self.model.list_tables()
            views.print_tables(tables)
        except Exception as e:
            views.show_error(str(e))

    def action_show_table(self):
        table = views.prompt("Назва таблиці")
        if table not in self.tables:
            views.show_error("Невідома таблиця. Приклад: Student")
            return
        try:
            rows = self.model.select_all(table, limit=500)
            views.print_rows(rows)
        except Exception as e:
            views.show_error("Не вдалося отримати записи.")

    def action_show_by_pk(self):
        table = views.prompt("Назва таблиці")
        if table not in self.tables:
            views.show_error("Невідома таблиця")
            return
        pk = self.model.primary_key(table)
        if not pk:
            views.show_error("PK не знайдено для таблиці")
            return
        val = views.prompt(f"Значення PK ({pk})")
        # простий парсинг типу (використовуємо schema info)
        cols = self.model.columns_info(table)
        col_info = next((c for c in cols if c['name'] == pk), None)
        if col_info and 'integer' in col_info['type']:
            try:
                val = int(val)
            except Exception:
                views.show_error("PK має бути числом")
                return
        try:
            row = self.model.select_by_pk(table, pk, val)
            views.print_row(row)
        except Exception:
            views.show_error("Помилка при отриманні запису")

    def _input_and_validate_for_table(self, table: str, skip_pk: bool = True) -> Dict[str, Any]:
        """
        Попросити користувача ввести значення для стовпців таблиці з валідацією типів.
        Якщо skip_pk=True — пропускаємо PK (часто serial).
        Повертаємо dict {col: value}
        """
        cols = self.model.columns_info(table)
        pk = self.model.primary_key(table)
        data = {}
        for c in cols:
            name = c['name']
            dtype = c['type']
            if skip_pk and name == pk:
                continue
            prompt_msg = f"{name} ({dtype})"
            raw = views.prompt_nullable(prompt_msg)
            if raw is None:
                if not c['nullable']:
                    # примусимо ввести значення
                    views.show_message(f"Поле {name} не може бути порожнім.")
                    return self._input_and_validate_for_table(table, skip_pk)
                else:
                    data[name] = None
                    continue
            # валідація типів за базовими правилами
            if 'integer' in dtype or dtype in ('smallint','bigint'):
                try:
                    data[name] = int(raw)
                except Exception:
                    views.show_error(f"Невірний формат для {name}: очікується ціле число")
                    return self._input_and_validate_for_table(table, skip_pk)
            elif dtype in ('real', 'double precision', 'numeric', 'decimal'):
                try:
                    data[name] = float(raw)
                except Exception:
                    views.show_error(f"Невірний формат для {name}: очікується число")
                    return self._input_and_validate_for_table(table, skip_pk)
            elif dtype == 'date':
                parsed = self.model.parse_date(raw)
                if parsed is None:
                    views.show_error(f"Невірний формат дати для {name}. Використайте YYYY-MM-DD")
                    return self._input_and_validate_for_table(table, skip_pk)
                data[name] = parsed
            else:
                # рядки, текст, timestamps — зберігаємо як є
                data[name] = raw
        return data

    def action_insert(self):
        table = views.prompt("Назва таблиці для вставки")
        if table not in self.tables:
            views.show_error("Невідома таблиця")
            return
        # Для дочірньої таблиці переконатися, що батьківська існує (якщо потрібно)
        data = self._input_and_validate_for_table(table, skip_pk=True)
        # Якщо таблиця - Registration або Task — перевіряємо існування FK-рядків
        if table == "Task":
            # перевірити, що Course_ID існує
            cid = data.get("Course_ID")
            if cid is None or not self.model.parent_exists("Course", "Course_ID", cid):
                views.show_error("Вказаний Course_ID не знайдено в Course")
                return
        if table == "Registration":
            # Course_ID, Professor_ID, Student_ID повинні існувати
            ok = True
            for parent_table, col in [("Course","Course_ID"), ("Professor","Professor_ID"), ("Student","Student_ID")]:
                val = data.get(col)
                if val is None or not self.model.parent_exists(parent_table, col, val):
                    views.show_error(f"Вказаний {col} ({val}) не знайдено у таблиці {parent_table}")
                    ok = False
            if not ok:
                return
        # Виконати вставку
        success, err = self.model.insert(table, data)
        if success:
            views.show_success("Запис додано успішно.")
        else:
            # адекватна обробка помилок (FK, PK)
            views.show_error(f"Не вдалося додати запис: {err}")

    def action_update(self):
        table = views.prompt("Назва таблиці для оновлення")
        if table not in self.tables:
            views.show_error("Невідома таблиця")
            return
        pk = self.model.primary_key(table)
        if not pk:
            views.show_error("Не знайдено PK для цієї таблиці")
            return
        pk_val_raw = views.prompt(f"Значення PK ({pk}) рядка для редагування")
        # перевіримо тип PK
        cols = self.model.columns_info(table)
        pk_col = next((c for c in cols if c['name'] == pk), None)
        if pk_col and 'integer' in pk_col['type']:
            try:
                pk_val = int(pk_val_raw)
            except Exception:
                views.show_error("PK має бути числом")
                return
        else:
            pk_val = pk_val_raw
        row = self.model.select_by_pk(table, pk, pk_val)
        if not row:
            views.show_error("Рядок не знайдено")
            return
        # Показати і попросити нові значення (порожнє — залишити)
        views.show_message("Введіть нові значення. Порожній ввод — залишити поточне значення.")
        cols_info = self.model.columns_info(table)
        updates = {}
        for c in cols_info:
            name = c['name']
            if name == pk:
                continue
            cur = row.get(name)
            raw = views.prompt_nullable(f"{name} (поточне: {cur})")
            if raw is None:
                continue
            # валідація як при вставці
            dtype = c['type']
            if 'integer' in dtype:
                try:
                    updates[name] = int(raw)
                except Exception:
                    views.show_error(f"Невірний формат для {name}. Очікується integer.")
                    return
            elif dtype in ('real','double precision','numeric','decimal'):
                try:
                    updates[name] = float(raw)
                except Exception:
                    views.show_error(f"Невірний формат для {name}. Очікується число.")
                    return
            elif dtype == 'date':
                parsed = self.model.parse_date(raw)
                if parsed is None:
                    views.show_error("Невірний формат дати.")
                    return
                updates[name] = parsed
            else:
                updates[name] = raw
        if not updates:
            views.show_message("Нічого не змінилося.")
            return
        # Якщо це дочірня таблиця — перевіримо батьків на існування при зміні FK
        if table == "Task" and "Course_ID" in updates:
            if not self.model.parent_exists("Course", "Course_ID", updates["Course_ID"]):
                views.show_error("Вказаний Course_ID не знайдено.")
                return
        if table == "Registration":
            for parent_col, parent_table in [("Course_ID","Course"), ("Professor_ID","Professor"), ("Student_ID","Student")]:
                if parent_col in updates:
                    if not self.model.parent_exists(parent_table, parent_col, updates[parent_col]):
                        views.show_error(f"Вказаний {parent_col} не знайдено у {parent_table}")
                        return
        success, err = self.model.update(table, pk, pk_val, updates)
        if success:
            views.show_success("Запис оновлено.")
        else:
            views.show_error(f"Не вдалося оновити: {err}")

    def action_delete(self):
        table = views.prompt("Назва таблиці для видалення рядка")
        if table not in self.tables:
            views.show_error("Невідома таблиця")
            return
        pk = self.model.primary_key(table)
        if not pk:
            views.show_error("PK не знайдено")
            return
        pk_val_raw = views.prompt(f"Значення PK ({pk}) для видалення")
        # парсимо pk тип
        pk_col = next((c for c in self.model.columns_info(table) if c['name']==pk), None)
        if pk_col and 'integer' in pk_col['type']:
            try:
                pk_val = int(pk_val_raw)
            except Exception:
                views.show_error("PK має бути числом")
                return
        else:
            pk_val = pk_val_raw
        # Перевірка на наявність дочірніх рядків
        try:
            if self.model.has_child_rows(table, pk, pk_val):
                views.show_error("Не можна видалити: існують рядки у підлеглих таблицях, що посилаються на цей запис.")
                return
        except Exception as e:
            views.show_error("Не вдалося перевірити залежності.")
            return
        confirm = views.prompt("Підтвердіть видалення (так/ні)").lower()
        if confirm not in ('так','yes','y','t'):
            views.show_message("Видалення скасовано")
            return
        success, err = self.model.delete(table, pk, pk_val)
        if success:
            views.show_success("Запис видалено.")
        else:
            views.show_error(f"Не вдалося видалити: {err}")

    def action_generate(self):
        """
        Запускає SQL-генерацію великої кількості рядків на сервері.
        Користувач вводить кількість.
        Генеруємо батьківські таблиці перед дочірніми.
        """
        count_raw = views.prompt("Скільки записів згенерувати для кожної таблиці (наприклад 100000)?")
        try:
            count = int(count_raw)
            if count <= 0:
                raise ValueError
        except Exception:
            views.show_error("Введіть позитивне ціле число")
            return
        views.show_message(f"Генеруємо {count} записів...")
        # Рекомендовано: генерувати в порядку батьки -> діти:
        tasks = [
            ("Student", self.model.generate_students),
            ("Professor", self.model.generate_professors),
            ("Course", self.model.generate_courses),
            # tasks and registrations require courses/prof/students to exist
            ("Task", self.model.generate_tasks),
            ("Registration", self.model.generate_registrations),
        ]
        for name, func in tasks:
            success, err = func(count)
            if success:
                views.show_success(f"{name}: згенеровано (або додано) {count} рядків (якщо можливо).")
            else:
                # для дочірніх таблиць може бути помилка коли немає батьків — відобразимо дружнє повідомлення
                views.show_error(f"{name}: не вдалося згенерувати: {err}")

    def action_complex_queries(self):
        views.show_message("1) Завдання студентів за іменем (JOIN, GROUP BY)")
        views.show_message("2) Кількість курсів на професора (GROUP BY, WHERE)")
        views.show_message("3) Кількість реєстрацій по курсах за період (BETWEEN)")
        choice = views.prompt("Який запит виконати (1/2/3)?")
        if choice == "1":
            pat = views.prompt("Введіть частину імені студента для фільтра (LIKE)")
            rows, time_ms, explain, err = self.model.query_student_tasks_by_name(pat)
            if err:
                views.show_error(f"Помилка виконання: {err}")
                return
            views.show_query_result(rows, time_ms, explain)
        elif choice == "2":
            exp_raw = views.prompt("Мінімальний досвід (ціле число)")
            try:
                exp = int(exp_raw)
            except Exception:
                views.show_error("Потрібно ціле число")
                return
            rows, time_ms, explain, err = self.model.query_professor_course_counts(exp)
            if err:
                views.show_error(f"Помилка виконання: {err}")
                return
            views.show_query_result(rows, time_ms, explain)
        elif choice == "3":
            start = views.prompt("Початкова дата (YYYY-MM-DD)")
            end = views.prompt("Кінцева дата (YYYY-MM-DD)")
            start_p = self.model.parse_date(start)
            end_p = self.model.parse_date(end)
            if not start_p or not end_p:
                views.show_error("Невірний формат дати")
                return
            rows, time_ms, explain, err = self.model.query_course_regs_in_period(start_p, end_p)
            if err:
                views.show_error(f"Помилка виконання: {err}")
                return
            views.show_query_result(rows, time_ms, explain)
        else:
            views.show_error("Невірний вибір")

    def action_demo_check_children(self):
        # Проста демонстрація перевірки перед видаленням
        table = views.prompt("Назва батьківської таблиці (наприклад Course)")
        pk = self.model.primary_key(table)
        if not pk:
            views.show_error("PK не знайдено")
            return
        val_raw = views.prompt(f"Значення PK ({pk}) для перевірки")
        pk_col = next((c for c in self.model.columns_info(table) if c['name'] == pk), None)
        if pk_col and 'integer' in pk_col['type']:
            try:
                val = int(val_raw)
            except Exception:
                views.show_error("PK має бути числом")
                return
        else:
            val = val_raw
        try:
            has_children = self.model.has_child_rows(table, pk, val)
        except Exception:
            views.show_error("Не вдалося перевірити залежності")
            return
        if has_children:
            views.show_message("Існують рядки в підлеглих таблицях, що посилаються на цей запис.")
        else:
            views.show_message("Підлеглих рядків не знайдено. Видалення дозволено (якщо потрібно).")
