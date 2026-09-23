FROM golang:1.26.1-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
ARG CMD
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /app ./cmd/${CMD}

FROM alpine:3.19
WORKDIR /srv
COPY --from=build /app /srv/app
ENTRYPOINT ["/srv/app"]