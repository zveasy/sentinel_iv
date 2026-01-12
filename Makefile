.PHONY: install test

install:
	python -m venv .venv
	. .venv/bin/activate && pip install -r mvp/requirements.txt

test:
	python -m unittest discover -s mvp/tests
