.PHONY: run deps

run:
	python tsukemen-alert.py

deps:
	pip install -r requirements.txt
