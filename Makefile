.PHONY: run deps
s3_bucket = tsukemen-alert

run:
	cd tsukemen_alert; python tsukemen_alert.py

deps:
	pip install -r requirements.txt

package:
	sam build --use-container
	sam package --s3-bucket $(s3_bucket)

