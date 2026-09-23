package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"os"

	"example.com/payload/internal/config"
	"example.com/payload/internal/payload"
	pb "example.com/payload/pb"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/status"
)

type server struct {
	pb.UnimplementedPayloadServiceServer
	cache map[string]*pb.PayloadResponse
}

func (s *server) GetPayload(_ context.Context, req *pb.PayloadRequest) (*pb.PayloadResponse, error) {
	resp, ok := s.cache[req.GetSizeClass()]
	if !ok {
		return nil, status.Error(codes.InvalidArgument, "kelas payload tidak dikenal")
	}
	return resp, nil // aman dibaca banyak goroutine: marshal tidak mengubah pesan
}

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatal(err)
	}
	name := os.Getenv("SERVICE_NAME")
	if name == "" {
		name = "grpc"
	}
	svc, err := cfg.Service(name)
	if err != nil {
		log.Fatal(err)
	}

	cache := make(map[string]*pb.PayloadResponse)
	for class, recs := range payload.BuildAll(cfg) {
		cache[class] = payload.ToProto(recs)
	}

	creds, err := credentials.NewServerTLSFromFile("server.crt", "server.key")
	if err != nil {
		log.Fatal(err)
	}
	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", svc.Port))
	if err != nil {
		log.Fatal(err)
	}

	s := grpc.NewServer(grpc.Creds(creds))
	pb.RegisterPayloadServiceServer(s, &server{cache: cache})
	log.Printf("%s siap: Protobuf/HTTP2+TLS di :%d, %d kelas payload",
		name, svc.Port, len(cfg.PayloadClasses))
	log.Fatal(s.Serve(lis))
}