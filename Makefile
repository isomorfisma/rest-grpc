CFG      ?= config/experiment.json
OVERRIDE ?=
PY       ?= $(HOME)/venv-skripsi/bin/python3
export CFG OVERRIDE

.PHONY: help certs env proto sizes plan build up down pilot run cpu dataset analyze all

help:           ## Daftar perintah
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/ →/'

certs:          ## Sertifikat TLS dari konfigurasi
	scripts/gen_certs.sh

env:            ## Tulis .env untuk docker compose
	scripts/gen_env.sh

proto:          ## Generate stub Go dari payload.proto
	protoc --go_out=. --go_opt=module=example.com/payload \
	       --go-grpc_out=. --go-grpc_opt=module=example.com/payload payload.proto

sizes:          ## Kalibrasi ukuran payload → data/payload_sizes.csv
	go run ./cmd/sizecheck

plan:           ## Matriks dan perkiraan durasi
	$(PY) scripts/plan.py

build: env      ## Build image kedua layanan
	docker compose build

up: env         ## Jalankan cAdvisor + Prometheus
	docker compose up -d cadvisor prometheus

down:           ## Hentikan semua container
	docker compose down

pilot:          ## Pilot test (config/pilot.json)
	sudo -E env "PATH=$$PATH" OVERRIDE=config/pilot.json scripts/run_experiment.sh

run:            ## Eksperimen penuh
	sudo -E env "PATH=$$PATH" scripts/run_experiment.sh

cpu:            ## CPU per run dari Prometheus
	$(PY) scripts/collect_cpu.py

dataset:        ## raw/*.json → data/dataset.csv
	$(PY) scripts/build_dataset.py

analyze:        ## ANOVA, regresi logistik, Random Forest, gambar
	$(PY) scripts/analyze.py

all: cpu dataset analyze   ## Seluruh tahap analisis