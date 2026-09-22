// Package payload menyediakan data yang identik untuk layanan REST dan gRPC.
package payload

import (
	"fmt"
	"strings"

	"example.com/payload/internal/config"
	pb "example.com/payload/pb"
)

type Record struct {
	ID          int32   `json:"id"`
	Name        string  `json:"name"`
	Description string  `json:"description"`
	Value       float64 `json:"value"`
}

// description menghasilkan teks dengan panjang tepat n karakter.
func description(n int) string {
	const base = "lorem ipsum dolor sit amet "
	var b strings.Builder
	for b.Len() < n {
		b.WriteString(base)
	}
	return b.String()[:n]
}

// Build menyusun n record dengan panjang field tetap.
func Build(n, descChars int) []Record {
	d := description(descChars)
	out := make([]Record, n)
	for i := range out {
		out[i] = Record{ID: int32(i), Name: fmt.Sprintf("rec-%05d", i), Description: d, Value: float64(i) * 1.1}
	}
	return out
}

// BuildAll menyusun cache untuk seluruh kelas yang ada di konfigurasi.
func BuildAll(cfg *config.Config) map[string][]Record {
	cache := make(map[string][]Record, len(cfg.PayloadClasses))
	for _, c := range cfg.PayloadClasses {
		cache[c.Name] = Build(c.Records, cfg.Record.DescriptionChars)
	}
	return cache
}

// ToProto mengubah record menjadi pesan Protobuf yang setara.
func ToProto(recs []Record) *pb.PayloadResponse {
	resp := &pb.PayloadResponse{Records: make([]*pb.DataRecord, len(recs))}
	for i, r := range recs {
		resp.Records[i] = &pb.DataRecord{Id: r.ID, Name: r.Name, Description: r.Description, Value: r.Value}
	}
	return resp
}