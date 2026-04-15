FROM golang:1.22-alpine AS builder

WORKDIR /app

COPY go.mod ./
RUN go mod download || true

COPY . .

RUN go build -o sr_psi_go ./cmd/api

FROM alpine:3.20

WORKDIR /app

COPY --from=builder /app/sr_psi_go /app/sr_psi_go

EXPOSE 8003

CMD ["/app/sr_psi_go"]