# models.py
from typing import Tuple, List, Dict, Any, Optional
import psycopg2
import psycopg2.extras
from psycopg2 import sql
from config import DB
from dateutil import parser as date_parser
import random

class DBModel:
    def __init__(self):
        try:
            self.conn = psycopg2.connect(**DB)
            self.conn.autocommit = True
        except Exception as e:
            # Не виводимо сирий traceback — кидаємо зрозуміле повідомлення
            raise RuntimeError("Не вдалося підключитися до бази даних. Перевірте налаштування в config.py") from e

    def close(self):
        self.conn.close()

    # --- Інспекція схеми (корисно для View/Controller) ---
    def list_tables(self) -> List[str]:
        q = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema='public' AND table_type='BASE TABLE'
        ORDER BY table_name;
        """
        with self.conn.cursor() as cur:
            cur.execute(q)
            return [r[0] for r in cur.fetchall()]

    def columns_info(self, table: str) -> List[Dict[str, Any]]:
        q = """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position;
        """
        with self.conn.cursor() as cur:
            cur.execute(q, (table,))
            res = []
            for r in cur.fetchall():
                res.append({"name": r[0], "type": r[1], "nullable": (r[2] == 'YES')})
            return res

    def primary_key(self, table: str) -> Optional[str]:
        q = """
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        WHERE i.indrelid = quote_ident(%s)::regclass AND i.indisprimary;
        """
        with self.conn.cursor() as cur:
            cur.execute(q, (table,))
            row = cur.fetchone()
            return row[0] if row else None

    # --- Generic CRUD (всі назви таблиць/стовпців як Identifier) ---
    def select_all(self, table: str, limit: int = 200) -> List[Dict[str, Any]]:
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql.SQL('SELECT * FROM {} ORDER BY 1 LIMIT %s').format(sql.Identifier(table)), (limit,))
            return cur.fetchall()

    def select_by_pk(self, table: str, pk: str, pk_value: Any) -> Optional[Dict[str, Any]]:
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql.SQL('SELECT * FROM {} WHERE {}=%s').format(sql.Identifier(table), sql.Identifier(pk)), (pk_value,))
            return cur.fetchone()

    def insert(self, table: str, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        cols = list(data.keys())
        vals = [data[c] for c in cols]
        query = sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(
            sql.Identifier(table),
            sql.SQL(', ').join(map(sql.Identifier, cols)),
            sql.SQL(', ').join(sql.Placeholder() * len(cols))
        )
        with self.conn.cursor() as cur:
            try:
                cur.execute(query, vals)
                return True, None
            except psycopg2.Error as e:
                return False, e.pgerror or str(e)

    def update(self, table: str, pk: str, pk_value: Any, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        cols = list(data.keys())
        vals = [data[c] for c in cols] + [pk_value]
        set_clause = sql.SQL(', ').join(
            sql.Composed([sql.Identifier(c), sql.SQL(' = '), sql.Placeholder()]) for c in cols
        )
        query = sql.SQL('UPDATE {} SET {} WHERE {} = %s').format(
            sql.Identifier(table),
            set_clause,
            sql.Identifier(pk)
        )
        with self.conn.cursor() as cur:
            try:
                cur.execute(query, vals)
                return True, None
            except psycopg2.Error as e:
                return False, e.pgerror or str(e)

    def delete(self, table: str, pk: str, pk_value: Any) -> Tuple[bool, Optional[str]]:
        query = sql.SQL('DELETE FROM {} WHERE {} = %s').format(sql.Identifier(table), sql.Identifier(pk))
        with self.conn.cursor() as cur:
            try:
                cur.execute(query, (pk_value,))
                return True, None
            except psycopg2.Error as e:
                return False, e.pgerror or str(e)

    # --- Helpers щодо FK контролю ---
    def has_child_rows(self, parent_table: str, parent_pk: str, pk_value: Any) -> bool:
        """
        Перевірити, чи існують рядки в інших таблицях, що посилаються на даний батьківський PK.
        Шукаємо у information_schema.constraint_column_usage / key_column_usage.
        """
        q = """
        SELECT c.table_name, kcu.column_name
        FROM information_schema.table_constraints c
        JOIN information_schema.key_column_usage kcu
          ON c.constraint_name = kcu.constraint_name AND c.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON c.constraint_name = ccu.constraint_name AND c.table_schema = ccu.constraint_schema
        WHERE c.constraint_type = 'FOREIGN KEY' AND ccu.table_name = %s AND ccu.column_name = %s;
        """
        with self.conn.cursor() as cur:
            cur.execute(q, (parent_table, parent_pk))
            fks = cur.fetchall()
            for fk_table, fk_col in fks:
                # build and run existence check
                check_q = sql.SQL('SELECT EXISTS (SELECT 1 FROM {} WHERE {} = %s LIMIT 1)').format(
                    sql.Identifier(fk_table), sql.Identifier(fk_col)
                )
                cur.execute(check_q, (pk_value,))
                exists = cur.fetchone()[0]
                if exists:
                    return True
        return False

    def parent_exists(self, parent_table: str, parent_pk: str, pk_value: Any) -> bool:
        with self.conn.cursor() as cur:
            cur.execute(sql.SQL('SELECT EXISTS (SELECT 1 FROM {} WHERE {} = %s LIMIT 1)').format(
                sql.Identifier(parent_table), sql.Identifier(parent_pk)
            ), (pk_value,))
            return cur.fetchone()[0]

    # --- SQL-генерація великих обсягів даних (generate_series на сервері) ---
    # Логіка: для кожної таблиці беремо максимальний ID і додаємо записи з новими ID, щоб не порушити PK.
    def generate_students(self, count: int):
        """Генерація студентів з числовими групами (integer)"""
        first_names = [
            "Олександр", "Марія", "Дмитро", "Ірина", "Максим",
            "Катерина", "Андрій", "Ольга", "Сергій", "Наталія"
        ]
        last_names = [
            "Попов", "Шевченко", "Коваленко", "Бойко", "Мельник",
            "Ткаченко", "Кравченко", "Поліщук", "Лисенко", "Савченко"
        ]

        with self.conn.cursor() as cur:
            try:
                # Отримуємо стартовий ID (якщо стовпець Student_ID не GENERATED ALWAYS)
                cur.execute('SELECT COALESCE(MAX("Student_ID"), 0) + 1 FROM "Student";')
                start_id = cur.fetchone()[0]

                for i in range(count):
                    name = f"{random.choice(first_names)} {random.choice(last_names)}"
                    group = random.randint(31, 35)  # числові групи
                    cur.execute(
                        'INSERT INTO "Student"("Student_Name", "Group") VALUES (%s, %s)',
                        (name, group)
                    )

                self.conn.commit()
                return True, None
            except psycopg2.Error as e:
                self.conn.rollback()
                return False, e.pgerror or str(e)

        with self.conn.cursor() as cur:
            try:
                for _ in range(count):
                    name = f"{random.choice(first_names)} {random.choice(last_names)}"
                    group = random.choice(groups)
                    cur.execute(
                        'INSERT INTO "Student"("Student_Name", "Group") VALUES (%s, %s)',
                        (name, group)
                    )
                return True, None
            except psycopg2.Error as e:
                return False, e.pgerror or str(e)

    def generate_professors(self, count: int):
        first_names = ["Іван", "Людмила", "Володимир", "Оксана", "Юрій", "Світлана", "Петро", "Галина"]
        last_names = ["Сидоренко", "Петренко", "Гончаренко", "Клименко", "Романенко", "Федоренко"]
        with self.conn.cursor() as cur:
            try:
                cur.execute('SELECT COALESCE(MAX("Professor_ID"),0) + 1 FROM "Professor";')
                start_id = cur.fetchone()[0]
                for i in range(count):
                    name = f"{random.choice(first_names)} {random.choice(last_names)}"
                    exp = random.randint(1, 40)
                    cur.execute(
                        'INSERT INTO "Professor"("Professor_ID","Professor_Name","Experience") VALUES (%s,%s,%s)',
                        (start_id + i, name, exp)
                    )
                return True, None
            except psycopg2.Error as e:
                return False, e.pgerror or str(e)

    def generate_courses(self, count: int):
        subjects = ["Математика", "Програмування", "Фізика", "Моделювання", "Бази даних", "Комп’ютерні мережі", "Операційні системи", "Штучний інтелект"]
        with self.conn.cursor() as cur:
            try:
                cur.execute('SELECT COALESCE(MAX("Course_ID"),0) + 1 FROM "Course";')
                start_id = cur.fetchone()[0]
                for i in range(count):
                    subj = random.choice(subjects)
                    name = f"{subj} {random.randint(1,5)}"
                    desc = f"Курс із дисципліни {subj}"
                    cur.execute(
                        'INSERT INTO "Course"("Course_ID","Name","describe") VALUES (%s,%s,%s)',
                        (start_id + i, name, desc)
                    )
                return True, None
            except psycopg2.Error as e:
                return False, e.pgerror or str(e)

    def generate_tasks(self, count: int):
        titles = ["Лабораторна", "Контрольна", "Домашнє завдання", "Проєкт", "Тест"]
        complexities = ["Low", "Medium", "High"]
        with self.conn.cursor() as cur:
            try:
                cur.execute('SELECT COALESCE(MAX("Task_ID"),0) + 1 FROM "Task";')
                start_id = cur.fetchone()[0]
                cur.execute('SELECT array_agg("Course_ID") FROM "Course";')
                course_ids = cur.fetchone()[0] or [1]
                for i in range(count):
                    task_name = f"{random.choice(titles)} №{random.randint(1,10)}"
                    complexity = random.choice(complexities)
                    course_id = random.choice(course_ids)
                    cur.execute(
                        'INSERT INTO "Task"("Task_ID","Task_Name","Complexity","Course_ID") VALUES (%s,%s,%s,%s)',
                        (start_id + i, task_name, complexity, course_id)
                    )
                return True, None
            except psycopg2.Error as e:
                return False, e.pgerror or str(e)

    def generate_registrations(self, count: int) -> Tuple[bool, Optional[str]]:
        q = """
        WITH start AS (
          SELECT COALESCE(MAX("Registration_ID"),0) + 1 AS s,
                 COALESCE((SELECT MAX("Course_ID") FROM "Course"),0) AS max_course,
                 COALESCE((SELECT MAX("Professor_ID") FROM "Professor"),0) AS max_prof,
                 COALESCE((SELECT MAX("Student_ID") FROM "Student"),0) AS max_student
          FROM "Registration"
        )
        INSERT INTO "Registration"("Registration_ID","Course_ID","Professor_ID","Student_ID","Date")
        SELECT s + gs - 1,
               (floor(random()*G.max_course)+1)::int,
               (floor(random()*G.max_prof)+1)::int,
               (floor(random()*G.max_student)+1)::int,
               (now() - (floor(random()*1000))::int * interval '1 day')::date
        FROM start G, generate_series(1, %s) gs
        WHERE G.max_course > 0 AND G.max_prof > 0 AND G.max_student > 0;
        """
        with self.conn.cursor() as cur:
            try:
                cur.execute(q, (count,))
                return True, None
            except psycopg2.Error as e:
                return False, e.pgerror or str(e)


    # --- Складні запити (JOIN, WHERE, GROUP BY) з EXPLAIN ANALYZE для часу виконання ---
    # Повертають (rows, exec_time_ms, explain_text)
    def query_student_tasks_by_name(self, student_name_pattern: str):
        sql_text = """
        SELECT s."Student_Name" AS student, c."Name" AS course, COUNT(t."Task_ID") AS tasks_count
        FROM "Student" s
        JOIN "Registration" r ON s."Student_ID" = r."Student_ID"
        JOIN "Course" c ON r."Course_ID" = c."Course_ID"
        LEFT JOIN "Task" t ON c."Course_ID" = t."Course_ID"
        WHERE s."Student_Name" ILIKE %s
        GROUP BY s."Student_Name", c."Name"
        ORDER BY tasks_count DESC
        LIMIT 100;
        """
        return self._run_timed_query(sql_text, (f"%{student_name_pattern}%",))

    def query_professor_course_counts(self, min_experience: int):
        sql_text = """
        SELECT p."Professor_Name" AS professor, p."Experience", COUNT(DISTINCT r."Course_ID") AS courses_count
        FROM "Professor" p
        LEFT JOIN "Registration" r ON p."Professor_ID" = r."Professor_ID"
        WHERE p."Experience" >= %s
        GROUP BY p."Professor_Name", p."Experience"
        ORDER BY courses_count DESC
        LIMIT 100;
        """
        return self._run_timed_query(sql_text, (min_experience,))

    def query_course_regs_in_period(self, start_date: str, end_date: str):
        # Expect dates in 'YYYY-MM-DD' or parseable format
        # We'll pass dates as strings and let psycopg2 cast
        sql_text = """
        SELECT c."Name" AS course, COUNT(r."Registration_ID") AS regs_count
        FROM "Course" c
        JOIN "Registration" r ON c."Course_ID" = r."Course_ID"
        WHERE r."Date" BETWEEN %s AND %s
        GROUP BY c."Name"
        ORDER BY regs_count DESC
        LIMIT 100;
        """
        return self._run_timed_query(sql_text, (start_date, end_date))

    def _run_timed_query(self, sql_text: str, params: tuple):
        # Get EXPLAIN ANALYZE text
        explain_text = ""
        exec_time_ms = None
        with self.conn.cursor() as cur:
            try:
                cur.execute("EXPLAIN ANALYZE " + sql_text, params)
                lines = [r[0] for r in cur.fetchall()]  # text rows
                explain_text = "\n".join(lines)
                # find "Execution Time: X ms"
                for line in reversed(lines):
                    if "Execution Time" in line:
                        try:
                            # line like: "Execution Time: 12.345 ms"
                            exec_time_ms = float(line.strip().split(":")[1].strip().split()[0])
                        except Exception:
                            exec_time_ms = None
                        break
            except psycopg2.Error:
                # не показуємо помилку тут; продовжимо — нижче ми виконаємо сам SELECT і вернемо помилку якщо буде
                exec_time_ms = None
        # Виконати реальний запит і повернути результати
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            try:
                cur.execute(sql_text, params)
                rows = cur.fetchall()
                return rows, exec_time_ms, explain_text, None
            except psycopg2.Error as e:
                return [], exec_time_ms, explain_text, e.pgerror or str(e)

    # --- Утиліти для конвертації введення ---
    @staticmethod
    def parse_int(value: str) -> Optional[int]:
        try:
            return int(value)
        except Exception:
            return None

    @staticmethod
    def parse_date(value: str) -> Optional[str]:
        try:
            d = date_parser.parse(value)
            return d.date().isoformat()
        except Exception:
            return None
