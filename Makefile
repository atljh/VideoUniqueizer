# Имя контейнера
CONTAINER_NAME = telegram_bot

# Команда для запуска контейнера
run:
	docker-compose up -d $(CONTAINER_NAME)

# Команда для остановки контейнера
stop:
	docker-compose stop $(CONTAINER_NAME)

# Команда для удаления контейнера
remove:
	docker-compose rm -f $(CONTAINER_NAME)

# Команда для просмотра логов
logs:
	docker-compose logs -f $(CONTAINER_NAME)

# Перезапуск контейнера
restart: stop remove run

# Построение образа
build:
	docker-compose build $(CONTAINER_NAME)

# Полная перезагрузка (пересборка образа и перезапуск контейнера)
rebuild: stop remove build run
