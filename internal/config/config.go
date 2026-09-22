package config

import (
	"encoding/json"
	"fmt"
	"os"
)

type PayloadClass struct {
	Name    string `json:"name"`
	Records int    `json:"records"`
}

type Protocol struct {
	Name string `json:"name"`
	Kind string `json:"kind"`
	IP   string `json:"ip"`
	Port int    `json:"port"`
	Path string `json:"path"`
	Call string `json:"call"`
}

type Config struct {
	Record struct {
		DescriptionChars int `json:"description_chars"`
	} `json:"record"`
	PayloadClasses []PayloadClass `json:"payload_classes"`
	Protocols      []Protocol     `json:"protocols"`
}

// Load membaca berkas pada CONFIG_PATH (default: config/experiment.json).
func Load() (*Config, error) {
	path := os.Getenv("CONFIG_PATH")
	if path == "" {
		path = "config/experiment.json"
	}
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var c Config
	if err := json.Unmarshal(b, &c); err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	if len(c.PayloadClasses) == 0 || c.Record.DescriptionChars <= 0 {
		return nil, fmt.Errorf("%s: payload_classes atau record.description_chars kosong", path)
	}
	return &c, nil
}

// Service mencari definisi protokol berdasarkan namanya.
func (c *Config) Service(name string) (Protocol, error) {
	for _, p := range c.Protocols {
		if p.Name == name {
			return p, nil
		}
	}
	return Protocol{}, fmt.Errorf("protokol %q tidak ada di konfigurasi", name)
}