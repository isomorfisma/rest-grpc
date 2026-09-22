// Mengukur ukuran nyata tiap kelas payload dan menuliskannya ke data/payload_sizes.csv.
package main

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"os"
	"strconv"

	"example.com/payload/internal/config"
	"example.com/payload/internal/payload"
	"google.golang.org/protobuf/proto"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		panic(err)
	}
	f, err := os.Create("data/payload_sizes.csv")
	if err != nil {
		panic(err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()
	_ = w.Write([]string{"payload_class", "records", "json_bytes", "protobuf_bytes"})

	for _, c := range cfg.PayloadClasses {
		recs := payload.Build(c.Records, cfg.Record.DescriptionChars)
		js, _ := json.Marshal(recs)
		size := proto.Size(payload.ToProto(recs))
		_ = w.Write([]string{c.Name, strconv.Itoa(c.Records), strconv.Itoa(len(js)), strconv.Itoa(size)})
		fmt.Printf("%-4s records=%-6d json=%9d B   protobuf=%9d B\n", c.Name, c.Records, len(js), size)
	}
}