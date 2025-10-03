# 📘 Система управління процесом навчання на курсах

## Опис проєкту
Даний проєкт реалізує ER-модель предметної області *«Система управління процесом навчання на курсах»*.  
Мета — формалізувати процеси обліку студентів, курсів, викладачів і реєстрації на курси.  

##  Структура моделі
У системі визначено такі сутності:  

1. **Студент (Student)**  
   - `student_id (PK)`  
   - `ПІБ`   
   - `Групу`  

2. **Курс (Course)**  
   - `course_id (PK)`  
   - `Назва`  
   - `Опис`  
   - `professor_id (FK)`  

3. **Професор (professor)**  
   - `professor_id (PK)`  
   - `ПІБ`  

4. **Реєстрація (Registration)**  
   - `registration_id (PK)`  
   - `student_id (FK)`  
   - `course_id (FK)`  
   - `Дата_реєстрації`  
   - `Статус`  

##  Зв’язки між сутностями
- **Студент – Курс**: зв'язок *N:M* (реалізується через сутність *Реєстрація*).  
- **Курс – Викладач**: зв'язок *1:N* (один викладач може викладати кілька курсів).   

##  Функціональні залежності

- **Student:**  
  `student_id → {Student_Name, Group}`  
  `Group → {Student_Name}`  

- **Course:**  
  `course_id → {Name, describe, professor_id}`  
  `Describe → {Name}`  

- **Professor:**  
  `professor_id → {Professor_Name}`    

- **Registration:**  
  `registration_id → {student_id, course_id, date, status}`  
  `status → {student_id}`  


