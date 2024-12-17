
VERSION = 0.1.2
IMAGE = jonross/kugel:$(VERSION)

venv:
	python3 -m venv venv

reqs: venv
	(cd venv && . bin/activate && pip install -r ../requirements.txt)

test:
	(. venv/bin/activate && PYTHONPATH=. pytest --cov --cov-report=html:coverage -vv -s --tb=native tests)

sdist:
	python3 setup.py sdist bdist_wheel

clean:
	rm -rf venv

docker:
	docker build -t $(IMAGE) .

push: docker
	echo docker push $(IMAGE)

shell: docker
	docker run -it $(IMAGE) /bin/sh
