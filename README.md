## Setup
    make certs      # sertifikat TLS dari konfigurasi
    make env        # .env untuk docker compose
    make proto      # generate stub Go dari payload.proto
    make sizes      # kalibrasi ukuran payload -> data/payload_sizes.csv
    make plan       # jumlah sel, jumlah run, perkiraan durasi
    make build      # build image layanan
    make up         # jalankan cAdvisor + Prometheus
    make pilot      # pilot test (config/pilot.json)
    make run        # eksperimen penuh
    make cpu dataset analyze
