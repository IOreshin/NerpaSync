# NerpaSync
NerpaSync - приложение для синхронизации файлов между общим сетевым диском и локальными пользователями.
Приложение рассчитано для работы с KOMPAS-3D v22. Не требует установки дополнительного ПО или библиотек, выделения и настройки отдельного сервера и может быть запущено напрямую из KOMPAS-3D, который использует встроенный Python 3.2.

# Основные функции
### Синхронизация сетевого и локального хранилищ
### Механизм блокировки возможности изменений файлов, которые находятся на редактировании у одного из пользователей
### Создание шаблонных документов

# Перед началом работы
Проект нужно разместить в удобном для Вас месте на сетевом диске и в корневой директории создать папку "databases". После этого можно запустить NerpaSync.pym из KOMPAS-3D и создать проект. Для создания проекта необходимо выбрать папку, в которой лежат все файлы проекта.
После этого в окне "Дерево проекта" должна появиться папочная структура проекта. Затем нужно использовать "Синхронизировать с сетевого диска". Если копирование прошло успешно, можно приступать к работе с локального диска, открывая файлы из дерева проекта.

Перед внесением изменений нужно обязательно "Разрегистрировать" документ, а после завершения работы над файлом - "Зарегистрировать".

# Примечание
Автор не несет ответственность за попытку использовать приложение. Приложение написано с учетом личного опыта и специфики проекта, для которого было написано это приложение.
