package main

import (
	"crypto/tls"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"

	"example.com/payload/internal/config"
	"example.com/payload/internal/payload"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatal(err)
	}
	name := os.Getenv("SERVICE_NAME")
	if name == "" {
		name = "rest"
	}
	svc, err := cfg.Service(name)
	if err != nil {
		log.Fatal(err)
	}

	// Seluruh kelas dibangun sekali saat start; per request hanya encode + kirim.
	cache := payload.BuildAll(cfg)

	mux := http.NewServeMux()
	mux.HandleFunc(svc.Path, func(w http.ResponseWriter, r *http.Request) {
		records, ok := cache[r.URL.Query().Get("size")]
		if !ok {
			http.Error(w, "kelas payload tidak dikenal", http.StatusBadRequest)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(records)
	})
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(http.StatusOK) })

	srv := &http.Server{
		Addr:    fmt.Sprintf(":%d", svc.Port),
		Handler: mux,
		// Map kosong (bukan nil) mematikan HTTP/2 otomatis Go, sehingga REST tetap HTTP/1.1.
		TLSNextProto: map[string]func(*http.Server, *tls.Conn, http.Handler){},
	}
	log.Printf("%s siap: JSON/HTTP1.1+TLS di %s%s, %d kelas payload",
		name, srv.Addr, svc.Path, len(cfg.PayloadClasses))
	log.Fatal(srv.ListenAndServeTLS("server.crt", "server.key"))
}