
.PHONY: prepare update run migrate build-thinker

prepare:
	conda env create -f environment.yml

update:
	conda env update --file environment.yml --prune

PYTHON := $(shell conda run -n PROVIDENCE which python)

run: build-thinker
	$(PYTHON) manage.py runserver

migrate:
	$(PYTHON) manage.py makemigrations
	$(PYTHON) manage.py migrate

KIEVAN_RUS_DIR := speech/context_manager/Kievan\ Rus

build-thinker:
	cd $(KIEVAN_RUS_DIR) && $${CXX:-g++} -std=c++17 -O2 *.cpp -lcurl -o kievan_rus_thinker
